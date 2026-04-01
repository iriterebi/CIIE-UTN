from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth import auth_router
from .config import ROSBRIDGE_URL
from .robot import m2m_robot_router, admin_robot_router, user_robot_router
from .robot.services.rosbridge_client import RosBridgeClient, set_rosbridge_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = RosBridgeClient(ROSBRIDGE_URL)
    await client.connect()
    set_rosbridge_client(client)
    yield
    await client.disconnect()


app = FastAPI(lifespan=lifespan)

# Rutas de autenticación: /auth
app.include_router(auth_router, prefix="/auth", tags=["publicas"])

# Rutas de usuario administrador: /admin
app.include_router(admin_robot_router, prefix="/admin/robot")

# Rutas de uso interno del sistema: /m2m
app.include_router(m2m_robot_router, prefix="/m2m/robot", tags=["internal"])

# Rutas del usuario común: /user
app.include_router(user_robot_router, prefix="/user/robot", tags=["internal"])
