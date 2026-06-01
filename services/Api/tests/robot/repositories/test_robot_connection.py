from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.auth.entities import User
from src.robot.entities import Robot
from src.robot.repositories.robot_connection import (
    RobotConnectionRepository,
    RobotInUseError,
)


def _make_robot():
    r = MagicMock(spec=Robot)
    r.id = uuid4()
    return r


def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid4()
    return u


def _make_source():
    return MagicMock()


@pytest.fixture
def repo():
    return RobotConnectionRepository()


class TestAddRobotConnection:
    def test_registra_y_retorna_robot_connection(self, repo):
        robot = _make_robot()
        source = _make_source()

        conn = repo.addRobotConnection(robot, source)

        assert conn is not None
        assert repo.getRobotConnection(robot) is conn

    def test_robot_duplicado_lanza_value_error(self, repo):
        robot = _make_robot()
        repo.addRobotConnection(robot, _make_source())

        with pytest.raises(ValueError, match="Robot already connected"):
            repo.addRobotConnection(robot, _make_source())


class TestAddUserConnection:
    def test_registra_y_retorna_user_connection(self, repo):
        user = _make_user()
        source = _make_source()

        conn = repo.addUserConnection(user, source)

        assert conn is not None
        assert repo.getUserConnection(user) is conn

    def test_usuario_duplicado_lanza_value_error(self, repo):
        user = _make_user()
        repo.addUserConnection(user, _make_source())

        with pytest.raises(ValueError, match="User already connected"):
            repo.addUserConnection(user, _make_source())


class TestGetters:
    def test_get_robot_connection_inexistente_es_none(self, repo):
        robot = _make_robot()
        assert repo.getRobotConnection(robot) is None

    def test_get_user_connection_inexistente_es_none(self, repo):
        user = _make_user()
        assert repo.getUserConnection(user) is None

    def test_get_robot_acepta_str(self, repo):
        robot = _make_robot()
        conn = repo.addRobotConnection(robot, _make_source())

        assert repo.getRobotConnection(str(robot.id)) is conn


class TestAddUserXRobotConnection:
    def test_arma_el_pipe_con_user_y_robot_existentes(self, repo):
        user = _make_user()
        robot = _make_robot()
        user_conn = repo.addUserConnection(user, _make_source())
        robot_conn = repo.addRobotConnection(robot, _make_source())

        pipe = repo.addUserXRobotConnection(user_conn, robot_conn)

        assert pipe.user is user_conn
        assert pipe.robot is robot_conn

    def test_user_ya_pipeado_lanza_robot_in_use(self, repo):
        user = _make_user()
        robot_a = _make_robot()
        robot_b = _make_robot()
        user_conn = repo.addUserConnection(user, _make_source())
        robot_a_conn = repo.addRobotConnection(robot_a, _make_source())
        robot_b_conn = repo.addRobotConnection(robot_b, _make_source())

        repo.addUserXRobotConnection(user_conn, robot_a_conn)

        with pytest.raises(RobotInUseError):
            repo.addUserXRobotConnection(user_conn, robot_b_conn)

    def test_robot_ya_pipeado_lanza_robot_in_use(self, repo):
        user_a = _make_user()
        user_b = _make_user()
        robot = _make_robot()
        user_a_conn = repo.addUserConnection(user_a, _make_source())
        user_b_conn = repo.addUserConnection(user_b, _make_source())
        robot_conn = repo.addRobotConnection(robot, _make_source())

        repo.addUserXRobotConnection(user_a_conn, robot_conn)

        with pytest.raises(RobotInUseError):
            repo.addUserXRobotConnection(user_b_conn, robot_conn)


class TestDiscardConnections:
    def test_discard_user_inexistente_lanza(self, repo):
        with pytest.raises(ValueError, match="User not found"):
            repo.discardUserConnection(str(uuid4()))

    def test_discard_robot_inexistente_lanza(self, repo):
        with pytest.raises(ValueError, match="Robot not found"):
            repo.discardRobotConnection(str(uuid4()))

    def test_discard_user_remueve_del_repo(self, repo):
        user = _make_user()
        repo.addUserConnection(user, _make_source())

        repo.discardUserConnection(user)

        assert repo.getUserConnection(user) is None

    def test_discard_robot_remueve_del_repo(self, repo):
        robot = _make_robot()
        repo.addRobotConnection(robot, _make_source())

        repo.discardRobotConnection(robot)

        assert repo.getRobotConnection(robot) is None

    def test_discard_user_con_pipe_activo_y_disconnect_false_lanza(self, repo):
        user = _make_user()
        robot = _make_robot()
        user_conn = repo.addUserConnection(user, _make_source())
        robot_conn = repo.addRobotConnection(robot, _make_source())
        pipe = repo.addUserXRobotConnection(user_conn, robot_conn)
        # Simular pipe conectado: agregar un task fake para que `pipe.connected` sea True
        pipe._tasks.append(MagicMock())

        with pytest.raises(RobotInUseError):
            repo.discardUserConnection(user, discardPipeddConnections=False)

    def test_discard_user_con_pipe_y_disconnect_true_limpia_cascada(self, repo):
        user = _make_user()
        robot = _make_robot()
        user_conn = repo.addUserConnection(user, _make_source())
        robot_conn = repo.addRobotConnection(robot, _make_source())
        pipe = repo.addUserXRobotConnection(user_conn, robot_conn)
        # Pipe activo con un task que se va a cancelar y un disconnectable noop
        fake_task = MagicMock()
        pipe._tasks.append(fake_task)

        repo.discardUserConnection(user, discardPipeddConnections=True)

        # El user fue removido
        assert repo.getUserConnection(user) is None
        # El pipe fue desconectado (disconnect cancela los tasks)
        fake_task.cancel.assert_called_once()
        # El robot persiste — la convención es que la conexión del robot
        # sobrevive al usuario
        assert repo.getRobotConnection(robot) is robot_conn


class TestGetUserXRobotConnection:
    def test_busca_por_user(self, repo):
        user = _make_user()
        robot = _make_robot()
        user_conn = repo.addUserConnection(user, _make_source())
        robot_conn = repo.addRobotConnection(robot, _make_source())
        pipe = repo.addUserXRobotConnection(user_conn, robot_conn)

        found = repo.getUserXRobotConnection(user=user)

        assert found is pipe

    def test_busca_por_robot(self, repo):
        user = _make_user()
        robot = _make_robot()
        user_conn = repo.addUserConnection(user, _make_source())
        robot_conn = repo.addRobotConnection(robot, _make_source())
        pipe = repo.addUserXRobotConnection(user_conn, robot_conn)

        found = repo.getUserXRobotConnection(robot=robot)

        assert found is pipe

    def test_sin_pipe_retorna_none(self, repo):
        user = _make_user()
        repo.addUserConnection(user, _make_source())

        assert repo.getUserXRobotConnection(user=user) is None
