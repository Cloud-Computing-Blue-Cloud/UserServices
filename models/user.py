# CREATE TABLE users (
#     user_id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
#     first_name VARCHAR(100) NOT NULL,
#     last_name VARCHAR(100),
#     email VARCHAR(255) NOT NULL UNIQUE,
#     password_hash VARCHAR(255) NOT NULL,
#     is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
#     deleted_at TIMESTAMP NULL,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
# );

from __future__ import annotations

from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import date, datetime
from pydantic import BaseModel, Field, EmailStr

class UserBase(BaseModel):
    first_name: str = Field(..., max_length=100, description="The user's first name")
    last_name: Optional[str] = Field(None, max_length=100, description="The user's last name")
    email: EmailStr = Field(..., max_length=255, description="The user's email address")
    password_hash: str = Field(..., max_length=255, description="The hashed password of the user")


class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100, description="The user's first name")
    last_name: Optional[str] = Field(None, max_length=100, description="The user's last name")
    email: Optional[EmailStr] = Field(None, max_length=255, description="The user's email address")
    password_hash: Optional[str] = Field(None, max_length=255, description="The hashed password of the user")

class UserRead(UserBase):
    user_id: int = Field(..., description="The unique identifier of the user")
    is_deleted: bool = Field(False, description="Indicates if the user is deleted")
    deleted_at: Optional[datetime] = Field(None, description="Timestamp when the user was deleted")
    created_at: datetime = Field(..., description="Timestamp when the user was created")
    updated_at: datetime = Field(..., description="Timestamp when the user was last updated")