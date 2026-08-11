import os
import sys
import argparse
import getpass
import bcrypt

# Add backend directory to sys.path so we can import from src and config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from supabase import create_client

def hash_password(plain_password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')

def main():
    parser = argparse.ArgumentParser(description="Reset or create an admin user password")
    parser.add_argument("--username", required=True, help="Username of the admin")
    parser.add_argument("--new-password", help="New password (will prompt if not provided)")
    parser.add_argument("--full-name", help="Full name (used only when creating a new admin)")
    
    args = parser.parse_args()
    
    password = args.new_password
    if not password:
        password = getpass.getpass(f"Enter new password for '{args.username}': ")
        confirm_password = getpass.getpass("Confirm new password: ")
        if password != confirm_password:
            print("Passwords do not match. Exiting.")
            sys.exit(1)
            
    if len(password) < 8:
        print("Password must be at least 8 characters long. Exiting.")
        sys.exit(1)
        
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    
    password_hash = hash_password(password)
    
    # Check if user exists
    res = supabase.table("admin_users").select("admin_id").eq("username", args.username).limit(1).execute()
    
    if res.data:
        # User exists, update password
        admin_id = res.data[0]["admin_id"]
        supabase.table("admin_users").update({"password_hash": password_hash}).eq("admin_id", admin_id).execute()
        print(f"Successfully updated password for existing admin '{args.username}'.")
    else:
        # User doesn't exist, create new
        new_admin = {
            "username": args.username,
            "password_hash": password_hash,
            "full_name": args.full_name
        }
        supabase.table("admin_users").insert(new_admin).execute()
        print(f"Successfully created new admin '{args.username}'.")

if __name__ == "__main__":
    main()
