import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.websockets import WebSocketState

from src.robot.adapters import UserStreamSource


def _make_ws(application_state=WebSocketState.CONNECTING):
    ws = MagicMock()
    ws.application_state = application_state
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestAccept:
    def test_acepta_si_no_estaba_conectado(self):
        ws = _make_ws(WebSocketState.CONNECTING)
        source = UserStreamSource(ws)

        asyncio.run(source.accept())

        ws.accept.assert_awaited_once_with()

    def test_no_acepta_si_ya_estaba_conectado(self):
        ws = _make_ws(WebSocketState.CONNECTED)
        source = UserStreamSource(ws)

        asyncio.run(source.accept())

        ws.accept.assert_not_awaited()


class TestDisconnect:
    def test_cierra_el_websocket(self):
        ws = _make_ws()
        source = UserStreamSource(ws)

        asyncio.run(source.disconnect())

        ws.close.assert_awaited_once_with()


class TestReceiveData:
    def test_parsea_json_rpc_valido(self):
        ws = _make_ws()
        ws.receive_text.return_value = '{"method": "move_arm"}'
        source = UserStreamSource(ws)

        result = asyncio.run(source.receive_data())

        assert result == {"method": "move_arm"}
        ws.send_json.assert_not_awaited()

    def test_payload_invalido_no_mata_la_conexion(self):
        # Primer mensaje: validation error (falta `method`).
        # Segundo mensaje: payload válido → debe devolverlo.
        ws = _make_ws()
        ws.receive_text.side_effect = [
            '{"otra_cosa": 1}',
            '{"method": "move_arm"}',
        ]
        source = UserStreamSource(ws)

        result = asyncio.run(source.receive_data())

        assert result == {"method": "move_arm"}
        # Se mandó un error al cliente por el primer mensaje
        assert ws.send_json.await_count == 1
        err = ws.send_json.await_args_list[0].args[0]
        assert err["status"] == "error"
        assert "Invalid payload" in err["message"]

    def test_json_invalido_no_mata_la_conexion(self):
        ws = _make_ws()
        ws.receive_text.side_effect = [
            'esto no es json',
            '{"method": "move_arm"}',
        ]
        source = UserStreamSource(ws)

        result = asyncio.run(source.receive_data())

        assert result == {"method": "move_arm"}
        assert ws.send_json.await_count == 1
        err = ws.send_json.await_args_list[0].args[0]
        assert err["status"] == "error"
        assert "Invalid JSON" in err["message"]


class TestSendData:
    def test_delega_en_websocket_send_json(self):
        ws = _make_ws()
        source = UserStreamSource(ws)

        asyncio.run(source.send_data({"hello": "world"}))

        ws.send_json.assert_awaited_once_with({"hello": "world"})


class TestReceiveDataPong:
    def test_pong_no_se_retorna_como_comando_y_marca_el_evento(self):
        ws = _make_ws()
        ws.receive_text.side_effect = [
            '{"type": "pong"}',
            '{"method": "move_arm"}',
        ]
        pong_received = asyncio.Event()
        source = UserStreamSource(ws, pong_received=pong_received)

        result = asyncio.run(source.receive_data())

        assert result == {"method": "move_arm"}
        assert pong_received.is_set()
        ws.send_json.assert_not_awaited()


class TestSendControl:
    def test_send_control_usa_send_json(self):
        ws = _make_ws()
        source = UserStreamSource(ws)

        asyncio.run(source.send_control({"type": "ping"}))

        ws.send_json.assert_awaited_once_with({"type": "ping"})
