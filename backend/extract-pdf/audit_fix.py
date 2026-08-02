import json
import os

skripsi_parents = [
    {"title": "Front Matter", "start": 0, "end": 5},
    {"title": "Surat Keputusan", "start": 6, "end": 10},
    {"title": "BAB I PENDAHULUAN", "start": 11, "end": 12},
    {"title": "BAB II KETENTUAN UMUM", "start": 13, "end": 37},
    {"title": "BAB III BENTUK TUGAS AKHIR", "start": 38, "end": 41},
    {"title": "BAB IV PENJELASAN SISTEMATIKA PENULISAN LAPORAN", "start": 42, "end": 57},
    {"title": "BAB V FORMAT DAN TATA CARA PENULISAN", "start": 58, "end": 82},
    {"title": "LAMPIRAN", "start": 83, "end": 145}
]

non_skripsi_parents = [
    {"title": "Front Matter", "start": 0, "end": 5},
    {"title": "Surat Keputusan", "start": 6, "end": 10},
    {"title": "BAB I PENDAHULUAN", "start": 11, "end": 12},
    {"title": "BAB II KETENTUAN UMUM", "start": 13, "end": 34},
    {"title": "BAB III BENTUK TUGAS AKHIR", "start": 35, "end": 61},
    {"title": "BAB IV PENJELASAN SISTEMATIKA PENULISAN LAPORAN", "start": 62, "end": 92},
    {"title": "BAB V FORMAT DAN TATA CARA PENULISAN", "start": 93, "end": 118},
    {"title": "LAMPIRAN", "start": 119, "end": 204}
]

def rebuild(id_prefix, out_dir, mapping):
    child_file = os.path.join(out_dir, f"child_chunk_{id_prefix}.json")
    with open(child_file, 'r', encoding='utf-8') as f:
        children = json.load(f)

    parents = []
    
    for idx, p_cfg in enumerate(mapping):
        p_id = f"parent-{id_prefix}-{idx+1:03d}"
        
        # Get children for this parent
        child_ids = []
        content_preview = ""
        
        for i in range(p_cfg["start"], min(p_cfg["end"]+1, len(children))):
            c = children[i]
            child_ids.append(c["id"])
            c["section"] = p_cfg["title"] # update child's section
            
            # Avoid too long content previews
            text_part = c["content"][:200].replace("\n", " ")
            if len(content_preview) < 800:
                content_preview += text_part + "... \n"
        
        parent_obj = {
            "parent_id": p_id,
            "title": p_cfg["title"],
            "content": content_preview.strip(),
            "child_ids": child_ids,
            "section": p_cfg["title"]
        }
        parents.append(parent_obj)

    # Save fixed children
    with open(child_file, 'w', encoding='utf-8') as f:
        json.dump(children, f, indent=2, ensure_ascii=False)
        
    # Save fixed parents
    parent_file = os.path.join(out_dir, f"parent_chunk_{id_prefix}.json")
    with open(parent_file, 'w', encoding='utf-8') as f:
        json.dump(parents, f, indent=2, ensure_ascii=False)
        
    print(f"[{id_prefix}] Rebuilt {len(parents)} parents and updated {len(children)} children.")

if __name__ == "__main__":
    base = r"c:\Users\Muhammad Fauza\SKRIPSI\backend\extract-pdf"
    rebuild("skripsi", os.path.join(base, "Skripsi"), skripsi_parents)
    rebuild("non-skripsi", os.path.join(base, "Non-Skripsi"), non_skripsi_parents)

