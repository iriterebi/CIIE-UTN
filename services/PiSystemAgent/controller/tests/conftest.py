"""Stubs mínimos de ROS 2 para importar los módulos que dependen de rclpy sin ROS
instalado (host / modo demo).

`ros2_controller`, `ros2_strategy` y `camera_relay` importan rclpy, std_msgs y
sensor_msgs al cargarse. Si el import real falla, se registran módulos stub con
los nombres que esos módulos usan; los tests reemplazan luego esos nombres en el
módulo bajo prueba con fakes vía `monkeypatch.setattr`. Con ROS disponible (el
contenedor de `make ros.test`) se usan los módulos reales y los stubs no se instalan.
"""

import importlib
import sys
import types


class _StubType:
    """Clase stub; soporta `Stub[T]` en anotaciones (ej. `Publisher[String]`)."""

    def __class_getitem__(cls, _item):
        return cls


def _stub_package(name: str, submodules: dict[str, dict[str, object]]) -> None:
    try:
        _ = importlib.import_module(name)
        return
    except ImportError:
        pass

    package = types.ModuleType(name)
    sys.modules[name] = package
    for sub, attrs in submodules.items():
        module = types.ModuleType(f"{name}.{sub}")
        module.__dict__.update(attrs)
        sys.modules[f"{name}.{sub}"] = module
        setattr(package, sub, module)


def _stub_class(name: str) -> type:
    return type(name, (_StubType,), {})


_stub_package("rclpy", {
    "node": {"Node": _stub_class("Node")},
    "publisher": {"Publisher": _stub_class("Publisher")},
    "executors": {"Executor": _stub_class("Executor")},
})
_stub_package("std_msgs", {"msg": {"String": _stub_class("String")}})
_stub_package("sensor_msgs", {"msg": {"Image": _stub_class("Image")}})
