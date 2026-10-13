"""Tests de `controller.main` en un subproceso.

Importar `controller.main` crea `Config()` (con `cli_parse_args=True`, que leería el
argv de pytest), así que cada test corre Python aparte. El subproceso corre en un
directorio temporal: sin el `.env` del desarrollador, la config sólo ve lo que el test
le pasa.

Regresión de import: en Python < 3.14 fallaba con `NameError: name 'Executor' is not
defined`, porque las anotaciones de `Executor` (importado sólo bajo TYPE_CHECKING) se
evaluaban al definir las funciones. Con 3.14 (PEP 649) se evalúan de forma diferida.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[2]  # services/PiSystemAgent


def _run_python(*args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "ARDUINO_PORT"}
    env |= {
        "SERVER_URL": "http://127.0.0.1:9/m2m/robot/",
        "PYTHONPATH": os.pathsep.join(filter(None, [str(PKG_ROOT), env.get("PYTHONPATH")])),
    } | (extra_env or {})
    with tempfile.TemporaryDirectory() as cwd:
        return subprocess.run(
            [sys.executable, *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )


def test_main_se_importa_sin_ros():
    result = _run_python("-c", "import controller.main")
    assert result.returncode == 0, result.stderr


def test_serial_strategy_no_esta_disponible():
    """SerialStrategy se eliminó: el Arduino lo maneja el agente ROS (PiRobotDriver)."""
    result = _run_python("-m", "controller", extra_env={"LOCAL_STRATEGY": "SerialStrategy"})
    assert result.returncode != 0
    assert "Strategy local desconocido: 'SerialStrategy'" in result.stderr
    assert "SerialStrategy" not in result.stderr.split("Disponibles:")[-1]


def test_config_no_requiere_arduino_port():
    """ARDUINO_PORT era del control serial (eliminado): la config arranca sin él."""
    result = _run_python("-c", "from controller.config import config; print(config.server_url)")
    assert result.returncode == 0, result.stderr
