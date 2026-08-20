import asyncio

from src.robot.repositories.video_relay import VideoRelay, VideoRelayRepository


class TestVideoRelay:
    def test_push_luego_next_frame_entrega_el_mismo_frame(self):
        relay = VideoRelay()

        async def run():
            relay.push_frame(b"frame1")
            return await relay.next_frame()

        assert asyncio.run(run()) == b"frame1"

    def test_next_frame_espera_hasta_que_llega_un_frame(self):
        relay = VideoRelay()

        async def run():
            async def _push_later():
                await asyncio.sleep(0.01)
                relay.push_frame(b"tardio")

            waiter = asyncio.create_task(relay.next_frame())
            pusher = asyncio.create_task(_push_later())
            result = await waiter
            await pusher
            return result

        assert asyncio.run(run()) == b"tardio"

    def test_ultimo_frame_gana_si_no_se_consume(self):
        relay = VideoRelay()

        async def run():
            relay.push_frame(b"a")
            relay.push_frame(b"b")
            return await relay.next_frame()

        assert asyncio.run(run()) == b"b"

    def test_frames_no_se_acumulan_tras_consumir(self):
        relay = VideoRelay()

        async def run():
            relay.push_frame(b"a")
            first = await relay.next_frame()

            async def _push_later():
                await asyncio.sleep(0.01)
                relay.push_frame(b"b")

            waiter = asyncio.create_task(relay.next_frame())
            pusher = asyncio.create_task(_push_later())
            second = await waiter
            await pusher
            return first, second

        assert asyncio.run(run()) == (b"a", b"b")


class TestVideoRelayRepository:
    def test_get_or_create_retorna_la_misma_instancia(self):
        repo = VideoRelayRepository()

        first = repo.get_or_create("robot-1")
        second = repo.get_or_create("robot-1")

        assert first is second

    def test_robots_distintos_tienen_relays_independientes(self):
        repo = VideoRelayRepository()

        relay_a = repo.get_or_create("robot-a")
        relay_b = repo.get_or_create("robot-b")

        assert relay_a is not relay_b

    def test_discard_remueve_el_relay(self):
        repo = VideoRelayRepository()
        first = repo.get_or_create("robot-1")

        repo.discard("robot-1")
        second = repo.get_or_create("robot-1")

        assert first is not second

    def test_discard_sobre_robot_inexistente_es_noop(self):
        repo = VideoRelayRepository()
        repo.discard("no-existe")  # no debe lanzar
