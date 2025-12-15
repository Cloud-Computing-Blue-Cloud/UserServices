"""
Database setup for User Service with SQLAlchemy
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

load_dotenv()

# Database Configuration

if os.getenv("env") == "local":
    DB_USER = "dev_user"
    DB_PASSWORD = "password123"
    DB_HOST = "127.0.0.1"
    DB_PORT = "3307"
    DB_NAME = "LookMyShow"

else: 
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "34.9.21.229")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "users")  # Default to 'users' if not set
    print("DB_USER: ", DB_USER)

DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine
engine = create_engine(
    DATABASE_URI,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)

# Create base class for models
Base = declarative_base()
Base.query = db_session.query_property()

def get_db():
    """
    FastAPI dependency to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
