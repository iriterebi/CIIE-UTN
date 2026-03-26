#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Compilar imágenes localmente y desplegar al servidor via SSH
# =============================================================================

set -euo pipefail

# --- Configuración -----------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${REPO_ROOT}/quadlets/.build-cache"

# Imágenes disponibles: servicio → contexto:dockerfile
declare -A IMAGES=(
    ["api"]="${REPO_ROOT}:Api/Dockerfile"
    ["webclient"]="WebClient:WebClient/Dockerfile"
    ["rosbridge"]="RosBridge:RosBridge/Dockerfile"
    ["proxy"]="Proxy:Proxy/Dockerfile"
)

# Todos los servicios válidos (los que tienen imagen compilable)
ALL_SERVICES=(api webclient rosbridge proxy)

# Orden de reinicio (incluye db que no se compila pero sí se reinicia)
RESTART_ORDER=(db rosbridge api webclient proxy)

IMAGE_PREFIX="localhost/labs-remoto"

# --- Funciones ---------------------------------------------------------------

log() {
    echo -e "\n\033[1;34m==>\033[0m \033[1m$1\033[0m"
}

log_ok() {
    echo -e "  \033[1;32m✓\033[0m $1"
}

log_err() {
    echo -e "  \033[1;31m✗\033[0m $1" >&2
}

show_help() {
    cat <<'EOF'
deploy.sh — Compilar imágenes localmente y desplegar al servidor via SSH

USO:
    ./deploy.sh <servidor> [-c <servicio>]... [-b | -d [--no-reload]]
    ./deploy.sh -h | --help

ARGUMENTOS:
    servidor              Destino SSH (usuario@host)

OPCIONES:
    -c <servicio>         Servicio a compilar/desplegar. Se puede repetir.
                          Servicios válidos: api, webclient, rosbridge, proxy.
                          Si no se especifica, se procesan todos.

    -b, --build-only      Solo compilar las imágenes localmente.
                          No transfiere ni reinicia nada en el servidor.

    -d, --deploy-only     Solo transferir y cargar imágenes ya compiladas.
                          Requiere que las imágenes existan localmente
                          (haber ejecutado -b previamente).

    --no-reload           No reiniciar servicios tras cargar las imágenes.
                          Solo válido con -d/--deploy-only.

    -h, --help            Mostrar esta ayuda.

DESCRIPCIÓN:
    Sin flags, ejecuta el flujo completo:
      1. podman build   — compila las imágenes localmente
      2. podman save    — exporta a archivos .tar
      3. scp            — transfiere los .tar al servidor
      4. podman load    — carga las imágenes en el servidor
      5. systemctl      — reinicia los servicios

    Con -b solo ejecuta los pasos 1-2. Con -d solo ejecuta 2-5.
    Con -d --no-reload ejecuta 2-4 (sin reiniciar).

REQUISITOS:
    Local:
      - podman
      - ssh y scp configurados con acceso al servidor

    Servidor:
      - podman
      - Quadlets instalados en /etc/containers/systemd/
      - Env files en /etc/containers/env/ (db.env, api.env)

IMÁGENES:
    localhost/labs-remoto/api          Api/Dockerfile        (contexto: raíz)
    localhost/labs-remoto/webclient    WebClient/Dockerfile  (contexto: WebClient/)
    localhost/labs-remoto/rosbridge    RosBridge/Dockerfile  (contexto: RosBridge/)
    localhost/labs-remoto/proxy        Proxy/Dockerfile      (contexto: Proxy/)

EJEMPLOS:
    # Deploy completo de todos los servicios
    ./deploy.sh admin@192.168.1.100

    # Solo compilar la api y el proxy
    ./deploy.sh admin@192.168.1.100 -c api -c proxy -b

    # Desplegar imágenes ya compiladas sin reiniciar
    ./deploy.sh admin@192.168.1.100 -c api -c proxy -d --no-reload

    # Compilar y desplegar solo rosbridge
    ./deploy.sh admin@192.168.1.100 -c rosbridge
EOF
}

# Validar que un nombre de servicio sea válido
validate_service() {
    local svc="$1"
    for valid in "${ALL_SERVICES[@]}"; do
        [[ "$svc" == "$valid" ]] && return 0
    done
    log_err "Servicio desconocido: '${svc}'"
    echo "  Servicios válidos: ${ALL_SERVICES[*]}" >&2
    exit 1
}

# --- Parseo de argumentos ----------------------------------------------------

SSH_TARGET=""
SELECTED_SERVICES=()
BUILD_ONLY=false
DEPLOY_ONLY=false
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
            validate_service "$2"
            SELECTED_SERVICES+=("$2")
            shift 2
            ;;
        -b|--build-only)
            BUILD_ONLY=true
            shift
            ;;
        -d|--deploy-only)
            DEPLOY_ONLY=true
            shift
            ;;
        --no-reload)
            NO_RELOAD=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_err "Opción desconocida: '$1'"
            echo "  Ejecutá ./deploy.sh --help para ver las opciones" >&2
            exit 1
            ;;
    esac
done

# Si no se especificaron servicios, usar todos
if [[ ${#SELECTED_SERVICES[@]} -eq 0 ]]; then
    SELECTED_SERVICES=("${ALL_SERVICES[@]}")
fi

# Validar combinaciones
if $BUILD_ONLY && $DEPLOY_ONLY; then
    log_err "--build-only y --deploy-only son mutuamente excluyentes"
    exit 1
fi

if $NO_RELOAD && ! $DEPLOY_ONLY; then
    log_err "--no-reload solo es válido con -d/--deploy-only"
    exit 1
fi

# Verificar que podman esté instalado
if ! command -v podman &>/dev/null; then
    log_err "podman no está instalado"
    exit 1
fi

# --- Build -------------------------------------------------------------------

do_build() {
    log "Compilando imágenes localmente"
    mkdir -p "$BUILD_DIR"

    for svc in "${SELECTED_SERVICES[@]}"; do
        IFS=':' read -r context dockerfile <<< "${IMAGES[$svc]}"

        if [[ "$context" != /* ]]; then
            context="${REPO_ROOT}/${context}"
        fi

        local image="${IMAGE_PREFIX}/${svc}"
        log "  Compilando ${svc}..."

        podman build \
            -t "$image" \
            -f "${REPO_ROOT}/${dockerfile}" \
            "$context"

        log_ok "${svc}"
    done
}

# --- Export ------------------------------------------------------------------

do_export() {
    log "Exportando imágenes a archivos .tar"
    mkdir -p "$BUILD_DIR"

    for svc in "${SELECTED_SERVICES[@]}"; do
        local image="${IMAGE_PREFIX}/${svc}"
        local tar_file="${BUILD_DIR}/${svc}.tar"

        podman save -o "$tar_file" "$image"
        log_ok "${svc}.tar ($(du -h "$tar_file" | cut -f1))"
    done
}

# --- Transfer ----------------------------------------------------------------

do_transfer() {
    log "Transfiriendo imágenes al servidor (${SSH_TARGET})"

    for svc in "${SELECTED_SERVICES[@]}"; do
        local tar_file="${BUILD_DIR}/${svc}.tar"

        if [[ ! -f "$tar_file" ]]; then
            log_err "${svc}.tar no existe. Ejecutá con -b primero."
            exit 1
        fi

        scp "$tar_file" "${SSH_TARGET}:/tmp/${svc}.tar"
        log_ok "${svc}.tar"
    done
}

# --- Load + Restart ----------------------------------------------------------

do_load() {
    log "Cargando imágenes en el servidor"

    local REMOTE_SCRIPT='set -euo pipefail
'

    for svc in "${SELECTED_SERVICES[@]}"; do
        REMOTE_SCRIPT+="
echo \"Cargando ${svc}...\"
podman load -i /tmp/${svc}.tar
rm /tmp/${svc}.tar
"
    done

    if ! $NO_RELOAD; then
        REMOTE_SCRIPT+='
echo "Reiniciando servicios..."
'
        # Reiniciar solo los servicios seleccionados, en orden de dependencias
        for svc in "${RESTART_ORDER[@]}"; do
            for selected in "${SELECTED_SERVICES[@]}"; do
                if [[ "$svc" == "$selected" ]]; then
                    REMOTE_SCRIPT+="systemctl restart ${svc}
"
                    break
                fi
            done
        done
    fi

    REMOTE_SCRIPT+='
echo "Estado de los servicios:"
systemctl --no-pager status db api rosbridge webclient proxy || true
'

    ssh "$SSH_TARGET" "sudo bash -c '${REMOTE_SCRIPT}'"
}

# --- Limpieza ----------------------------------------------------------------

do_cleanup() {
    log "Limpiando archivos temporales"
    rm -rf "$BUILD_DIR"
    log_ok "Cache de build eliminada"
}

# --- Ejecución ---------------------------------------------------------------

if $BUILD_ONLY; then
    do_build
    do_export
    log "Build completado (solo local)"
    echo "  Imágenes: ${SELECTED_SERVICES[*]}"
    echo "  Cache: ${BUILD_DIR}/"
elif $DEPLOY_ONLY; then
    do_export
    do_transfer
    do_load
    do_cleanup
    log "Deploy completado (sin build)"
    echo "  Servidor: ${SSH_TARGET}"
    echo "  Servicios: ${SELECTED_SERVICES[*]}"
    $NO_RELOAD && echo "  Reload: omitido (--no-reload)"
else
    do_build
    do_export
    do_transfer
    do_load
    do_cleanup
    log "Deploy completado"
    echo "  Servidor: ${SSH_TARGET}"
    echo "  Servicios: ${SELECTED_SERVICES[*]}"
fi
