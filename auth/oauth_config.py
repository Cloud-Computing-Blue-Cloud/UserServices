import os
from typing import Dict, Any
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import httpx

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8001/auth/google/callback")

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]


def get_google_oauth_flow(redirect_uri: str = None) -> Flow:
    """
    Get Google OAuth flow.
    
    Args:
        redirect_uri: Optional redirect URI. If not provided, uses GOOGLE_REDIRECT_URI from env.
    """
    redirect = redirect_uri or GOOGLE_REDIRECT_URI
    
    # Ensure redirect_uri doesn't have trailing slash and is normalized
    redirect = redirect.rstrip('/')
    
    print(f"[DEBUG] get_google_oauth_flow - Using redirect_uri: {redirect}")
    print(f"[DEBUG] GOOGLE_CLIENT_ID exists: {bool(GOOGLE_CLIENT_ID)}")
    print(f"[DEBUG] GOOGLE_CLIENT_SECRET exists: {bool(GOOGLE_CLIENT_SECRET)}")
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
    
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect],
        }
    }

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=SCOPES,
        redirect_uri=redirect
    )

    return flow


async def exchange_code_for_token(code: str, redirect_uri: str = None) -> Dict[str, Any]:
    """
    Exchange OAuth code for access token.
    
    Args:
        code: OAuth authorization code from Google
        redirect_uri: Redirect URI used in the authorization request (must match)
    
    Raises:
        InvalidGrantError: If the code has already been used or is invalid
    """
    import os
    from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
    
    print(f"[DEBUG] exchange_code_for_token called with redirect_uri: {redirect_uri}")
    print(f"[DEBUG] GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID', 'NOT SET')[:20]}...")
    
    flow = get_google_oauth_flow(redirect_uri=redirect_uri)
    print(f"[DEBUG] Created flow, attempting to fetch token...")
    try:
        flow.fetch_token(code=code)
    except InvalidGrantError as e:
        # Code has already been used or is invalid
        print(f"[ERROR] fetch_token failed: {str(e)}")
        print(f"[ERROR] Code: {code[:20]}...")
        print(f"[ERROR] Redirect URI: {redirect_uri}")
        print(f"[WARNING] This code may have already been used. This can happen if the callback is called twice.")
        raise InvalidGrantError(
            error="invalid_grant",
            error_description="The authorization code has already been used or is invalid. Please try logging in again."
        )
    except Exception as e:
        print(f"[ERROR] fetch_token failed: {str(e)}")
        print(f"[ERROR] Code: {code[:20]}...")
        print(f"[ERROR] Redirect URI: {redirect_uri}")
        raise
    credentials = flow.credentials

    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "id_token": credentials.id_token,
    }


async def get_user_info(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        return response.json()
