def test_server_imports():
    """Smoke test: el módulo principal de la API importa limpio.

    Atrapa ImportError en frío (re-exports rotos, módulos eliminados sin
    actualizar callers, dependencias circulares). Tan barato como tener
    un canario que ejecutar en CI sin levantar la API completa.
    """
    import src.server  # noqa: F401
