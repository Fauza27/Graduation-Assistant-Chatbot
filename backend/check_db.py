from supabase import create_client
from config.settings import get_settings
import os

try:
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    res = supabase.table(settings.table_parent_chunks).select("*").limit(2).execute()
    for row in res.data:
        print(f"Parent ID: {row.get('parent_id')}")
        print(f"Title: {repr(row.get('title'))}")
        print(f"Section: {repr(row.get('section'))}")
        print("---")
except Exception as e:
    print(f"Error: {e}")
