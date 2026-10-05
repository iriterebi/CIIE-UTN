import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from controller.strategy.remote import ws_strategy
from controller.strategy.remote.ws_strategy import WsStrategy


class _FakeConnection:
    """Doble de ClientConnection: entrega mensajes de una lista y luego
    se queda "colgada" (simula que no llega nada más, forzando el
    timeout del heartbeat si aplica)."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []
        self.closed = False

    async def recv(self):
        if not self._messages:
            await asyncio.sleep(3600)
        return self._messages.pop(0)

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True


def _make_strategy():
    return WsStrategy(
        server_url="http://api.example/m2m/robot/",
        metadata_file="/tmp/unused-robot-metadata.json",
    )


class TestPingPong:
    def test_ping_se_responde_con_pong_y_no_se_retorna_como_comando(self):
        strategy = _make_strategy()
        strategy._ws = _FakeConnection([
            json.dumps({"type": "ping"}),
            json.dumps({"jsonrpc": "2.0", "method": "move_arm", "params": {}, "id": 1}),
        ])

        result = asyncio.run(strategy.receive())

        assert result["method"] == "move_arm"
        assert json.loads(strategy._ws.sent[0]) == {"type": "pong"}


class TestParseMessage:
    def test_frame_malformado_retorna_none_y_no_levanta(self):
        """Fix 3: un frame que no valida contra `JsonRpcCommand` (falta `method`)
        debe descartarse devolviendo `None`, igual que el JSON mal formado (rama
        hermana dos líneas más abajo). Antes del fix, esta rama construía y
        devolvía una respuesta de error JSON-RPC -- que `receive()` entregaba al
        core como si fuera un comando, y que `local.send()` jamás podía validar
        como `JsonRpcCommand` (no tiene `method`), reventando con
        `ValidationError` fuera de la red de seguridad de `dispatch()`."""
        strategy = _make_strategy()

        result = strategy._parse_message(json.dumps({"jsonrpc": "2.0"}))  # sin 'method'

        assert result is None

    def test_json_mal_formado_retorna_none_y_no_levanta(self):
        strategy = _make_strategy()

        result = strategy._parse_message("esto no es json")

        assert result is None


class TestHeartbeatWatchdog:
    def test_sin_ping_de_la_api_fuerza_reconexion(self, monkeypatch):
        monkeypatch.setattr(ws_strategy, "_HEARTBEAT_TIMEOUT_SECONDS", 0.02)
        strategy = _make_strategy()
        strategy._ws = _FakeConnection([])

        reconnected = _FakeConnection([
            json.dumps({"jsonrpc": "2.0", "method": "ping_ok", "params": {}, "id": 2}),
        ])

        async def _fake_reconnect():
            strategy._ws = reconnected

        strategy._reconnect = AsyncMock(side_effect=_fake_reconnect)

        result = asyncio.run(asyncio.wait_for(strategy.receive(), timeout=2.0))

        assert result["method"] == "ping_ok"
        strategy._reconnect.assert_awaited_once()
