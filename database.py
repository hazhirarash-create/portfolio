import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///portfolio.db",
)


def create_db_engine(database_url: str):
    db_engine = create_engine(
        database_url,
        echo=False,
    )

    if db_engine.dialect.name == "sqlite":

        @event.listens_for(db_engine, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection,
            connection_record,
        ):
            cursor = dbapi_connection.cursor()

            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    return db_engine


engine = create_db_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()