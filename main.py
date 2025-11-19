# main.py
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, status

from models.user import (
    UserCreate,
    UserRead,
    UserUpdate,
)

from datetime import datetime

app = FastAPI(
    title="User Service",
    version="0.1.0",
    description=(
        "Central service for all user information. "
        "Manages user profiles including first name, last name, email, and authentication. "
        "Supports user registration, retrieval, updates, and soft deletion."
    ),
)

# In-memory store (same pattern as your Books & Authors code)
users: Dict[int, UserRead] = {}
next_user_id: int = 1


# ----------------------- USERS -----------------------
@app.get("/users", response_model=List[UserRead], summary="List all users")
def list_users(
    first_name: Optional[str] = Query(
        None, description="Case-insensitive substring match on first name"
    ),
    last_name: Optional[str] = Query(
        None, description="Case-insensitive substring match on last name"
    ),
    email: Optional[str] = Query(
        None, description="Case-insensitive substring match on email"
    ),
    is_deleted: Optional[bool] = Query(None, description="Filter by deletion status"),
) -> List[UserRead]:
    vals = list(users.values())

    if first_name is not None:
        fn = first_name.lower()
        vals = [u for u in vals if fn in u.first_name.lower()]
    if last_name is not None:
        ln = last_name.lower()
        vals = [u for u in vals if u.last_name and ln in u.last_name.lower()]
    if email is not None:
        e = email.lower()
        vals = [u for u in vals if e in u.email.lower()]
    if is_deleted is not None:
        vals = [u for u in vals if u.is_deleted == is_deleted]

    return vals


@app.get("/users/{user_id}", response_model=UserRead, summary="Get detailed user info")
def get_user(user_id: int) -> UserRead:
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")
    return users[user_id]


@app.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def create_user(body: UserCreate) -> UserRead:
    global next_user_id

    # Check if email already exists
    for user in users.values():
        if user.email == body.email and not user.is_deleted:
            raise HTTPException(status_code=400, detail="Email already exists")

    user = UserRead(
        user_id=next_user_id,
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        password_hash=body.password_hash,
        is_deleted=False,
        deleted_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    users[next_user_id] = user
    next_user_id += 1
    return user


@app.put(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Update user information",
)
def update_user(user_id: int, body: UserUpdate) -> UserRead:
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")

    user = users[user_id]

    if user.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot update deleted user")

    # Check if email already exists (if email is being updated)
    if body.email is not None and body.email != user.email:
        for u in users.values():
            if u.email == body.email and not u.is_deleted and u.user_id != user_id:
                raise HTTPException(status_code=400, detail="Email already exists")

    # Update only provided fields
    update_data = body.model_dump(exclude_unset=True)
    updated_user = user.model_copy(update={**update_data, "updated_at": datetime.now()})
    users[user_id] = updated_user
    return updated_user


@app.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a user",
)
def delete_user(user_id: int):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")

    user = users[user_id]

    if user.is_deleted:
        raise HTTPException(status_code=400, detail="User already deleted")

    # Soft delete
    updated_user = user.model_copy(
        update={
            "is_deleted": True,
            "deleted_at": datetime.now(),
            "updated_at": datetime.now(),
        }
    )
    users[user_id] = updated_user
    return None


# ------------------------ Root ------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the User Service. See /docs for Swagger UI."}
