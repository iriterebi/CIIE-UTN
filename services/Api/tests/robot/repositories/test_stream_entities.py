import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.robot.repositories.stream_entities import (
    RobotConnection,
    RobotSideClosed,
    UserConnection,
    UsersXRobotMapType,
)


class _FakeSource:
    """Doble de StreamSource controlable a mano: permite simular una
    caída física llamando a `die()`, sin depender de ProxyStreamSource."""

    def __init__(self):
        self.disconnected = False
        self.sent = []
        self._recv_queue = asyncio.Queue()
        self._die_event = asyncio.Event()

    async def accept(self):
        return None

    async def disconnect(self):
        self.disconnected = True

    async def receive_data(self):
        get_task = asyncio.ensure_future(self._recv_queue.get())
        die_task = asyncio.ensure_future(self._die_event.wait())
        done, pending = await asyncio.wait(
            {get_task, die_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        if die_task in done:
            raise RuntimeError("conexión física perdida")
        return get_task.result()

    async def send_data(self, data):
        if self._die_event.is_set():
            # Simula el comportamiento real de starlette: escribir a un
            # WebSocket físico ya cerrado (que es justo lo que pasa con el
            # WS del robot en m2m.py, cerrado en su `finally` antes de que
            # el pipe se entere de la caída) lanza RuntimeError en vez de
            # encolar el mensaje.
            raise RuntimeError('Cannot call "send" once a close message has been sent.')
        self.sent.append(data)

    def die(self):
        self._die_event.set()


def _make_robot_conn():
    robot = type("FakeRobot", (), {})()
    robot.id = uuid4()
    return RobotConnection(_FakeSource(), robot), robot


def _make_user_conn():
    user = type("FakeUser", (), {})()
    user.id = uuid4()
    return UserConnection(_FakeSource(), user)


class TestRobotReconnectFlow:
    def test_robot_reconecta_dentro_del_timeout_y_el_pipe_sigue(self):
        user_conn = _make_user_conn()
        robot_conn, robot = _make_robot_conn()
        new_robot_conn, _ = _make_robot_conn()
        wait_for_robot_reconnect = AsyncMock(return_value=new_robot_conn)
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(
                    wait_for_robot_reconnect=wait_for_robot_reconnect,
                    reconnect_timeout=5.0,
                )
            )
            await asyncio.sleep(0)
            robot_conn.ws.die()
            await asyncio.sleep(0.01)

            assert pipe.robot is new_robot_conn
            assert {
                "status": "robot_disconnected",
                "message": "robot desconectado, reconectando...",
            } in user_conn.ws.sent
            assert {"status": "robot_reconnected"} in user_conn.ws.sent
            # el usuario nunca se desconectó durante la espera
            assert user_conn.ws.disconnected is False

            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, BaseExceptionGroup):
                pass

        asyncio.run(run())
        wait_for_robot_reconnect.assert_awaited_once_with(str(robot.id), 5.0)

    def test_robot_no_reconecta_a_tiempo_cierra_todo_el_pipe(self):
        user_conn = _make_user_conn()
        robot_conn, robot = _make_robot_conn()
        wait_for_robot_reconnect = AsyncMock(return_value=None)
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(
                    wait_for_robot_reconnect=wait_for_robot_reconnect,
                    reconnect_timeout=0.01,
                )
            )
            await asyncio.sleep(0)
            robot_conn.ws.die()
            with pytest.raises(BaseExceptionGroup) as exc_info:
                await task
            return exc_info.value

        eg = asyncio.run(run())
        assert any(isinstance(e, RobotSideClosed) for e in eg.exceptions)
        assert {
            "status": "robot_unavailable",
            "message": "el robot no reconectó a tiempo",
        } in user_conn.ws.sent

    def test_disconnect_cancela_ambos_lados_sin_esperar_reconexion(self):
        user_conn = _make_user_conn()
        robot_conn, _ = _make_robot_conn()
        wait_for_robot_reconnect = AsyncMock()
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(wait_for_robot_reconnect=wait_for_robot_reconnect)
            )
            await asyncio.sleep(0)
            assert pipe.connected is True

            # Un solo `sleep(0)` solo alcanza para que el TaskGroup cree las
            # tareas hijas (user/robot); todavía no tuvieron su primer turno
            # para llegar a `ws.accept()`/`ws.receive_data()`. Un segundo
            # `sleep(0)` se lo da, para que `disconnect()` cancele conexiones
            # realmente en curso y no tareas que nunca llegaron a arrancar
            # (lo cual dejaría sin ejecutar el `finally`/`_on_disconnect`).
            await asyncio.sleep(0)

            pipe.disconnect()

            with pytest.raises((asyncio.CancelledError, BaseExceptionGroup)):
                await task

            assert user_conn.ws.disconnected is True

        asyncio.run(run())
        wait_for_robot_reconnect.assert_not_called()

    def test_disconnect_cancela_tambien_tareas_extra_registradas(self):
        user_conn = _make_user_conn()
        robot_conn, _ = _make_robot_conn()
        wait_for_robot_reconnect = AsyncMock()
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(wait_for_robot_reconnect=wait_for_robot_reconnect)
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            async def _forever():
                while True:
                    await asyncio.sleep(3600)

            extra_task = asyncio.create_task(_forever())
            pipe.register_extra_task(extra_task)

            pipe.disconnect()

            with pytest.raises((asyncio.CancelledError, BaseExceptionGroup)):
                await task

            assert extra_task.cancelled() or extra_task.done()

        asyncio.run(run())

    def test_comando_de_usuario_durante_espera_de_reconexion_no_tumba_la_sesion(self):
        """Reproduce el bug del finding 1: mientras el pipe espera que el
        robot reconecte, el listener usuario→robot todavía apuntaba al
        `RobotConnection` viejo (con el WS físico ya cerrado). Un comando
        del usuario en esa ventana debía, con el bug, propagar la
        excepción del `send` fallido y tumbar TODO el pipe (incluida la
        espera de reconexión en curso). Con el fix, el usuario recibe un
        error JSON-RPC inmediato y el pipe sigue esperando, sin tocar el
        canal robot muerto."""
        user_conn = _make_user_conn()
        robot_conn, robot = _make_robot_conn()
        new_robot_conn, _ = _make_robot_conn()
        reconnect_ready = asyncio.Event()

        async def _wait_for_robot_reconnect_impl(robot_id, timeout):
            await reconnect_ready.wait()
            return new_robot_conn

        wait_for_robot_reconnect = AsyncMock(side_effect=_wait_for_robot_reconnect_impl)
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(
                    wait_for_robot_reconnect=wait_for_robot_reconnect,
                    reconnect_timeout=5.0,
                )
            )
            await asyncio.sleep(0)

            # El robot muere; en la implementación real, para cuando esto
            # pasa, m2m.py ya cerró el WS físico del robot (su `finally`
            # corre `websocket.close()` antes de `mark_disconnected`).
            robot_conn.ws.die()
            await asyncio.sleep(0.01)

            assert {
                "status": "robot_disconnected",
                "message": "robot desconectado, reconectando...",
            } in user_conn.ws.sent

            # El pipe sigue esperando la reconexión: todavía no volvió a
            # llamar a `robot_conn.connect()` (viejo), ni terminó.
            assert not task.done()

            # El usuario manda un comando MIENTRAS se espera la reconexión.
            # Con el bug, esto intentaría reenviarse al `RobotConnection`
            # viejo (WS ya cerrado) y tumbaría el pipe entero.
            user_conn.ws._recv_queue.put_nowait({"method": "mover", "args": []})
            await asyncio.sleep(0.01)

            # El pipe sigue vivo y esperando: la excepción NO se propagó.
            assert not task.done()
            assert pipe.connected is True
            assert user_conn.ws.disconnected is False

            # El usuario recibió un error inmediato en lugar de que se
            # reenviara silenciosamente (o de que la sesión muriera).
            error_responses = [
                m for m in user_conn.ws.sent
                if isinstance(m, dict) and "error" in m
            ]
            assert len(error_responses) == 1
            assert error_responses[0]["error"]["message"] == "robot no disponible"

            # El comando NUNCA llegó al robot viejo (que está muerto).
            assert {"method": "mover", "args": []} not in robot_conn.ws.sent

            # Ahora el robot reconecta a tiempo: la operación normal debe
            # resumir.
            reconnect_ready.set()
            await asyncio.sleep(0.01)

            assert pipe.robot is new_robot_conn
            assert {"status": "robot_reconnected"} in user_conn.ws.sent

            # Un nuevo comando del usuario ahora sí se reenvía al robot
            # (nuevo, vivo) en vez de ser rechazado.
            user_conn.ws._recv_queue.put_nowait({"method": "girar", "args": []})
            await asyncio.sleep(0.01)

            assert {"method": "girar", "args": []} in new_robot_conn.ws.sent

            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, BaseExceptionGroup):
                pass

        asyncio.run(run())
