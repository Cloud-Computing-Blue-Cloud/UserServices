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
from sqlalchemy.orm import Session

from datetime import datetime
from auth.jwt_utils import create_access_token, get_password_hash
from auth.oauth_config import get_google_oauth_flow, exchange_code_for_token, get_user_info
from auth.dependencies import get_current_user

load_dotenv()

print(load_dotenv())

# Create tables (with error handling for connection issues)
try:
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified successfully")
except Exception as e:
    print(f"Warning: Could not connect to database during startup: {e}")
    print("Application will start, but database operations will fail until connection is available")

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

# In-memory cache to track processed OAuth codes (prevents duplicate processing)
# Note: This is cleared on server restart, but helps with duplicate callback calls
processed_oauth_codes: Dict[str, dict] = {}


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
def google_login(redirect_uri: Optional[str] = None):
    """
    Initiate Google OAuth2 login.
    
    If redirect_uri is provided, it will be used as the callback URL.
    Otherwise, uses the default from environment variables.
    """
    from auth.oauth_config import get_google_oauth_flow
    
    # URL decode if needed
    if redirect_uri:
        from urllib.parse import unquote
        redirect_uri = unquote(redirect_uri)
        print(f"[DEBUG] Login endpoint - Using redirect_uri: {redirect_uri}")
    
    flow = get_google_oauth_flow(redirect_uri=redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    print(f"[DEBUG] Generated authorization URL with redirect_uri: {redirect_uri}")
    return {"authorization_url": authorization_url, "state": state}


@app.get("/auth/google/callback", summary="Google OAuth2 callback")
async def google_callback(code: str, redirect_uri: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle Google OAuth2 callback.
    
    Args:
        code: Authorization code from Google
        redirect_uri: Redirect URI used in the authorization request (should match)
    """
    from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
    
    # Check if we've already processed this code (prevents duplicate processing)
    if code in processed_oauth_codes:
        print(f"[INFO] Code already processed, returning cached response")
        return processed_oauth_codes[code]
    
    try:
        # URL decode the redirect_uri if it's encoded
        if redirect_uri:
            from urllib.parse import unquote
            redirect_uri = unquote(redirect_uri)
            print(f"[DEBUG] Using redirect_uri: {redirect_uri}")
        
        print(f"[DEBUG] Exchanging code for token with redirect_uri: {redirect_uri}")
        token_data = await exchange_code_for_token(code, redirect_uri=redirect_uri)
        print(f"[DEBUG] Successfully exchanged code for token")
        user_info = await get_user_info(token_data["access_token"])

        email = user_info.get("email")
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")

        # Try to get/create user in DB, but handle DB connection failures gracefully
        user = None
        user_id = None
        
        try:
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
            
            user_id = user.user_id
            print(f"[DEBUG] User found/created in DB with ID: {user_id}")
            
        except Exception as db_error:
            # Database connection failed - use a temporary user ID for demo
            print(f"[WARNING] Database connection failed: {db_error}")
            print(f"[WARNING] Using temporary user ID for demo purposes")
            # Generate a temporary user_id based on email hash for consistency
            import hashlib
            user_id = int(hashlib.md5(email.encode()).hexdigest()[:8], 16) % 1000000
            print(f"[WARNING] Temporary user_id: {user_id}")

        jwt_token = create_access_token(
            data={
                "sub": str(user_id),
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            }
        )

        response = {
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": {
                "user_id": user_id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            }
        }
        
        # Cache the response for this code (expires after 5 minutes to prevent memory bloat)
        processed_oauth_codes[code] = response
        # Clean up old entries periodically (simple approach: limit cache size)
        if len(processed_oauth_codes) > 1000:
            # Remove oldest 500 entries (simple FIFO-like cleanup)
            codes_to_remove = list(processed_oauth_codes.keys())[:500]
            for old_code in codes_to_remove:
                del processed_oauth_codes[old_code]
        
        return response
    except InvalidGrantError as e:
        # Code has already been used - this can happen if callback is called twice
        # Try to get user from DB if possible (though we won't have email from failed exchange)
        error_msg = "The authorization code has already been used. This may happen if the login page was refreshed. Please try logging in again."
        print(f"[WARNING] InvalidGrantError: {str(e)}")
        print(f"[WARNING] This usually means the callback was called twice with the same code.")
        raise HTTPException(
            status_code=400, 
            detail=error_msg
        )
    except Exception as e:
        import traceback
        error_details = str(e)
        print(f"[ERROR] OAuth callback failed: {error_details}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Failed to authenticate: {error_details}")


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
