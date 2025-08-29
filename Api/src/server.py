from fastapi import FastAPI
from .auth import auth_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth")
