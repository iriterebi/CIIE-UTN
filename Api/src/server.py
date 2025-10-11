from fastapi import FastAPI
from .auth import auth_router
from .robot import m2m_robot_router, admin_robot_router, user_robot_router

app = FastAPI()

# Rutas de autenticación: /auth
app.include_router(auth_router, prefix="/auth", tags=["publicas"])

# Rutas de usuario administrador: /admin
app.include_router(admin_robot_router, prefix="/admin/robot")

# Rutas de uso interno del sistema: /m2m
app.include_router(m2m_robot_router, prefix="/m2m/robot", tags=["internal"])

# Rutas del usuario común: /user
app.include_router(user_robot_router, prefix="/user/robot", tags=["internal"])
