"""
数据库初始化模块
使用 SQLite + SQLModel
"""
from sqlmodel import SQLModel, create_engine, Session
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "admin.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
