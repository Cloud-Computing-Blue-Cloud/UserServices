# main.py
from __future__ import annotations

from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Query, status, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse

from models.user import (
    UserCreate,
    UserRead,
    UserUpdate,
)

from datetime import datetime
from auth.jwt_utils import create_access_token, get_password_hash
from auth.oauth_config import get_google_oauth_flow, exchange_code_for_token, get_user_info
from auth.dependencies import get_current_user

load_dotenv()

app = FastAPI(
    title="User Service",
    version="0.1.0",
    description=(
        "Central service for all user information. "
        "Manages user profiles including first name, last name, email, and authentication. "
        "Supports user registration, retrieval, updates, and soft deletion."
    ),
)

port = int(os.environ.get("FASTAPIPORT", 5004))

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
    summary="Update user information (requires JWT)",
)
def update_user(user_id: int, body: UserUpdate, current_user: dict = Depends(get_current_user)) -> UserRead:
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
    summary="Soft delete a user (requires JWT)",
)
def delete_user(user_id: int, current_user: dict = Depends(get_current_user)):
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


# ----------------------- AUTH -----------------------
@app.get("/auth/google/login", summary="Initiate Google OAuth2 login")
def google_login():
    flow = get_google_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return {"authorization_url": authorization_url, "state": state}


@app.get("/auth/google/callback", summary="Google OAuth2 callback")
async def google_callback(code: str):
    try:
        token_data = await exchange_code_for_token(code)
        user_info = await get_user_info(token_data["access_token"])

        email = user_info.get("email")
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")

        existing_user = None
        for user in users.values():
            if user.email == email and not user.is_deleted:
                existing_user = user
                break

        if not existing_user:
            global next_user_id
            user = UserRead(
                user_id=next_user_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password_hash="oauth_google",
                is_deleted=False,
                deleted_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            users[next_user_id] = user
            next_user_id += 1
        else:
            user = existing_user

        jwt_token = create_access_token(
            data={
                "sub": str(user.user_id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        )

        return {
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to authenticate: {str(e)}")


@app.post("/auth/token", summary="Get JWT token (for testing)")
def login_for_token(email: str, password: str):
    for user in users.values():
        if user.email == email and not user.is_deleted:
            jwt_token = create_access_token(
                data={
                    "sub": str(user.user_id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }
            )
            return {
                "access_token": jwt_token,
                "token_type": "bearer"
            }
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ------------------------ Root ------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the User Service. See /docs for Swagger UI."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
