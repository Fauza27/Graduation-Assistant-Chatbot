import os
import re
import json

def process_markdown(filepath, source_name, id_prefix, output_dir):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    parent_chunks = []
    child_chunks = []

    current_parent = None
    current_child = None
    
    parent_counter = 1
    child_counter = 1

    current_page = "1"
    current_section_name = "Front Matter"
    
    # Create the very first parent chunk for Front Matter
    current_parent = {
        "parent_id": f"parent-{id_prefix}-{parent_counter:03d}",
        "title": "Front Matter",
        "content": "",
        "child_ids": [],
        "section": current_section_name
    }
    parent_chunks.append(current_parent)
    
    current_child = {
        "id": f"{id_prefix}-{child_counter:03d}",
        "title": "Awal Dokumen",
        "content": "",
        "source": source_name,
        "section": current_section_name,
        "pages": []
    }
    current_parent["child_ids"].append(current_child["id"])
    child_chunks.append(current_child)

    for line in lines:
        # Check for page tags
        page_match = re.search(r'<span id="page-(\d+)-\d+"></span>', line)
        if page_match:
            current_page = str(int(page_match.group(1)) + 1) # 0-indexed usually, so +1
            line = re.sub(r'<span id="page-\d+-\d+"></span>', '', line)

        line_stripped = line.strip()
        if not line_stripped:
            if current_child:
                current_child["content"] += "\n"
            continue

        # Check for headings
        heading_match = re.match(r'^(#{1,4})\s+(.+)$', line_stripped)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2)
            
            # Clean title from markdown bold/italic
            clean_title = re.sub(r'[*_]', '', title)

            if level == 1:
                # New Parent!
                # If current parent has empty content, we can derive it from children later
                parent_counter += 1
                current_section_name = clean_title
                current_parent = {
                    "parent_id": f"parent-{id_prefix}-{parent_counter:03d}",
                    "title": clean_title,
                    "content": "",
                    "child_ids": [],
                    "section": current_section_name
                }
                parent_chunks.append(current_parent)
                
                # Also create a new child under this parent automatically
                child_counter += 1
                current_child = {
                    "id": f"{id_prefix}-{child_counter:03d}",
                    "title": clean_title,
                    "content": "",
                    "source": source_name,
                    "section": current_section_name,
                    "pages": []
                }
                current_parent["child_ids"].append(current_child["id"])
                child_chunks.append(current_child)
            else:
                # New Child!
                child_counter += 1
                current_child = {
                    "id": f"{id_prefix}-{child_counter:03d}",
                    "title": clean_title,
                    "content": "",
                    "source": source_name,
                    "section": current_section_name,
                    "pages": []
                }
                current_parent["child_ids"].append(current_child["id"])
                child_chunks.append(current_child)
        else:
            # Just content
            if current_child:
                current_child["content"] += line
                if current_page not in current_child["pages"]:
                    current_child["pages"].append(current_page)

    # Post processing: clean up empty child chunks
    valid_children = []
    for c in child_chunks:
        c["content"] = c["content"].strip()
        # if the chunk has content, keep it
        if c["content"]:
            valid_children.append(c)
            # update parent's content summary loosely
            for p in parent_chunks:
                if c["id"] in p["child_ids"]:
                    # append a small summary to parent
                    p["content"] += c["content"][:200] + "... \n"

    # Fix child_ids in parents
    valid_child_ids = set(c["id"] for c in valid_children)
    for p in parent_chunks:
        p["child_ids"] = [cid for cid in p["child_ids"] if cid in valid_child_ids]
        p["content"] = p["content"].strip()

    # Filter out empty parents
    valid_parents = [p for p in parent_chunks if p["child_ids"]]

    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, f'parent_chunk_{id_prefix}.json'), 'w', encoding='utf-8') as f:
        json.dump(valid_parents, f, indent=2, ensure_ascii=False)
        
    with open(os.path.join(output_dir, f'child_chunk_{id_prefix}.json'), 'w', encoding='utf-8') as f:
        json.dump(valid_children, f, indent=2, ensure_ascii=False)
        
    print(f"[{id_prefix}] Generated {len(valid_parents)} parents and {len(valid_children)} children.")


if __name__ == '__main__':
    base_dir = r"c:\Users\Muhammad Fauza\SKRIPSI"
    
    skripsi_md = os.path.join(base_dir, r"marker_workspace\output\Panduan-Tugas-Akhir-Skripsi-2024\Panduan-Tugas-Akhir-Skripsi-2024.md")
    non_skripsi_md = os.path.join(base_dir, r"marker_workspace\output\Panduan-Tugas-Akhir-Non-Skripsi-2024\Panduan-Tugas-Akhir-Non-Skripsi-2024.md")
    
    out_skripsi = os.path.join(base_dir, r"backend\extract-pdf\Skripsi")
    out_non_skripsi = os.path.join(base_dir, r"backend\extract-pdf\Non-Skripsi")
    
    process_markdown(
        filepath=skripsi_md,
        source_name="Panduan Penyusunan Skripsi Cetak",
        id_prefix="skripsi",
        output_dir=out_skripsi
    )
    
    process_markdown(
        filepath=non_skripsi_md,
        source_name="Panduan Penyusunan Tugas Akhir Non-Skripsi Cetak",
        id_prefix="non-skripsi",
        output_dir=out_non_skripsi
    )

