# Investigación: ¿Typer para el CLI de gestión del controlador?

Veredicto sobre si conviene adoptar [Typer](https://typer.tiangolo.com/) para el CLI
de gestión del micro core de RaspberryPi (`services/RaspberryPi/cli/`), o si es
overhead frente a alternativas (click directo, argparse stdlib, o seguir con el
dispatch manual actual).

---

## 1. Resumen ejecutivo

**Recomendación: seguir con stdlib (`argparse` con subparsers anidados) por ahora.
No adoptar Typer.**

Razones cortas:

- El CLI es chico y va a crecer poco. La filosofía del proyecto es dependencias
  mínimas y bien justificadas; Typer arrastra `click + rich + shellingham +
  annotated-doc` (4 paquetes nuevos) para resolver un dispatch que ya está
  resuelto en ~180 líneas con `match`.
- **Typer no soporta `async def` nativamente** (issue #950 abierto del propio
  tiangolo). Hay que envolver con `asyncio.run` igual que ahora, lo cual elimina
  buena parte del atractivo "ergonómico" para este caso, donde casi todos los
  comandos son async.
- El **caso pesado es scoped args por strategy** (`cli connection remote select
  wsstrategy --token X --url Y`). Typer/click nestean grupos pero no resuelven
  bien argumentos cuyo schema depende del valor de un argumento previo
  posicional (el nombre del strategy). Hay que implementar dispatch manual igual,
  o forzar a que cada strategy sea un subcomando concreto.
- `argparse` con subparsers cubre el 100% de las necesidades actuales y planeadas
  con cero dependencias y un patrón conocido por cualquier dev de Python.

Reconsiderar Typer si: (a) el CLI deja de ser solo gestión y se vuelve interfaz
principal de operación, (b) se necesita output rico/coloreado serio (tablas,
progress bars), o (c) el proyecto adopta Typer en otro servicio y vale unificar.

---

## 2. Necesidades del CLI (recap)

El CLI vive en `services/RaspberryPi/cli/cli.py` y:

- Es un proceso separado del controlador. Se conecta vía Unix socket
  (`/tmp/robot-controller.sock` por default) y habla JSON-RPC 2.0 delimitado
  por newline.
- Se invoca como `python -m cli ...` (entry point en `cli/__main__.py`).
- Es **gestión, no operación**: status, start/stop/pause/resume de strategies,
  switch-telemetry, y a futuro `select` de strategy con argumentos propios.
- Casi todos los comandos son `async def` porque la I/O al socket usa
  `asyncio.open_unix_connection`. Hoy se envuelve con un único `asyncio.run`
  en `__main__.py` y `main()` hace dispatch con `match args`.
- Comparte tipos con el controlador (`controller.type_defs`) — `JsonRpcRequest`,
  `JsonRpcResponse`, `CoreStatusData`, `StatusData`.
- Necesita crecer hacia comandos anidados con la forma:

  ```
  cli connection {local|remote} {status|start|stop|pause|resume}
  cli connection {local|remote} select list
  cli connection {local|remote} select <strategy_name> [args propios]
  ```

  El último caso es el delicado: cada strategy define sus propios args
  (`wsstrategy --token X --url Y` distinto de `mqttstrategy --broker B --topic T`).

- Stack del proyecto: Python 3.13.7+, gestor `uv`, dependencias actuales
  mínimas y todas operativas (pydantic, websockets, requests, pyserial,
  python-dotenv). Sin Typer/click/rich en ningún lado.
- Equipo de 3 personas, código en español/inglés, comentarios mínimos.

Punto importante: el lado servidor (micro core) ya hace el ruteo real por nombre
de método JSON-RPC (`connection::remote::start`). El CLI solo arma el string del
método y un dict de params. **El parsing del CLI no necesita conocer la lógica
del strategy**, solo pasarle los flags como dict al servidor.

---

## 3. Análisis de Typer

### 3.1 Pros para este caso

- **Type hints + Annotated**: encaja con el estilo del repo (Python 3.13, ya
  usa generics nuevos en `JsonRpcRequest[T]`). Sintaxis legible:

  ```python
  def start(
      scope: Annotated[Scope, typer.Argument(help="local o remote")],
  ) -> None: ...
  ```

- **Help auto-generado**: el help estático actual (con `dedent`) hay que
  mantenerlo a mano. Typer lo genera y lo formatea con rich. Buena UX cuando
  hay muchos comandos.
- **Sub-apps con `add_typer`** mapean bien al modelo de scoped commands:

  ```python
  app = typer.Typer()
  connection_app = typer.Typer()
  remote_app = typer.Typer()
  app.add_typer(connection_app, name="connection")
  connection_app.add_typer(remote_app, name="remote")

  @remote_app.command()
  def start(): ...
  ```

- **Callback global** para opciones comunes (`--socket-path`, `--verbose`)
  via `@app.callback()` y context para compartir estado entre subcomandos.
- **Validación automática** de tipos (`Enum`, `int`, `bool`...). Para `scope`
  basta un `Enum("Scope", ["local", "remote"])`.

### 3.2 Contras concretos para *este* caso

- **No soporta async nativo.** Confirmado: issue
  [tiangolo/typer#950](https://github.com/fastapi/typer/issues/950) sigue
  abierto en 2026. Hay que escribir uno de estos por cada comando:

  ```python
  @app.command()
  def status(scope: Optional[Scope] = None) -> None:
      asyncio.run(_status_impl(socket_path, scope))
  ```

  o un decorador propio que envuelva con `asyncio.run`. En el código actual
  hay UN `asyncio.run` en `__main__.py`. Con Typer, cada función Typer es
  síncrona y dispara su propio `asyncio.run`, o se mantiene el wrapper a mano.
  Esto **anula el beneficio ergonómico** porque el grueso del código es I/O.

- **Dependencias**: Typer requiere `click >= 8.2.1`, `rich >= 13.8.0`,
  `shellingham >= 1.3.0`, `annotated-doc >= 0.0.2`. Son ~3-5 MB instalados.
  Para un CLI de gestión que probablemente nunca se ejecute en producción
  (solo via SSH puntual o desde el host de dev), eso es bastante peso. Más
  importante: **rompe la regla "dependencias mínimas y justificadas"** del
  proyecto. Hoy `pyproject.toml` tiene 6 dependencias, todas con un rol claro.
  Sumar 4 más para reemplazar 30 líneas de dispatch es desproporcionado.

- **Scoped args por strategy no se modela elegante.** El comando objetivo:

  ```
  cli connection remote select wsstrategy --token X --url Y
  cli connection remote select mqttstrategy --broker B --topic T
  ```

  No es trivial en Typer (ni en click). Tres opciones:

  1. **Un subcomando Typer por strategy**: `select.command("wsstrategy")`,
     `select.command("mqttstrategy")`. **Problema**: el CLI tendría que
     conocer el registro de strategies del servidor, hardcodear sus nombres,
     y declarar sus args. Acopla CLI con servidor — exactamente lo opuesto
     a lo que el JSON-RPC desacopló.
  2. **Un solo comando `select` con `nargs=-1` (extra args)**: pasás todo
     después del nombre del strategy como lista cruda, parseás `--key value`
     a mano y lo mandás como `params` al servidor. Funciona. **Pero entonces
     Typer no te ayuda en esa parte** — estás haciendo lo mismo que harías
     con `argparse` o con el match actual.
  3. **`context_settings={"allow_extra_args": True, "ignore_unknown_options":
     True}`**: Typer hereda esto de click. Te da el `ctx.args` con los flags
     no parseados. Mismo costo: parseás los `--token X --url Y` manual.

  Las tres opciones equivalen a "Typer hasta `select`, después manual". El
  beneficio queda solo en los comandos sin scoped args.

- **Curva**: Typer es ergonómico pero tiene su propia capa de magia
  (Annotated, callbacks, contextos). El equipo es chico — alguien tiene que
  conocer la herramienta lo suficiente para no caer en trampas (orden de
  evaluación de callbacks, `invoke_without_command`, `no_args_is_help`,
  qué se hereda y qué no entre sub-apps). No es horrible pero suma.

- **Help auto pierde el control fino**. El help actual está en español, con
  `\t` de alineación y agrupado lógicamente. Typer mete las cosas en los
  panels que él considera. Configurable con `rich_help_panel` y
  `help` arg, sí — pero cada customización te acerca al esfuerzo de mantener
  un help a mano.

### 3.3 Snippet ilustrativo (cómo se vería)

```python
import asyncio
from enum import Enum
from typing import Annotated, Optional
import typer

app = typer.Typer(no_args_is_help=True)
connection_app = typer.Typer(no_args_is_help=True)
app.add_typer(connection_app, name="connection")

class Scope(str, Enum):
    local = "local"
    remote = "remote"

@app.callback()
def main(
    ctx: typer.Context,
    socket_path: Annotated[str, typer.Option()] = DEFAULT_SOCKET_PATH,
) -> None:
    ctx.obj = {"socket_path": socket_path}

@connection_app.command("start")
def connection_start(
    ctx: typer.Context,
    scope: Annotated[Scope, typer.Argument()],
) -> None:
    asyncio.run(cmd_connection_action(ctx.obj["socket_path"], "start", scope.value))

# Para `select wsstrategy --token X --url Y` hay que hacer esto:
@connection_app.command(
    "select",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def connection_select(
    ctx: typer.Context,
    scope: Annotated[Scope, typer.Argument()],
    strategy: Annotated[str, typer.Argument()],
) -> None:
    extra = parse_kv_flags(ctx.args)  # parser propio: --token X --url Y → {token: X, url: Y}
    asyncio.run(send_request(
        ctx.obj["socket_path"],
        f"connection::{scope.value}::select",
        {"strategy": strategy, "args": extra},
    ))
```

Notar que `parse_kv_flags` es ~10 líneas que igual hay que escribir. Y todos
los comandos terminan con `asyncio.run(...)` boilerplate.

---

## 4. Análisis de click

Click es la base sobre la que se monta Typer. Si el atractivo de Typer son los
Annotated y el help bonito, y descontamos eso, queda preguntarse: ¿conviene
click directo?

### 4.1 Pros

- **Una dependencia menos** que Typer (no rich, no shellingham, no
  annotated-doc). Solo `click` (~250 KB).
- **Anidamiento de grupos** es la feature estrella, mejor que argparse.
  `@parent.group()` y `@grupo.command()` son legibles:

  ```python
  @click.group()
  def cli(): pass

  @cli.group()
  def connection(): pass

  @connection.group()
  def remote(): pass

  @remote.command()
  @click.argument("scope")
  def start(scope): ...
  ```

- **`pass_context` + `ctx.ensure_object`** para opciones globales como
  `--socket-path`. Patrón estándar y documentado.
- **Soporte nativo de `allow_extra_args` / `ignore_unknown_options`** en
  `context_settings` — útil para los scoped args del `select`.
- Sintaxis con decoradores: el dev típico de Flask/FastAPI lo lee al toque.

### 4.2 Contras

- **Sin async nativo tampoco.** Mismo problema que Typer: `asyncio.run` por
  comando o decorador propio.
- **Sigue siendo una dependencia nueva** para reemplazar dispatch manual.
- **No usa type hints**: las firmas de los comandos son `def start(scope)`,
  con los tipos declarados en los decoradores `@click.argument(..., type=...)`.
  Choca con el estilo "type hints modernos" del repo.
- Mismo problema con scoped args por strategy: terminás parseando manual los
  flags extras o declarando un comando por strategy.

Click es una opción razonable y más liviana que Typer, pero con el mismo
trade-off central: no resuelve async, no resuelve scoped args, suma
dependencia. **No vale la pena si no hay otro consumidor de click en el repo.**

---

## 5. Análisis de argparse

`argparse` es stdlib. Soporta subparsers anidados (Python 3.13 los soporta
sin issues). El patrón:

```python
import argparse, asyncio

parser = argparse.ArgumentParser(prog="cli")
parser.add_argument("--socket-path", default=DEFAULT_SOCKET_PATH)
sub = parser.add_subparsers(dest="cmd", required=True)

# connection
conn = sub.add_parser("connection")
conn_sub = conn.add_subparsers(dest="scope", required=True)

for scope in ("local", "remote"):
    s = conn_sub.add_parser(scope)
    s_sub = s.add_subparsers(dest="action", required=True)
    for act in ("status", "start", "stop", "pause", "resume"):
        s_sub.add_parser(act)
    sel = s_sub.add_parser("select")
    sel.add_argument("strategy", nargs="?")  # opcional para "select list"
    sel.add_argument("strategy_args", nargs=argparse.REMAINDER)

args = parser.parse_args()
asyncio.run(dispatch(args))
```

### 5.1 Pros

- **Cero dependencias**. Coherente con la filosofía del proyecto.
- **Async limpio**: un único `asyncio.run(dispatch(args))` al final, igual
  que hoy. Es lo que el código actual ya hace bien.
- **`nargs=REMAINDER`** captura todo lo que viene después del nombre del
  strategy en `select wsstrategy --token X --url Y`. Pasás esa lista al
  servidor o la parseás con un mini-parser propio (`shlex` + dict).
  **Esto es exactamente lo que hace falta** y argparse no lucha contra el caso.
- Help auto-generado, no tan lindo como Typer pero suficiente para gestión.
- **Cualquier dev de Python lo conoce**. Cero curva.
- El dispatch manual con `match` ya está implementado y funciona — migrar
  a argparse es básicamente declarar los subparsers y mantener el `match`
  o convertirlo a `getattr(module, args.cmd)`.

### 5.2 Contras

- **Verbose**: declarar sub/sub/sub/sub-parsers es repetitivo. Ayudable con un
  helper interno (`for scope in ...:` como en el snippet).
- **Sin type hints "vivos"**: los args salen del Namespace como `Any`. Se
  resuelve con un `cast` o un TypedDict propio. No es bonito pero es lo de hoy.
- Help no tiene panels ni colores. Para un CLI de gestión es un no-issue.
- El parser de subparsers anidados puede dar mensajes de error un poco
  ásperos. Mitigable con `parser.error()` custom donde haga falta.

### 5.3 Tamaño estimado

Migrar el CLI actual (~180 líneas) a argparse + dispatch tabular:
estimado **150-220 líneas**. Mismo orden de magnitud, mejor estructura,
sin nuevas dependencias.

---

## 6. Comparación lado a lado

| Criterio                          | Typer                              | click                            | argparse (stdlib)               | match actual                |
|-----------------------------------|------------------------------------|----------------------------------|---------------------------------|-----------------------------|
| Async `def` nativo                | No (issue #950 abierto)            | No                               | N/A (parsing es sync)           | Sí (un solo `asyncio.run`)  |
| Subcomandos anidados              | Sí (`add_typer`)                   | Sí (`@grupo.group`)              | Sí (`add_subparsers` anidados)  | Sí (`match` patterns)       |
| Scoped args por strategy          | Manual (`allow_extra_args`)        | Manual (`allow_extra_args`)      | Limpio con `nargs=REMAINDER`    | Manual                      |
| Help auto                         | Sí, rico (rich)                    | Sí, plano                        | Sí, plano                       | A mano (`dedent`)           |
| Type hints                        | Sí, idiomático (`Annotated`)       | No (decoradores)                 | No (Namespace)                  | Sí (en handlers)            |
| Validación auto (Enum, int...)    | Sí                                 | Sí (`type=...`)                  | Sí (`type=`, `choices=`)        | Manual                      |
| Peso de dependencia               | click+rich+shellingham+annotated-doc | click (~250 KB)                | 0 (stdlib)                      | 0                           |
| Curva para el equipo              | Media                              | Baja-media                       | Baja (todos lo conocen)         | Mínima                      |
| Coherencia con filosofía del repo | Floja (4 deps nuevas)              | Aceptable (1 dep)                | Total (0 deps)                  | Total                       |
| Ergonomía al escribir comandos    | Alta                               | Media-alta                       | Media-baja                      | Media                       |
| Customización fina del output     | Buena (panels, colors)             | Buena                            | Limitada                        | Total (control absoluto)    |

---

## 7. Veredicto

**Usar `argparse` con subparsers anidados.** Migrar el dispatch manual
(`match args`) a argparse, manteniendo el resto de la arquitectura igual:
un único `asyncio.run` en el entry point, handlers `async def cmd_*`,
`send_request` ya tipado.

Justificación condensada:

1. El argumento más fuerte para Typer/click —ergonomía con type hints y help
   auto— se diluye porque **todos los comandos son async** y hay que envolver
   con `asyncio.run` igual.
2. El segundo argumento —subcomandos anidados— `argparse` lo cubre
   suficientemente bien para 2-3 niveles, que es lo que el CLI llegará a tener.
3. El caso peliagudo —**scoped args por strategy**— `argparse` lo resuelve más
   limpio (`nargs=REMAINDER`) que Typer/click, donde hay que activar
   `allow_extra_args` y parsear flags a mano.
4. Filosofía del repo: dependencias mínimas. Sumar 4 paquetes (Typer) o 1
   (click) para reemplazar dispatch manual no se justifica para un CLI de
   gestión de bajo tráfico.
5. Cero curva. Cualquier persona que llegue al equipo lee `argparse` sin docs.

### 7.1 Boceto del comando objetivo

```python
# cli/cli.py (esqueleto)
import argparse
import asyncio
import shlex
import sys

DEFAULT_SOCKET_PATH = "/tmp/robot-controller.sock"

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cli")
    p.add_argument("--socket-path", default=DEFAULT_SOCKET_PATH)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("help")

    st = sub.add_parser("status")
    st.add_argument("scope", nargs="?", choices=["local", "remote"])

    sw = sub.add_parser("switch-telemetry")
    sw.add_argument("state", choices=["on", "off"])

    # Grupo "connection"
    conn = sub.add_parser("connection")
    conn_sub = conn.add_subparsers(dest="scope", required=True)

    for scope in ("local", "remote"):
        s = conn_sub.add_parser(scope)
        s_sub = s.add_subparsers(dest="action", required=True)

        for act in ("status", "start", "stop", "pause", "resume"):
            s_sub.add_parser(act)

        sel = s_sub.add_parser("select")
        sel.add_argument("strategy", nargs="?")  # vacío o "list" o nombre
        # REMAINDER captura todo lo que sigue tal cual: --token X --url Y
        sel.add_argument("strategy_args", nargs=argparse.REMAINDER)

    return p


def parse_kv_flags(tokens: list[str]) -> dict[str, str]:
    """`['--token', 'X', '--url', 'Y']` → `{'token': 'X', 'url': 'Y'}`."""
    out: dict[str, str] = {}
    it = iter(tokens)
    for tok in it:
        if not tok.startswith("--"):
            raise SystemExit(f"argumento inesperado: {tok}")
        key = tok.removeprefix("--")
        try:
            out[key] = next(it)
        except StopIteration:
            raise SystemExit(f"falta valor para --{key}")
    return out


async def dispatch(args: argparse.Namespace) -> None:
    sp = args.socket_path
    match args.cmd:
        case "help":
            print_help()
        case "status":
            await cmd_status(sp, args.scope)
        case "switch-telemetry":
            await cmd_switch_telemetry(sp, args.state)
        case "connection":
            await cmd_connection(sp, args)


async def cmd_connection(sp: str, args: argparse.Namespace) -> None:
    scope: str = args.scope        # "local" | "remote"
    action: str = args.action      # "start" | ... | "select"

    if action == "select":
        strategy: str | None = args.strategy
        if strategy is None or strategy == "list":
            print_response(await send_request(sp, f"connection::{scope}::select_list"))
            return
        params = {"strategy": strategy, "args": parse_kv_flags(args.strategy_args)}
        print_response(await send_request(sp, f"connection::{scope}::select", params))
        return

    # start | stop | pause | resume | status
    method = f"connection::{scope}::{action}"
    print_response(await send_request(sp, method))


def main_entry() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(dispatch(args))
    except (ConnectionRefusedError, FileNotFoundError):
        print(f"Error: no se pudo conectar al controlador. Socket: {args.socket_path}")
        sys.exit(1)


if __name__ == "__main__":
    main_entry()
```

Notas de diseño:

- Los **scoped args de cada strategy** se mandan crudos como `params.args`
  (un dict). El **servidor** valida que sean los esperados para ese strategy
  y devuelve error JSON-RPC si faltan. Esto es coherente con el patrón actual
  del proyecto: validación en adapters, no en el pipe.
- El CLI **no conoce** los strategies. Solo arma el método y pasa los flags.
  Acoplamiento bajo, evolución independiente de cliente y servidor.
- El help estático actual (`print_help`) se mantiene si se quiere control
  total del formato en español. argparse genera uno automático también,
  podés conservar ambos: `parser.print_help()` para `-h/--help`, y
  `print_help()` propio para `cli help`.
- Si el CLI crece, conviene partir `cli.py` en `cli/commands/connection.py`,
  `cli/commands/status.py`, etc., con cada módulo exponiendo un
  `register(subparsers)` y `dispatch(args)`. argparse lo permite sin fricción.

### 7.2 Checklist de migración mínima

1. Reemplazar el `match args` de `main()` por `argparse.ArgumentParser`
   construido con un helper `build_parser()`.
2. Mantener intactas `send_request`, `cmd_status`, `cmd_switch_telemetry`,
   `cmd_connection_action`, `print_*`. Cambia solo cómo se llaman.
3. Agregar `parse_kv_flags()` (10 líneas) para los args extra de `select`.
4. Mover `print_help` a `parser.print_help()` o conservarlo si preferís
   formato propio.
5. No tocar `__main__.py` ni `__init__.py`. El entry point sigue siendo el
   mismo.

Estimado: **media tarde**, sin dependencias nuevas.

---

## 8. Riesgos y cuándo reconsiderar

- **Si el CLI cruza ~15-20 comandos con muchas opciones por comando**:
  argparse se vuelve denso (mucho `add_argument`). En ese punto, **click**
  (no Typer) es la migración natural — sigue sin async pero los grupos
  anidados con decoradores son más legibles. Costo: 1 dependencia.
- **Si se agrega un CLI similar en otro servicio del proyecto (Api,
  RaspberryPi nivel sistema)**: vale unificar bajo Typer/click. La
  consistencia entre servicios pesa más que -1 dependencia.
- **Si el output empieza a necesitar tablas, color, progress bars en
  serio** (no solo ANSI básico): Typer + rich tiene una ventaja real,
  porque rich ya viene como transitiva y la integración es directa.
- **Si Typer cierra el issue #950 y soporta async nativo**: vale revisar.
  En ese momento el principal contra técnico de Typer desaparece y queda
  solo el peso de dependencias, que es subjetivo.
- **Si el "select strategy" pasa a tener validación rica del lado cliente**
  (ej: el CLI hace `select list` primero, infiere los args válidos del
  strategy y los valida antes de mandar): entonces conviene un dispatch más
  estructurado, y click con un comando dinámico por strategy podría tener
  sentido. Hoy no es el caso — la validación vive en el servidor.
- **Si aparece autocompletado de shell** como requerimiento (bash/zsh
  completion): Typer lo da gratis (vía shellingham). argparse necesita
  `argcomplete`, que suma una dep. Para un CLI de gestión interno,
  probablemente no haga falta.

---

## 9. Apéndice: por qué NO seguir con `match args` puro

El dispatch manual actual está bien para 6-7 comandos. Cuando se sumen
`connection`, `select`, `select list` y posibles `--socket-path` global, el
`match` se vuelve frágil:

- No valida `--flags` mezclados con posicionales.
- Un typo en el comando da "comando desconocido" sin sugerencia.
- No hay help por subcomando (`cli connection -h`).
- La extensión a más niveles (3-4 deep) explota la cantidad de patterns.

Por eso vale migrar a `argparse` ahora, no después. Es trabajo barato y
deja la base lista para los comandos del punto 6 de `ARQUITECTURA.md`.
