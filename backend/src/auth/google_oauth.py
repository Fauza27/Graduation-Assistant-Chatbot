from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Dict, Any

from config.settings import get_settings

settings = get_settings()

def verify_google_id_token(token_string: str) -> Dict[str, Any]:
    """
    Verify Google ID token sent from Frontend (Google Identity Services).
    Returns user info dictionary if valid.
    """
    try:
        # Verify the token against Google's API
        idinfo = id_token.verify_oauth2_token(
            token_string, 
            requests.Request(), 
            settings.GOOGLE_CLIENT_ID
        )
        
        # idinfo contains claims like 'sub', 'email', 'name', 'picture'
        return idinfo
    except ValueError as e:
        # Invalid token
        raise ValueError(f"Invalid or expired Google token: {str(e)}")
