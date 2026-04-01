from typing import Annotated
from fastapi import Depends
from sqlmodel import Session, create_engine
from ..config import POSTGRES_PASSWORD, POSTGRES_USER, POSTGRES_DB, POSTGRES_URL

__db_url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_URL}/{POSTGRES_DB}"

__engine = create_engine(
    __db_url,
    echo=True
)

def get_db_session():
    with Session(__engine) as session:
        yield session

DbSessionDep = Annotated[Session, Depends(get_db_session)]
