from fastapi import FastAPI
from .auth import auth_router
from .robot import robot_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth")
app.include_router(robot_router, prefix="/robot")
