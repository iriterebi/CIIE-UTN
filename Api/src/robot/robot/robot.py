from uuid import UUID as PythonUUID
from sqlmodel import Field, SQLModel
from pydantic import BaseModel
from sqlalchemy import text


class Robot(SQLModel, table=True):
    __tablename__ = "robots"

    id: PythonUUID | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()"), "nullable": False},
    )

    # This is a string to match VARCHAR(255) in the DB.
    # It's also marked as unique=True to match the DB constraint.
    external_identifier: str = Field(index=True, unique=True)

    name: str

    description: str | None = Field(default=None)

    psw: str

    status: str

    user_id: int | None = Field(default=None, foreign_key="usuarios.id")


class RobotInput(BaseModel):
    external_identifier: PythonUUID
    name: str
    description: str | None = None
    psw: str
    status: str = "Init"

class RobotOutput(BaseModel):
    id: PythonUUID
    external_identifier: PythonUUID
    name: str
    description: str | None = None
    status: str
