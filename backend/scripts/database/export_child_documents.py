#!/usr/bin/env python3
"""
Script untuk export data dari tabel child_documents ke CSV
Tidak termasuk kolom: embedding, created_at, embedding_status, updated_at
"""
import csv
import sys
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from supabase import create_client, Client
from config.settings import get_settings

def get_all_child_documents():
    """Ambil semua data child_documents dari database"""
    settings = get_settings()
    
    # Initialize Supabase client
    supabase: Client = create_client(
        settings.supabase_url, 
        settings.supabase_service_key
    )
    
    # Kolom yang ingin kita ambil (tanpa embedding, created_at, embedding_status, updated_at)
    columns_to_select = [
        "id",
        "parent_id", 
        "title",
        "content",
        "section",
        "pages",
        "source",
        "metadata",
        "domain"
    ]
    
    try:
        # Query database
        print("Mengambil data dari tabel child_documents...")
        response = supabase.table(settings.table_child_chunks).select(
            ", ".join(columns_to_select)
        ).execute()
        
        if response.data:
            print(f"Berhasil mengambil {len(response.data)} record")
            return response.data, columns_to_select
        else:
            print("Tidak ada data yang ditemukan")
            return [], columns_to_select
            
    except Exception as e:
        print(f"Error saat mengambil data: {e}")
        return [], columns_to_select

def export_to_csv(data, columns, filename=None):
    """Export data ke file CSV"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"child_documents_export_{timestamp}.csv"
    
    export_directory = project_root / "backup" / "exports"
    export_directory.mkdir(parents=True, exist_ok=True)
    filepath = export_directory / Path(filename).name
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            
            # Write header
            writer.writeheader()
            
            # Write data
            for row in data:
                # Convert metadata to string if it's a dict/json
                if 'metadata' in row and isinstance(row['metadata'], dict):
                    row['metadata'] = str(row['metadata'])
                writer.writerow(row)
        
        print(f"Data berhasil diekspor ke: {filepath}")
        print(f"Total records: {len(data)}")
        return str(filepath)
        
    except Exception as e:
        print(f"Error saat menulis file CSV: {e}")
        return None

def main():
    """Main function"""
    print("=== Export Child Documents to CSV ===")
    print("Mengambil data tanpa kolom: embedding, created_at, embedding_status, updated_at")
    print()
    
    # Get data from database
    data, columns = get_all_child_documents()
    
    if not data:
        print("Tidak ada data untuk diekspor")
        return
    
    # Export to CSV
    csv_file = export_to_csv(data, columns)
    
    if csv_file:
        print(f"\n✅ Export selesai!")
        print(f"📁 File tersimpan di: {csv_file}")
        print(f"📊 Total records: {len(data)}")
        print(f"📋 Kolom yang diekspor: {', '.join(columns)}")
    else:
        print("❌ Export gagal!")

if __name__ == "__main__":
    main()
