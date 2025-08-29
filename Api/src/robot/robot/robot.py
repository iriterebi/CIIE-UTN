from datetime import datetime
from sqlmodel import Field, SQLModel, Column, Integer, String, DateTime
from sqlalchemy import ForeignKey


class Robot(SQLModel, table=True):
    __tablename__ = "robots"

    id: int | None = Field(sa_column=Column("r_id", Integer, primary_key=True), default=None)

    name: str = Field(sa_column=Column("r_name", String))

    description: str | None = Field(sa_column=Column("r_description", String), default=None)

    status: str = Field(sa_column=Column("r_status", String))

    timestamp: datetime = Field(sa_column=Column("r_timestamp", DateTime(timezone=True), nullable=False))

    # user_id: int | None = Field(default=None, sa_column=Column("r_user_id", Integer, ForeignKey("usuarios.id")))
