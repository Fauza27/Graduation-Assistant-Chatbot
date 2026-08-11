import os
import sys

sys.path.append(os.getcwd())

from config.settings import get_settings
from supabase import create_client

settings = get_settings()
supabase = create_client(settings.supabase_url, settings.supabase_service_key)

try:
    res = supabase.table("parent_documents").select("*").limit(1).execute()
    print("Columns in parent_documents:", list(res.data[0].keys()) if res.data else "Table is empty")
    print("Data:", res.data)
except Exception as e:
    print("Error querying parent_documents:", e)
