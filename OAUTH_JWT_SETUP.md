# OAuth2/OIDC and JWT Authentication Setup

This document explains how to set up and test OAuth2 login with Google and JWT authentication in the Blue Cloud Cinema Booking System.

## Overview

- **User Service** implements OAuth2/OIDC login with Google
- After successful Google login, the system generates a custom JWT token
- JWT tokens are required for protected endpoints (user update, user delete)
- Booking Service can optionally validate JWT tokens

---

## Prerequisites

### 1. Create Google OAuth2 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services > Credentials**
4. Click **Create Credentials > OAuth 2.0 Client ID**
5. Configure OAuth consent screen if prompted
6. Select **Web application** as application type
7. Add authorized redirect URIs:
   - `http://localhost:8001/auth/google/callback`
8. Copy the **Client ID** and **Client Secret**

---

## Configuration

### User Service Environment Variables

Create a `.env` file in the `UserServices` directory:

```bash
# UserServices/.env

# Google OAuth2 Configuration
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:8001/auth/google/callback

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application Configuration
FASTAPIPORT=8001
```

**IMPORTANT**: Replace the placeholder values with your actual Google OAuth2 credentials.

---

## Installation

### Install Dependencies

```bash
cd UserServices
pip install -r requirements.txt
```

The requirements include:
- `python-jose[cryptography]` - JWT token handling
- `passlib[bcrypt]` - Password hashing
- `google-auth` - Google authentication
- `google-auth-oauthlib` - OAuth2 flow
- `httpx` - Async HTTP client
- `python-dotenv` - Environment variable loading

---

## Running the Service

```bash
cd UserServices
python main.py
```

The service will start on `http://localhost:8001`

Access the API documentation at: `http://localhost:8001/docs`

---

## Testing OAuth2 Login Flow

### Method 1: Using a Browser

1. **Start the User Service**:
   ```bash
   cd UserServices
   python main.py
   ```

2. **Get Google Login URL**:
   ```bash
   curl http://localhost:8001/auth/google/login
   ```

   Response:
   ```json
   {
     "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
     "state": "random-state-string"
   }
   ```

3. **Open the `authorization_url` in your browser**
   - Login with your Google account
   - Grant permissions
   - You'll be redirected to the callback URL

4. **Extract the JWT token from the callback response**
   The callback will return:
   ```json
   {
     "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
     "token_type": "bearer",
     "user": {
       "user_id": 1,
       "email": "user@example.com",
       "first_name": "John",
       "last_name": "Doe"
     }
   }
   ```

5. **Save the `access_token`** - you'll use this for authenticated requests

### Method 2: Testing with Existing User (Simpler)

For testing purposes, you can use the test token endpoint:

1. **Create a test user**:
   ```bash
   curl -X POST http://localhost:8001/users \
     -H "Content-Type: application/json" \
     -d '{
       "first_name": "Test",
       "last_name": "User",
       "email": "test@example.com",
       "password_hash": "hashed_password"
     }'
   ```

2. **Get a JWT token**:
   ```bash
   curl -X POST "http://localhost:8001/auth/token?email=test@example.com&password=anything"
   ```

   Response:
   ```json
   {
     "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
     "token_type": "bearer"
   }
   ```

---

## Using JWT Tokens for Protected Endpoints

### Protected Endpoints

The following endpoints require a valid JWT token:

1. **PUT /users/{user_id}** - Update user information
2. **DELETE /users/{user_id}** - Soft delete a user

### Making Authenticated Requests

Use the JWT token in the Authorization header:

```bash
# Store the token
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Update user (requires JWT)
curl -X PUT http://localhost:8001/users/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "first_name": "Updated",
    "last_name": "Name"
  }'

# Delete user (requires JWT)
curl -X DELETE http://localhost:8001/users/1 \
  -H "Authorization: Bearer $TOKEN"
```

### Testing Without Token (Should Fail)

```bash
# Try to update without token - should return 401 Unauthorized
curl -X PUT http://localhost:8001/users/1 \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Updated"
  }'
```

Expected response:
```json
{
  "detail": "Not authenticated"
}
```

### Testing With Invalid Token (Should Fail)

```bash
# Try with invalid token - should return 401 Unauthorized
curl -X PUT http://localhost:8001/users/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid-token-here" \
  -d '{
    "first_name": "Updated"
  }'
```

Expected response:
```json
{
  "detail": "Invalid authentication credentials"
}
```

---

## API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/auth/google/login` | Initiate Google OAuth2 login | No |
| GET | `/auth/google/callback` | Google OAuth2 callback (with code) | No |
| POST | `/auth/token` | Get JWT token for testing | No |

### User Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/users` | List all users | No |
| GET | `/users/{user_id}` | Get user details | No |
| POST | `/users` | Create new user | No |
| PUT | `/users/{user_id}` | Update user | **Yes (JWT)** |
| DELETE | `/users/{user_id}` | Soft delete user | **Yes (JWT)** |

---

## JWT Token Structure

The JWT tokens contain the following claims:

```json
{
  "sub": "1",                    // User ID (subject)
  "email": "user@example.com",   // User email
  "first_name": "John",          // First name
  "last_name": "Doe",            // Last name
  "exp": 1234567890,             // Expiration time (Unix timestamp)
  "iat": 1234567890              // Issued at (Unix timestamp)
}
```

Tokens expire after 30 minutes (configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).

---

## Complete Test Flow

### Full OAuth2 + JWT Flow

```bash
# 1. Get Google login URL
curl http://localhost:8001/auth/google/login

# 2. Open the authorization_url in browser and complete login
# (You'll be redirected to the callback with the token)

# 3. Use the token from the callback response
TOKEN="<paste-token-here>"

# 4. Create a test user using Google account (automatic on first login)
# The callback already created the user

# 5. Test protected endpoint - Update user
curl -X PUT http://localhost:8001/users/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "first_name": "Updated"
  }'

# 6. Test protected endpoint - Delete user
curl -X DELETE http://localhost:8001/users/1 \
  -H "Authorization: Bearer $TOKEN"

# 7. Verify user was soft-deleted
curl http://localhost:8001/users/1
```

---

## Security Notes

1. **Never commit `.env` files** - They contain secrets
2. **Change `JWT_SECRET_KEY` in production** - Use a strong random key
3. **Use HTTPS in production** - Tokens should only be transmitted over HTTPS
4. **Token expiration** - Tokens expire after 30 minutes by default
5. **Refresh tokens** - Not implemented (add if needed for production)

---

## Troubleshooting

### Issue: "Invalid authentication credentials"

- Check that you're including the token in the Authorization header
- Verify the token hasn't expired (30 minute default)
- Ensure JWT_SECRET_KEY matches between token generation and validation

### Issue: Google OAuth redirect fails

- Verify `GOOGLE_REDIRECT_URI` matches the one in Google Cloud Console
- Check that the redirect URI is added to authorized redirect URIs
- Ensure the callback URL is accessible

### Issue: "Module not found" errors

- Run `pip install -r requirements.txt` in the UserServices directory
- Make sure you're using Python 3.8+

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OAuth2/OIDC Flow                         │
└─────────────────────────────────────────────────────────────┘

1. User → GET /auth/google/login
   ↓
2. User Service → Returns Google authorization URL
   ↓
3. User → Opens URL in browser, logs in with Google
   ↓
4. Google → Redirects to /auth/google/callback?code=...
   ↓
5. User Service → Exchanges code for Google access token
   ↓
6. User Service → Gets user info from Google
   ↓
7. User Service → Creates/finds user in database
   ↓
8. User Service → Generates custom JWT token
   ↓
9. User Service → Returns JWT token to user


┌─────────────────────────────────────────────────────────────┐
│                    JWT Authentication Flow                  │
└─────────────────────────────────────────────────────────────┘

1. User → PUT /users/1 with Authorization: Bearer <token>
   ↓
2. User Service → Extracts token from header
   ↓
3. User Service → Validates token signature and expiration
   ↓
4. User Service → Extracts user info from token payload
   ↓
5. User Service → Processes request
   ↓
6. User Service → Returns response
```

---

## Next Steps

- Add refresh token support for long-lived sessions
- Implement role-based access control (RBAC)
- Add JWT validation to Booking Service endpoints
- Set up Cloud Function deployment for User Service
- Add Pub/Sub integration for event-driven architecture (optional)
