# User Service - FastAPI

A microservice for managing user accounts, authentication, and profiles with Google OAuth integration, built with **FastAPI**.

## 🚀 Features

- ✅ User registration and profile management
- ✅ Google OAuth 2.0 authentication
- ✅ JWT token-based authentication
- ✅ User profile CRUD operations
- ✅ Soft deletion of users
- ✅ **Interactive API documentation** (Swagger UI)
- ✅ **Automatic request validation** (Pydantic)
- ✅ **Google Cloud SQL integration** (MySQL)
- ✅ **Cloud Run deployment ready**

## 📋 Project Structure

```
UserServices/
├── main.py                    # FastAPI application
├── database.py                # SQLAlchemy database setup
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker configuration for Cloud Run
├── models/
│   ├── user.py               # Pydantic models for API
│   └── db.py                 # SQLAlchemy database models
├── auth/
│   ├── oauth_config.py       # Google OAuth configuration
│   ├── jwt_utils.py          # JWT token generation/validation
│   └── dependencies.py       # Auth dependencies (get_current_user)
└── openapi.yaml              # OpenAPI specification
```

## 🛠️ Installation

### Quick Start

1. **Create virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**
```bash
# Create .env file
cp .env.example .env  # or create manually

# Edit .env with your configuration:
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=34.9.21.229
DB_PORT=3306
DB_NAME=users
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5004/auth/google/callback
```

4. **Run the service:**
```bash
# Option 1: Direct
python main.py

# Option 2: With uvicorn
uvicorn main:app --reload --port 5004
```

The service will start on `http://localhost:5004`

## 📚 Interactive API Documentation

**Visit: http://localhost:5004/docs**

FastAPI provides automatic, interactive API documentation where you can:
- 📖 View all endpoints and schemas
- 🧪 Test APIs directly in your browser
- 📋 See request/response examples
- ✅ Validate data in real-time

Alternative documentation: http://localhost:5004/redoc

## 🔌 API Endpoints

All endpoints are documented interactively at `/docs`. Quick reference:

### Users

```bash
# List all users (with optional filters)
GET /users?first_name=John&email=example@email.com

# Get user by ID
GET /users/{user_id}

# Register new user (201 Created)
POST /users
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "password_hash": "hashed_password"
}

# Update user (requires JWT)
PUT /users/{user_id}
Authorization: Bearer <jwt_token>
{
  "first_name": "Jane",
  "email": "jane.doe@example.com"
}

# Soft delete user (requires JWT)
DELETE /users/{user_id}
Authorization: Bearer <jwt_token>
```

### Authentication

```bash
# Initiate Google OAuth login
GET /auth/google/login?redirect_uri=http://localhost:3000/login
# Returns: {"authorization_url": "...", "state": "..."}

# OAuth callback (handled by Google redirect)
GET /auth/google/callback?code=...&redirect_uri=...

# Get JWT token (for testing)
POST /auth/token?email=user@example.com&password=password
# Returns: {"access_token": "...", "token_type": "bearer"}
```

### Health & Info

```bash
# Root endpoint
GET /
```

## 🗄️ Database

Uses **Google Cloud SQL (MySQL)** with the following table:

- **users** - User profiles with authentication info
  - `user_id` (primary key)
  - `first_name`, `last_name`, `email`
  - `password_hash`
  - `is_deleted` (soft deletion flag)
  - `created_at`, `updated_at`, `deleted_at`

## ⚙️ Configuration

### Environment Variables

```bash
# Database
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=34.9.21.229
DB_PORT=3306
DB_NAME=users

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://your-frontend-url/login

# Application
env=production  # or "local" for local development
PORT=5004       # Port for Cloud Run (defaults to 5004 locally)
```

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 Client ID
3. Add authorized redirect URIs:
   - Local: `http://localhost:5004/auth/google/callback`
   - Production: `https://your-frontend-url/login`
4. Copy `Client ID` and `Client Secret` to `.env`

## 🔐 Authentication Flow

### Google OAuth Flow

1. **Frontend**: Call `GET /auth/google/login?redirect_uri=...`
2. **Service**: Returns `authorization_url`
3. **Frontend**: Redirect user to `authorization_url`
4. **Google**: User authenticates, redirects to `redirect_uri?code=...`
5. **Frontend**: Extract `code`, call `GET /auth/google/callback?code=...`
6. **Service**: Exchanges code for user info, creates/updates user, returns JWT
7. **Frontend**: Store JWT token for authenticated requests

### JWT Token Usage

Include JWT token in protected endpoints:

```bash
Authorization: Bearer <jwt_token>
```

Protected endpoints:
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user

## 🧪 Testing

### Using Swagger UI (Easiest!)
1. Go to http://localhost:5004/docs
2. Click any endpoint
3. Click "Try it out"
4. Fill in parameters
5. Click "Execute"

### Using cURL

```bash
# Health check
curl http://localhost:5004/

# Create user (201 Created)
curl -i -X POST http://localhost:5004/users \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "password_hash": "hashed_password"
  }'

# Get user
curl http://localhost:5004/users/1

# Update user (requires JWT)
curl -X PUT http://localhost:5004/users/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{"first_name": "Jane"}'
```

## 🚀 Deployment

### Local Development
```bash
# Auto-reload on code changes
uvicorn main:app --reload --port 5004
```

### Google Cloud Run

The service includes a `Dockerfile` for Cloud Run deployment:

```bash
# Build and deploy
gcloud run deploy user-services \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "DB_USER=...,DB_PASSWORD=...,GOOGLE_CLIENT_ID=...,GOOGLE_CLIENT_SECRET=..."
```

**Important**: Set environment variables in Cloud Run:
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI` (your frontend callback URL)



## 🤝 Integration with Other Services

- **Frontend (Theatre_UI)**: User authentication and profile management
- **Booking Service**: User validation for bookings

## 📖 Documentation

- **Interactive API Docs**: http://localhost:5004/docs
- [OAUTH_JWT_SETUP.md](OAUTH_JWT_SETUP.md) - OAuth and JWT setup guide

## 💡 Development Tips

```bash
# View logs
uvicorn main:app --log-level debug

# Test database connection
python test_connection.py

# Clean Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +
```

## ⚠️ Notes

- Password hashing is handled by the service (stored as `password_hash`)
- OAuth users have `password_hash="oauth_google"`
- JWT tokens contain: `sub` (user_id), `email`, `first_name`, `last_name`
- Cloud Run uses `PORT` environment variable (defaults to 5004 locally)

## 📝 Quick Commands

```bash
# Install
pip install -r requirements.txt

# Run
python main.py
# or
uvicorn main:app --reload --port 5004

# View docs
open http://localhost:5004/docs
```

---

**Built with FastAPI** 🚀 | **Version 0.1.0** | **Python 3.11+**

For questions, check the interactive documentation at http://localhost:5004/docs
