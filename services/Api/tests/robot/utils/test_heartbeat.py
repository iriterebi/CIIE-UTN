import asyncio
from unittest.mock import AsyncMock

import pytest

from src.robot.utils.heartbeat import HeartbeatTimeoutError, run_heartbeat_watchdog


class TestRunHeartbeatWatchdog:
    def test_pong_a_tiempo_no_lanza_y_reintenta_pings(self):
        send_ping = AsyncMock()
        pong_received = asyncio.Event()

        async def _auto_pong():
            while True:
                await asyncio.sleep(0.005)
                pong_received.set()

        async def run():
            watchdog = asyncio.create_task(
                run_heartbeat_watchdog(
                    send_ping, pong_received, ping_interval=0.01, pong_timeout=0.05
                )
            )
            answerer = asyncio.create_task(_auto_pong())
            await asyncio.sleep(0.08)
            still_running = not watchdog.done()
            watchdog.cancel()
            answerer.cancel()
            for t in (watchdog, answerer):
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            return still_running

        assert asyncio.run(run()) is True
        assert send_ping.await_count >= 2

    def test_sin_pong_lanza_heartbeat_timeout(self):
        send_ping = AsyncMock()
        pong_received = asyncio.Event()

        async def run():
            with pytest.raises(HeartbeatTimeoutError):
                await run_heartbeat_watchdog(
                    send_ping, pong_received, ping_interval=1.0, pong_timeout=0.02
                )

        asyncio.run(run())
        send_ping.assert_awaited_once()
