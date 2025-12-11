# main.py
from __future__ import annotations

from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Query, status, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from models.user import (
    UserCreate,
    UserRead,
    UserUpdate,
)
from models.db import User as DBUser
from database import get_db, engine, Base

from datetime import datetime
from auth.jwt_utils import create_access_token, get_password_hash
from auth.oauth_config import get_google_oauth_flow, exchange_code_for_token, get_user_info
from auth.dependencies import get_current_user
from dotenv import load_dotenv

load_dotenv()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="User Service",
    version="0.1.0",
    description=(
        "Central service for all user information. "
        "Manages user profiles including first name, last name, email, and authentication. "
        "Supports user registration, retrieval, updates, and soft deletion."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cloud Run uses PORT, fallback to FASTAPIPORT for local development
port = int(os.environ.get("PORT", os.environ.get("FASTAPIPORT", 5004)))


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
    db: Session = Depends(get_db),
) -> List[UserRead]:
    q = db.query(DBUser)

    if first_name is not None:
        q = q.filter(DBUser.first_name.ilike(f"%{first_name}%"))
    if last_name is not None:
        q = q.filter(DBUser.last_name.ilike(f"%{last_name}%"))
    if email is not None:
        q = q.filter(DBUser.email.ilike(f"%{email}%"))
    if is_deleted is not None:
        q = q.filter(DBUser.is_deleted == is_deleted)

    users = q.all()
    return [UserRead(**u.to_dict()) for u in users]


@app.get("/users/{user_id}", response_model=UserRead, summary="Get detailed user info")
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    user = db.query(DBUser).filter(DBUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead(**user.to_dict())


@app.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    # Check if email already exists
    existing_user = db.query(DBUser).filter(DBUser.email == body.email, DBUser.is_deleted == False).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    new_user = DBUser(
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        password_hash=body.password_hash,
        is_deleted=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserRead(**new_user.to_dict())


@app.put(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Update user information (requires JWT)",
)
def update_user(user_id: int, body: UserUpdate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> UserRead:
    user = db.query(DBUser).filter(DBUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot update deleted user")

    # Check if email already exists (if email is being updated)
    if body.email is not None and body.email != user.email:
        existing_user = db.query(DBUser).filter(
            DBUser.email == body.email,
            DBUser.is_deleted == False,
            DBUser.user_id != user_id
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")

    # Update only provided fields
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    user.updated_at = datetime.now() # Update updated_at timestamp
    db.commit()
    db.refresh(user)
    return UserRead(**user.to_dict())


@app.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a user (requires JWT)",
)
def delete_user(user_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_deleted:
        raise HTTPException(status_code=400, detail="User already deleted")

    # Soft delete
    user.is_deleted = True
    user.deleted_at = datetime.now()
    user.updated_at = datetime.now()
    db.commit()
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
async def google_callback(code: str, db: Session = Depends(get_db)):
    try:
        token_data = await exchange_code_for_token(code)
        user_info = await get_user_info(token_data["access_token"])

        email = user_info.get("email")
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")

        # Check if user exists in DB
        user = db.query(DBUser).filter(DBUser.email == email, DBUser.is_deleted == False).first()

        if not user:
            # Create new user
            user = DBUser(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password_hash="oauth_google",
                is_deleted=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

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
def login_for_token(email: str, password: str, db: Session = Depends(get_db)):
    # Find user by email
    user = db.query(DBUser).filter(DBUser.email == email, DBUser.is_deleted == False).first()
    
    if user:
        # In a real app, verify password hash here. 
        # For now, we just check if user exists as per previous logic, 
        # or we could check if password matches password_hash if it wasn't just a placeholder.
        # Assuming simple check for now to match previous behavior but using DB.
        
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
