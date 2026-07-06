import asyncio
from unittest.mock import AsyncMock

import pytest

from src.robot.adapters import ProxyStreamSource


def _make_source():
    on_recieve = AsyncMock()
    on_accept = AsyncMock()
    on_disconnect = AsyncMock()
    on_idle_changed = AsyncMock()
    source = ProxyStreamSource(
        on_recieve=on_recieve,
        on_accept=on_accept,
        on_disconnect=on_disconnect,
        on_idle_changed=on_idle_changed,
    )
    return source, on_recieve, on_accept, on_disconnect, on_idle_changed


class TestEnqueueReceive:
    def test_round_trip(self):
        source, *_ = _make_source()

        async def run():
            await source.enqueue_data({"msg": 1})
            return await source.receive_data()

        result = asyncio.run(run())
        assert result == {"msg": 1}

    def test_orden_fifo(self):
        source, *_ = _make_source()

        async def run():
            await source.enqueue_data("a")
            await source.enqueue_data("b")
            await source.enqueue_data("c")
            return [await source.receive_data() for _ in range(3)]

        assert asyncio.run(run()) == ["a", "b", "c"]


class TestCleanQueue:
    def test_vacia_la_queue(self):
        source, *_ = _make_source()

        async def run():
            await source.enqueue_data(1)
            await source.enqueue_data(2)
            await source.clean_queue()
            return source.queue.empty()

        assert asyncio.run(run()) is True

    def test_sobre_queue_vacia_es_noop(self):
        source, *_ = _make_source()

        async def run():
            await source.clean_queue()
            return source.queue.empty()

        assert asyncio.run(run()) is True


class TestCallbacks:
    def test_accept_invoca_on_accept(self):
        source, _, on_accept, *_ = _make_source()

        asyncio.run(source.accept())

        on_accept.assert_awaited_once_with()

    def test_disconnect_invoca_on_disconnect(self):
        source, _, _, on_disconnect, _ = _make_source()

        asyncio.run(source.disconnect())

        on_disconnect.assert_awaited_once_with()

    def test_send_data_invoca_on_recieve_con_payload(self):
        source, on_recieve, *_ = _make_source()

        asyncio.run(source.send_data({"x": 1}))

        on_recieve.assert_awaited_once_with({"x": 1})

    def test_on_idle_changed_propaga_flag(self):
        source, *_, on_idle_changed = _make_source()

        asyncio.run(source.on_idle_changed(True))
        asyncio.run(source.on_idle_changed(False))

        assert on_idle_changed.await_args_list[0].args == (True,)
        assert on_idle_changed.await_args_list[1].args == (False,)


class TestBackpressure:
    def test_queue_llena_bloquea_put_nowait(self):
        source, *_ = _make_source()
        # maxsize=256 según ProxyStreamSource.__init__
        for i in range(256):
            source.queue.put_nowait(i)

        with pytest.raises(asyncio.QueueFull):
            source.queue.put_nowait(257)


from src.robot.adapters.proxy_stream_source import ProxyStreamDisconnected


class TestMarkDisconnected:
    def test_receive_data_pendiente_levanta_disconnected(self):
        source, *_ = _make_source()

        async def run():
            task = asyncio.create_task(source.receive_data())
            await asyncio.sleep(0)  # deja que receive_data empiece a esperar
            await source.mark_disconnected("timeout")
            with pytest.raises(ProxyStreamDisconnected) as exc_info:
                await task
            return exc_info.value.reason

        assert asyncio.run(run()) == "timeout"

    def test_receive_data_futura_levanta_disconnected_de_inmediato(self):
        source, *_ = _make_source()

        async def run():
            await source.mark_disconnected("clean_close")
            with pytest.raises(ProxyStreamDisconnected) as exc_info:
                await source.receive_data()
            return exc_info.value.reason

        assert asyncio.run(run()) == "clean_close"

    def test_mensaje_encolado_antes_de_desconectar_se_entrega(self):
        source, *_ = _make_source()

        async def run():
            await source.enqueue_data("a")
            result = await source.receive_data()
            await source.mark_disconnected("timeout")
            return result

        assert asyncio.run(run()) == "a"

    def test_receive_data_cancelado_propaga_cancelled_error(self):
        source, *_ = _make_source()

        async def run():
            task = asyncio.create_task(source.receive_data())
            await asyncio.sleep(0)  # deja que receive_data entre en la espera
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(run())

    def test_mensaje_y_desconexion_simultaneos_no_pierden_el_mensaje(self):
        source, *_ = _make_source()

        async def run():
            task = asyncio.create_task(source.receive_data())
            await asyncio.sleep(0)  # deja que receive_data arranque y quede esperando

            await source.enqueue_data("a")
            await source.mark_disconnected("timeout")

            return await task

        assert asyncio.run(run()) == "a"
