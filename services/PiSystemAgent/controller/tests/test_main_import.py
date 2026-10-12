"""Regresión: `controller.main` debe importarse sin ROS (modo demo en el host).

En Python < 3.14 fallaba con `NameError: name 'Executor' is not defined`, porque
las anotaciones de `Executor` (importado sólo bajo TYPE_CHECKING) se evaluaban
al definir las funciones. Con 3.14 (PEP 649) se evalúan de forma diferida.
"""
import os
import subprocess
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[2]  # services/PiSystemAgent


def test_main_se_importa_sin_ros():
    env = os.environ | {
        "SERVER_URL": "http://127.0.0.1:9/m2m/robot/",
        "ARDUINO_PORT": "/dev/null",
    }
    result = subprocess.run(
        [sys.executable, "-c", "import controller.main"],
        cwd=PKG_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
