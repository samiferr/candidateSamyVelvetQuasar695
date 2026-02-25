from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

#DATABASE_URL = "sqlite+pysqlite:///:memory:"
DATABASE_URL = "sqlite+pysqlite:///example_1.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()