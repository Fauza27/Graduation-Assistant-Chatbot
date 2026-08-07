from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Dict, Any

from config.settings import get_settings

settings = get_settings()

def verify_google_id_token(token_string: str) -> Dict[str, Any]:
    """
    Verifikasi token Google ID (Secure JWT Flow).
    
    Args:
        token_string: ID token dari Google Identity Services
        
    Returns:
        dict: Payload profil pengguna jika valid (sub, email, name, picture)
        
    Raises:
        ValueError: Jika token tidak valid, kadaluarsa, atau client ID tidak cocok
    """
    try:
        # Verifikasi audience (aud) terhadap client ID kita
        idinfo = id_token.verify_oauth2_token(
            token_string, 
            requests.Request(), 
            settings.GOOGLE_CLIENT_ID
        )

        return idinfo
    except ValueError as e:
        # Invalid token
        raise ValueError(f"Google token invalid: {e}")
