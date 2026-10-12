import asyncio
import time

from controller.server.server_service import ServerServices


def _make_service(monkeypatch, status_code: int) -> ServerServices:
    service = ServerServices(
        base_url="http://api.example/m2m/robot/",
        metadata_file="/tmp/unused-robot-metadata.json",
    )
    monkeypatch.setattr(service, "register", lambda: False)
    monkeypatch.setattr(service, "connect", lambda: status_code)
    return service


def test_cancelar_durante_el_backoff_no_retiene_el_apagado(monkeypatch):
    """Regresión: el backoff de connect_with_retry no debe dejar un thread
    dormido que bloquee el cierre de asyncio.run (docker stop → SIGKILL)."""
    service = _make_service(monkeypatch, status_code=403)

    async def main():
        task = asyncio.create_task(service.connect_with_retry(base_delay=5))
        await asyncio.sleep(0.1)  # ya entró al backoff de 5s
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    t0 = time.monotonic()
    asyncio.run(main())
    assert time.monotonic() - t0 < 1.0


def test_reintenta_hasta_el_handshake_exitoso(monkeypatch):
    service = _make_service(monkeypatch, status_code=0)
    statuses = iter([0, 403, 200])
    monkeypatch.setattr(service, "connect", lambda: next(statuses))

    assert asyncio.run(service.connect_with_retry(base_delay=0)) is True
