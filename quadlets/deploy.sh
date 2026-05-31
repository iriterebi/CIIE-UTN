#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Compilar imágenes localmente y desplegar al servidor via SSH
# =============================================================================

set -euo pipefail

# --- Configuración -----------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Imágenes disponibles: servicio → contexto:dockerfile
declare -A IMAGES=(
    ["api"]="${REPO_ROOT}:services/Api/Dockerfile"
    ["webclient"]="services/WebClient:services/WebClient/Dockerfile"
    ["proxy"]="services/Proxy:services/Proxy/Dockerfile"
)

# Todos los servicios válidos (los que tienen imagen compilable)
ALL_SERVICES=(api webclient proxy)
RESTART_ORDER=(db api webclient proxy)

# Servicios reiniciables (incluye db, que no se compila pero sí se reinicia)
RESTARTABLE_SERVICES=(api webclient proxy db)

# Directorios de quadlets (local en el repo, remoto en el servidor)
QUADLET_DIR_LOCAL="${REPO_ROOT}/quadlets"
QUADLET_DIR_REMOTE="/etc/containers/systemd"

IMAGE_PREFIX="localhost/labs-remoto"

# --- Funciones ---------------------------------------------------------------

log() {
    echo -e "\n\033[1;34m==>\033[0m \033[1m$1\033[0m";
}

log_ok() {
    echo -e "  \033[1;32m✓\033[0m $1";
}

log_err() {
    echo -e "  \033[1;31m✗\033[0m $1" >&2;
}

show_help() {
    cat <<'EOF'
deploy.sh — Compilar imágenes localmente y desplegar al servidor via SSH

USO:
    ./deploy.sh <servidor> [-c <servicio>]... [-b | -d [--no-reload] | -r | --deploy-quadlets [--no-reload]]
    ./deploy.sh -h | --help

ARGUMENTOS:
    servidor              Destino SSH (usuario@host)

OPCIONES:
    -c <servicio>         Servicio a procesar. Se puede repetir.
                          El dominio válido depende del modo:
                            -b, -d, flujo completo: api, webclient, proxy
                            -r:                     api, webclient, proxy, db
                            --deploy-quadlets:      nombres base de .container
                                                    (api, db, proxy, webclient)
                                                    + .network/.volume con
                                                    extensión explícita
                                                    (labs-remoto.network,
                                                    db-data.volume)
                          Si no se especifica, se procesan todos los del dominio.

    -b, --build-only      Solo compilar las imágenes localmente.

    -d, --deploy-only     Solo transferir imágenes ya compiladas al servidor.

    -r, --reload-only     Solo reiniciar los servicios en el servidor.
                          No compila ni transfiere imágenes.

    --deploy-quadlets     Sincroniza los archivos quadlet (.container, .network,
                          .volume) con /etc/containers/systemd/ en el servidor.
                          Sin -c, además borra los huérfanos del server que ya
                          no existen localmente. Pide confirmación interactiva
                          antes de transferir. Tras la copia ejecuta
                          systemctl daemon-reload (salvo --no-reload). No
                          reinicia servicios (usar -r después si hace falta).
                          Asume usuario remoto con escritura en
                          /etc/containers/systemd/ (no usa sudo).

    --no-reload           Suprime la acción de systemd al final del modo:
                          - con -d: no reinicia servicios
                          - con --deploy-quadlets: no corre daemon-reload

    -h, --help            Mostrar esta ayuda.

DESCRIPCIÓN:
    Modos mutuamente excluyentes:
      sin flag           build + transfer + restart (flujo completo de imágenes)
      -b                 solo build local
      -d                 transfer + restart (omitiendo build local)
      -r                 solo restart
      --deploy-quadlets  sincroniza quadlets en el servidor + daemon-reload

IMÁGENES:
    localhost/labs-remoto/api          services/Api/Dockerfile        (contexto: raíz)
    localhost/labs-remoto/webclient    services/WebClient/Dockerfile  (contexto: services/WebClient/)
    localhost/labs-remoto/proxy        services/Proxy/Dockerfile      (contexto: services/Proxy/)

EJEMPLOS:
    # Deploy completo de todos los servicios
    ./deploy.sh admin@192.168.1.100

    # Solo compilar la api y el proxy
    ./deploy.sh admin@192.168.1.100 -c api -c proxy -b

    # Desplegar imágenes ya compiladas sin reiniciar
    ./deploy.sh admin@192.168.1.100 -c api -c proxy -d --no-reload

    # Compilar y desplegar solo el webclient
    ./deploy.sh admin@192.168.1.100 -c webclient

    # Reiniciar la api en el servidor sin rebuild
    ./deploy.sh admin@192.168.1.100 -c api -r

    # Reiniciar la base de datos
    ./deploy.sh admin@192.168.1.100 -c db -r

    # Sincronizar todos los quadlets (incluye borrar huérfanos)
    ./deploy.sh admin@192.168.1.100 --deploy-quadlets

    # Sincronizar solo el quadlet de la api
    ./deploy.sh admin@192.168.1.100 -c api --deploy-quadlets

    # Sincronizar todos los quadlets sin disparar daemon-reload
    ./deploy.sh admin@192.168.1.100 --deploy-quadlets --no-reload
EOF
}

# Imprime el dominio de -c para --deploy-quadlets (basenames de .container,
# nombres completos para .network/.volume huérfanos).
quadlet_selection_domain() {
    local f base
    for f in "$QUADLET_DIR_LOCAL"/*.container; do
        [[ -e "$f" ]] || continue
        base=$(basename "$f" .container)
        echo "$base"
    done
    for f in "$QUADLET_DIR_LOCAL"/*.network "$QUADLET_DIR_LOCAL"/*.volume; do
        [[ -e "$f" ]] || continue
        # Solo se acepta con extensión si no comparte basename con un .container
        base="${f##*/}"
        local stem="${base%.*}"
        if [[ ! -e "$QUADLET_DIR_LOCAL/${stem}.container" ]]; then
            echo "$base"
        fi
    done
}

# Valida cada elemento de SELECTED_SERVICES contra el dominio de la operación
# elegida. Llamar DESPUÉS de parsear todos los args.
validate_selection() {
    local domain=()
    local op_label=""

    if $DEPLOY_QUADLETS; then
        op_label="--deploy-quadlets"
        mapfile -t domain < <(quadlet_selection_domain)
    elif $RELOAD_ONLY; then
        op_label="-r/--reload-only"
        domain=("${RESTARTABLE_SERVICES[@]}")
    else
        op_label="-b/-d/flujo completo"
        domain=("${ALL_SERVICES[@]}")
    fi

    local sel valid
    for sel in "${SELECTED_SERVICES[@]}"; do
        valid=false
        for d in "${domain[@]}"; do
            [[ "$sel" == "$d" ]] && { valid=true; break; }
        done
        if ! $valid; then
            log_err "'-c ${sel}' no es válido para ${op_label}"
            echo "  Valores aceptados: ${domain[*]}" >&2
            exit 1
        fi
    done
}

# --- Parseo de argumentos ----------------------------------------------------

SSH_TARGET=""
SELECTED_SERVICES=()
BUILD_ONLY=false
DEPLOY_ONLY=false
RELOAD_ONLY=false
DEPLOY_QUADLETS=false
NO_RELOAD=false

# Primer argumento posicional es el servidor (a menos que sea -h/--help)
if [[ $# -lt 1 ]]; then
    show_help
    exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

SSH_TARGET="$1"
shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        -c)
            [[ $# -lt 2 ]] && { log_err "-c requiere un argumento"; exit 1; }
            SELECTED_SERVICES+=("$2")
            shift 2
            ;;
        -b|--build-only)    BUILD_ONLY=true; shift ;;
        -d|--deploy-only)   DEPLOY_ONLY=true; shift ;;
        -r|--reload-only)   RELOAD_ONLY=true; shift ;;
        --deploy-quadlets)  DEPLOY_QUADLETS=true; shift ;;
        --no-reload)        NO_RELOAD=true; shift ;;
        -h|--help)          show_help; exit 0 ;;
        *)
            log_err "Opción desconocida: '$1'"
            echo "  Ejecutá ./deploy.sh --help para ver las opciones" >&2
            exit 1
            ;;
    esac
done

# Validar combinaciones — un solo modo activo
mode_count=0
$BUILD_ONLY      && ((mode_count++)) || true
$DEPLOY_ONLY     && ((mode_count++)) || true
$RELOAD_ONLY     && ((mode_count++)) || true
$DEPLOY_QUADLETS && ((mode_count++)) || true
if (( mode_count > 1 )); then
    log_err "--build-only, --deploy-only, --reload-only y --deploy-quadlets son mutuamente excluyentes"
    exit 1
fi

if $NO_RELOAD && ! $DEPLOY_ONLY && ! $DEPLOY_QUADLETS; then
    log_err "--no-reload solo es válido con -d/--deploy-only o --deploy-quadlets"
    exit 1
fi

# Validar -c contra el dominio de la operación elegida
validate_selection

# Si no se especificaron servicios, usar el dominio por defecto de la operación.
# Para --deploy-quadlets, una lista vacía significa "todos" y se resuelve más
# adelante en resolve_quadlet_files.
if [[ ${#SELECTED_SERVICES[@]} -eq 0 ]]; then
    if $RELOAD_ONLY; then
        SELECTED_SERVICES=("${RESTARTABLE_SERVICES[@]}")
    elif ! $DEPLOY_QUADLETS; then
        SELECTED_SERVICES=("${ALL_SERVICES[@]}")
    fi
fi

# Verificar que podman esté instalado (no se necesita para --deploy-quadlets)
if ! $DEPLOY_QUADLETS && ! command -v podman &>/dev/null; then
    log_err "podman no está instalado"
    exit 1
fi

# --- Build -------------------------------------------------------------------

do_build() {
    log "Compilando imágenes localmente"

    for svc in "${SELECTED_SERVICES[@]}"; do
        IFS=':' read -r context dockerfile <<< "${IMAGES[$svc]}"

        if [[ "$context" != /* ]]; then
            context="${REPO_ROOT}/${context}"
        fi

        log "  Compilando ${svc}..."
        podman build \
            -t "${IMAGE_PREFIX}/${svc}" \
            -f "${REPO_ROOT}/${dockerfile}" \
            "$context"
        log_ok "${svc}"
    done
}

# --- Transfer (stream comprimido via SSH) ------------------------------------

do_transfer() {
    log "Transfiriendo imágenes al servidor (${SSH_TARGET})"

    for svc in "${SELECTED_SERVICES[@]}"; do
        local image="${IMAGE_PREFIX}/${svc}"
        log "  Enviando ${svc}..."
        podman save "$image" | gzip | ssh "$SSH_TARGET" "gunzip | podman load"
        log_ok "${svc}"
    done
}

# --- Restart -----------------------------------------------------------------

do_restart() {
    log "Reiniciando servicios en el servidor"

    local cmds=""
    for svc in "${RESTART_ORDER[@]}"; do
        for selected in "${SELECTED_SERVICES[@]}"; do
            if [[ "$svc" == "$selected" ]]; then
                cmds+="systemctl restart ${svc} && "
                break
            fi
        done
    done

    cmds+="echo 'Estado de los servicios:' && systemctl --no-pager status db api webclient proxy || true"
    ssh "$SSH_TARGET" "bash -c '${cmds}'"
}

# --- Deploy de quadlets -------------------------------------------------------

# Imprime (por stdout, uno por línea) los basenames de archivos a copiar.
resolve_quadlet_files() {
    local sel

    if [[ ${#SELECTED_SERVICES[@]} -eq 0 ]]; then
        # Sin -c: todos los .container/.network/.volume del directorio
        local f
        for f in "$QUADLET_DIR_LOCAL"/*.container \
                 "$QUADLET_DIR_LOCAL"/*.network \
                 "$QUADLET_DIR_LOCAL"/*.volume; do
            [[ -e "$f" ]] && echo "${f##*/}"
        done
        return
    fi

    for sel in "${SELECTED_SERVICES[@]}"; do
        if [[ "$sel" == *.network || "$sel" == *.volume ]]; then
            # Caso excepcional: nombre con extensión
            echo "$sel"
        else
            # Nombre base: .container + .network/.volume que compartan basename
            [[ -e "$QUADLET_DIR_LOCAL/${sel}.container" ]] && echo "${sel}.container"
            [[ -e "$QUADLET_DIR_LOCAL/${sel}.network" ]]   && echo "${sel}.network"
            [[ -e "$QUADLET_DIR_LOCAL/${sel}.volume" ]]    && echo "${sel}.volume"
        fi
    done
}

# Imprime (por stdout, uno por línea) los archivos que están en el server
# pero ya no en el repo. Solo aplica cuando se sincroniza todo (sin -c).
detect_quadlet_orphans() {
    local remote local_list
    remote=$(ssh "$SSH_TARGET" "ls -1 ${QUADLET_DIR_REMOTE} 2>/dev/null | grep -E '\\.(container|network|volume)\$' || true" 2>/dev/null || true)
    local_list=$(cd "$QUADLET_DIR_LOCAL" && ls -1 *.container *.network *.volume 2>/dev/null || true)
    comm -23 <(echo "$remote" | sort -u) <(echo "$local_list" | sort -u) | grep -v '^$' || true
}

# Pregunta al usuario antes de transferir. Cancela si la respuesta no es y/Y.
confirm_quadlet_deploy() {
    local -n _to_copy=$1
    local -n _to_delete=$2

    log "Archivos a enviar a ${SSH_TARGET}:${QUADLET_DIR_REMOTE}/"
    local f
    for f in "${_to_copy[@]}"; do
        echo "  + ${f}"
    done

    if (( ${#_to_delete[@]} > 0 )); then
        echo
        log "Archivos a eliminar del servidor (huérfanos):"
        for f in "${_to_delete[@]}"; do
            echo "  - ${f}"
        done
    fi

    echo
    local ans
    read -r -p "¿Continuar? [y/N] " ans
    if [[ ! "$ans" =~ ^[yY]$ ]]; then
        log "Cancelado por el usuario"
        exit 0
    fi
}

# Ejecuta la transferencia, el rm de huérfanos y el daemon-reload.
do_deploy_quadlets() {
    local -n _to_copy=$1
    local -n _to_delete=$2

    log "Preparando ${QUADLET_DIR_REMOTE}/ en ${SSH_TARGET}"
    ssh "$SSH_TARGET" "mkdir -p ${QUADLET_DIR_REMOTE}"

    log "Transfiriendo quadlets"
    local f
    for f in "${_to_copy[@]}"; do
        log "  Enviando ${f}..."
        cat "${QUADLET_DIR_LOCAL}/${f}" | ssh "$SSH_TARGET" "tee ${QUADLET_DIR_REMOTE}/${f} > /dev/null"
        log_ok "${f}"
    done

    if (( ${#_to_delete[@]} > 0 )); then
        log "Eliminando huérfanos"
        local rm_cmd=""
        for f in "${_to_delete[@]}"; do
            rm_cmd+="rm -f ${QUADLET_DIR_REMOTE}/${f}; "
        done
        ssh "$SSH_TARGET" "${rm_cmd}"
        for f in "${_to_delete[@]}"; do
            log_ok "borrado: ${f}"
        done
    fi

    if ! $NO_RELOAD; then
        log "systemctl daemon-reload"
        ssh "$SSH_TARGET" "systemctl daemon-reload"
        log_ok "daemon-reload"
    fi
}

# --- Ejecución ---------------------------------------------------------------

if $BUILD_ONLY; then
    do_build
    log "Build completado (solo local)"
    echo "  Imágenes: ${SELECTED_SERVICES[*]}"
elif $DEPLOY_ONLY; then
    do_transfer
    $NO_RELOAD || do_restart
    log "Deploy completado (sin build)"
    echo "  Servidor: ${SSH_TARGET}"
    echo "  Servicios: ${SELECTED_SERVICES[*]}"
    $NO_RELOAD && echo "  Reload: omitido (--no-reload)"
elif $RELOAD_ONLY; then
    do_restart
    log "Reload completado (sin build ni transfer)"
    echo "  Servidor: ${SSH_TARGET}"
    echo "  Servicios: ${SELECTED_SERVICES[*]}"
elif $DEPLOY_QUADLETS; then
    mapfile -t TO_COPY < <(resolve_quadlet_files)
    if (( ${#TO_COPY[@]} == 0 )); then
        log_err "No hay archivos quadlet a transferir"
        exit 1
    fi

    TO_DELETE=()
    if [[ ${#SELECTED_SERVICES[@]} -eq 0 ]]; then
        mapfile -t TO_DELETE < <(detect_quadlet_orphans)
    fi

    confirm_quadlet_deploy TO_COPY TO_DELETE
    do_deploy_quadlets TO_COPY TO_DELETE

    log "Quadlets sincronizados"
    echo "  Servidor: ${SSH_TARGET}:${QUADLET_DIR_REMOTE}/"
    echo "  Copiados: ${TO_COPY[*]}"
    (( ${#TO_DELETE[@]} > 0 )) && echo "  Borrados: ${TO_DELETE[*]}"
    $NO_RELOAD && echo "  daemon-reload: omitido (--no-reload)"
else
    do_build
    do_transfer
    do_restart
    log "Deploy completado"
    echo "  Servidor: ${SSH_TARGET}"
    echo "  Servicios: ${SELECTED_SERVICES[*]}"
fi
