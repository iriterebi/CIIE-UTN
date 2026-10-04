import asyncio
from unittest.mock import AsyncMock

import pytest

from ..camera import video_ws_client
from ..camera.video_ws_client import VideoWsClient, derive_video_ws_url
from ..server.server_service import ServerServices


def _make_client():
    server_service = ServerServices(
        base_url="http://api.example/m2m/robot/",
        metadata_file="/tmp/unused-robot-metadata.json",
    )
    return VideoWsClient(server_service=server_service, ws_url="ws://api.example/m2m/robot/video")


class _FakeConnection:
    def __init__(self):
        self.sent: list[bytes] = []

    async def send(self, data):
        self.sent.append(data)


class TestDeriveVideoWsUrl:
    @pytest.mark.parametrize("server_url,expected", [
        ("http://api.example/m2m/robot/", "ws://api.example/m2m/robot/video"),
        ("https://api.example/m2m/robot/", "wss://api.example/m2m/robot/video"),
        ("http://api.example/m2m/robot", "ws://api.example/m2m/robot/video"),
    ])
    def test_deriva_ws_url_desde_http(self, server_url, expected):
        assert derive_video_ws_url(server_url) == expected


class TestRunSendsFrames:
    def test_run_envia_frames_de_next_frame(self):
        client = _make_client()
        client._connect = AsyncMock()
        fake_ws = _FakeConnection()
        client._ws = fake_ws

        frames = [b"frame1", b"frame2"]

        async def next_frame():
            if frames:
                return frames.pop(0)
            await asyncio.sleep(3600)

        async def run():
            task = asyncio.create_task(client.run(next_frame))
            await asyncio.sleep(0.01)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run())
        assert fake_ws.sent == [b"frame1", b"frame2"]
        client._connect.assert_awaited_once()


class TestReconnect:
    def test_run_reconecta_tras_conexion_perdida(self, monkeypatch):
        monkeypatch.setattr(video_ws_client, "_MIN_RECONNECT_DELAY", 0.01)
        monkeypatch.setattr(video_ws_client, "_MAX_RECONNECT_DELAY", 0.01)
        client = _make_client()
        connect_calls: list[int] = []

        class _DyingThenAliveConnection:
            def __init__(self, fail: bool):
                self.fail = fail
                self.sent: list[bytes] = []

            async def send(self, data):
                if self.fail:
                    raise ConnectionError("conexión perdida")
                self.sent.append(data)

        async def fake_connect():
            connect_calls.append(1)
            client._ws = _DyingThenAliveConnection(fail=(len(connect_calls) == 1))

        client._connect = fake_connect

        frames = [b"a", b"b"]

        async def next_frame():
            if frames:
                return frames.pop(0)
            await asyncio.sleep(3600)

        async def run():
            task = asyncio.create_task(client.run(next_frame))
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run())
        assert len(connect_calls) == 2
        assert client._ws.sent == [b"b"]
