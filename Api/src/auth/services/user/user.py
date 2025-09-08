from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "usuarios"

    id: int | None = Field(default=None, primary_key=True)
    nombrecompleto: str
    email: str
    usr_name: str
    usr_psw: str
    statuss: str
    usr_pronouns: str
    accion: str | None

    @property
    def is_admin(self) -> bool:
        return self.statuss == 'profe'
