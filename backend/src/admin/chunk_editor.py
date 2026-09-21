"""Build the admin knowledge tree and read chunk details.

Mutation functions are re-exported for the existing admin API.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from supabase import Client

from src.admin.auth import ResourceNotFoundError
from src.admin.chunk_mutations import (
    ChunkConflictError,
    delete_chunk,
    process_chunk_reembed,
    save_chunk,
    trigger_reembed,
)
from src.utils.page_sorting import smart_page_sort_key as _smart_page_sort_key

__all__ = [
    "ChunkConflictError",
    "delete_chunk",
    "get_chunk_detail",
    "get_edit_status",
    "list_knowledge_tree",
    "process_chunk_reembed",
    "save_chunk",
    "trigger_reembed",
]


# === DATA STRUCTURES FOR CLARITY ===

@dataclass
class ChunkSummary:
    """Summary statistics for the knowledge tree"""
    total_documents: int
    total_parents: int
    total_children: int
    last_updated_at: str | None = None


@dataclass
class ParentChunk:
    """Represents a parent document with its children"""
    parent_id: str
    title: str
    child_count: int
    children: list[dict[str, Any]]


@dataclass
class DocumentSection:
    """Represents a section within a document"""
    section: str
    parents: list[ParentChunk]


@dataclass
class Document:
    """Represents a complete document with all sections"""
    domain: str
    source: str
    chapters: list[DocumentSection]


def format_pages_for_frontend(pages: Any) -> str:
    """
    Convert database pages array to user-friendly string with smart sorting.
    
    Examples:
        ["1", "2"] -> "1, 2"
        ["12-13"] -> "12-13"
        ["2", "1", "10"] -> "1, 2, 10"  # Sorted numerically
        None -> ""
    """
    if not pages:
        return ""
    if isinstance(pages, list):
        # Apply smart sorting before joining
        sorted_pages = sorted(pages, key=_smart_page_sort_key)
        return ", ".join(str(page) for page in sorted_pages)
    return str(pages)


def parse_pages_from_frontend(pages_string: str) -> list[str]:
    """
    Convert user input pages string to database array.
    
    Examples:
        "1, 2, 3" -> ["1", "2", "3"]
        "12-13" -> ["12-13"]
        "" -> []
    """
    if not pages_string or not pages_string.strip():
        return []
    
    # Split by comma and clean whitespace
    pages = [page.strip() for page in pages_string.split(",")]
    return [page for page in pages if page]  # Remove empty strings


def calculate_last_updated_time(
    parents_data: list[dict[str, Any]],
    children_data: list[dict[str, Any]],
) -> str | None:
    """
    Find the most recent update time from both parents and children.
    """
    all_timestamps = []
    
    # Collect parent timestamps
    for parent in parents_data:
        if parent.get("updated_at"):
            all_timestamps.append(parent["updated_at"])
    
    # Collect children timestamps
    for child in children_data:
        if child.get("updated_at"):
            all_timestamps.append(child["updated_at"])
    
    return max(all_timestamps) if all_timestamps else None


# === MAIN FUNCTIONS ===

def get_knowledge_tree_data(supabase: Client) -> Tuple[List[Dict], List[Dict]]:
    """
    Fetch raw data from database for knowledge tree construction.
    
    Returns:
        Tuple of (parents_data, children_data)
    """
    # Get all parent documents with essential fields
    parents_query = supabase.table("parent_documents").select(
        "parent_id, title, domain, section, updated_at"
    ).order("domain").order("section").order("parent_id")
    
    parents_result = parents_query.execute()
    parents_data = parents_result.data
    
    # Get all child documents with essential fields
    children_query = supabase.table("child_documents").select(
        "id, parent_id, title, pages, source, embedding_status, updated_at"
    ).order("parent_id")  # Page ordering is handled in Python.
    
    children_result = children_query.execute()
    children_data = children_result.data
    
    return parents_data, children_data


def build_parent_source_mapping(children_data: List[Dict]) -> Dict[str, str]:
    """
    Create mapping from parent_id to source document.
    
    Since 'source' is stored in child_documents, we need to map each parent
    to its source by looking at its first child's source field.
    """
    parent_to_source = {}
    
    for child in children_data:
        parent_id = child["parent_id"]
        child_source = child.get("source")
        
        # Use first child's source as representative for the parent
        if parent_id not in parent_to_source and child_source:
            parent_to_source[parent_id] = child_source
    
    return parent_to_source


def group_children_by_parent(children_data: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group child documents by their parent_id for easier lookup.
    Applies smart sorting to pages within each child.
    """
    children_by_parent = {}
    
    for child in children_data:
        parent_id = child["parent_id"]
        
        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []
        
        # Sort pages using smart page sorting
        pages = child.get("pages") or []
        if pages:
            sorted_pages = sorted(pages, key=_smart_page_sort_key)
        else:
            sorted_pages = []
        
        # Store simplified child info
        child_info = {
            "id": child["id"],
            "title": child["title"],
            "pages": sorted_pages,  # Use sorted pages
            "embedding_status": child["embedding_status"]
        }
        children_by_parent[parent_id].append(child_info)
    
    # Sort children within each parent by first page number
    for parent_id in children_by_parent:
        children_by_parent[parent_id].sort(
            key=lambda child: _smart_page_sort_key(child["pages"][0]) if child["pages"] else (999, 0, "")
        )
    
    return children_by_parent


def organize_documents_by_domain_and_source(
    parents_data: List[Dict],
    parent_to_source: Dict[str, str],
    children_by_parent: Dict[str, List[Dict]]
) -> Dict[Tuple[str, str], Dict[str, List[ParentChunk]]]:
    """
    Organize all documents by (domain, source) and then by section.
    
    Returns:
        Dictionary with structure: {(domain, source): {section: [parents]}}
    """
    documents_tree = {}
    
    for parent in parents_data:
        # Extract parent information
        parent_id = parent["parent_id"]
        domain = parent.get("domain", "")
        section = parent["section"]
        source = parent_to_source.get(parent_id, "")
        
        # Get children for this parent
        parent_children = children_by_parent.get(parent_id, [])
        
        # Create document key
        document_key = (domain, source)
        
        # Initialize document structure if needed
        if document_key not in documents_tree:
            documents_tree[document_key] = {}
        
        if section not in documents_tree[document_key]:
            documents_tree[document_key][section] = []
        
        # Add parent to the appropriate section
        parent_chunk = ParentChunk(
            parent_id=parent_id,
            title=parent["title"],
            child_count=len(parent_children),
            children=parent_children
        )
        documents_tree[document_key][section].append(parent_chunk)
    
    return documents_tree


def format_knowledge_tree_response(
    documents_tree: Dict[Tuple[str, str], Dict[str, List[ParentChunk]]],
    summary: ChunkSummary
) -> Dict[str, Any]:
    """
    Convert internal tree structure to API response format.
    """
    documents_list = []
    
    for (domain, source), sections_dict in documents_tree.items():
        # Convert sections to list format
        chapters_list = []
        for section_name, parents_list in sections_dict.items():
            section_data = DocumentSection(
                section=section_name,
                parents=[{
                    "parent_id": p.parent_id,
                    "title": p.title,
                    "child_count": p.child_count,
                    "children": p.children
                } for p in parents_list]
            )
            chapters_list.append({
                "section": section_data.section,
                "parents": section_data.parents
            })
        
        # Create document
        document = Document(
            domain=domain,
            source=source,
            chapters=chapters_list
        )
        documents_list.append({
            "domain": document.domain,
            "source": document.source,
            "chapters": document.chapters
        })
    
    return {
        "summary": {
            "total_documents": summary.total_documents,
            "total_parents": summary.total_parents,
            "total_children": summary.total_children,
            "last_updated_at": summary.last_updated_at
        },
        "documents": documents_list
    }


def list_knowledge_tree_readable(supabase: Client) -> Dict[str, Any]:
    """
    Build complete knowledge tree with maximum readability.
    
    This function breaks down the complex tree-building logic into
    clear, understandable steps:
    
    1. Fetch raw data from database
    2. Build parent-to-source mapping
    3. Group children by parent
    4. Organize by domain and source
    5. Format for API response
    """
    # Step 1: Get raw data
    parents_data, children_data = get_knowledge_tree_data(supabase)
    
    # Step 2: Build helper mappings
    parent_to_source = build_parent_source_mapping(children_data)
    children_by_parent = group_children_by_parent(children_data)
    
    # Step 3: Organize into tree structure
    documents_tree = organize_documents_by_domain_and_source(
        parents_data, parent_to_source, children_by_parent
    )
    
    # Step 4: Calculate summary statistics
    summary = ChunkSummary(
        total_documents=len(documents_tree),
        total_parents=len(parents_data),
        total_children=len(children_data),
        last_updated_at=calculate_last_updated_time(parents_data, children_data)
    )
    
    # Step 5: Format response
    return format_knowledge_tree_response(documents_tree, summary)


def get_chunk_detail_readable(child_id: str, supabase: Client) -> Dict[str, Any]:
    """
    Get complete details for a single chunk with clear error handling.
    
    This combines data from multiple tables:
    - child_documents: main chunk data
    - parent_documents: parent information
    - chunk_edit_logs: latest reembed timestamp
    """
    # Step 1: Get the child chunk
    child_result = supabase.table("child_documents").select("*").eq("id", child_id).limit(1).execute()
    
    if not child_result.data:
        raise ResourceNotFoundError(f"Child chunk {child_id} not found")
    
    child_data = child_result.data[0]
    
    # Step 2: Get parent information
    parent_info = None
    section = child_data.get("section")  # fallback to child's section
    
    if child_data.get("parent_id"):
        parent_result = supabase.table("parent_documents").select(
            "parent_id, title, section"
        ).eq("parent_id", child_data["parent_id"]).limit(1).execute()
        
        if parent_result.data:
            parent_data = parent_result.data[0]
            parent_info = {
                "parent_id": parent_data["parent_id"],
                "title": parent_data["title"]
            }
            section = parent_data["section"]  # prefer parent's section
    
    # Step 3: Get latest successful reembed timestamp
    latest_reembed = None
    log_result = supabase.table("chunk_edit_logs").select("reembedded_at").eq(
        "child_id", child_id
    ).eq("status", "success").order("reembedded_at", desc=True).limit(1).execute()
    
    if log_result.data:
        latest_reembed = log_result.data[0]["reembedded_at"]
    
    # Step 4: Format response
    return {
        "id": child_data["id"],
        "title": child_data["title"],
        "pages": format_pages_for_frontend(child_data.get("pages")),
        "content": child_data["content"],
        "embedding_status": child_data["embedding_status"],
        "reembedded_at": latest_reembed,
        "parent": parent_info,
        "section": section,
        "domain": child_data.get("domain", ""),
        "source": child_data.get("source", "")
    }


def get_chunk_edit_status(child_id: str, supabase: Client) -> Optional[Dict[str, Any]]:
    """
    Get the latest edit/reembedding status for a chunk.
    
    Returns None if no edit history exists.
    """
    status_result = supabase.table("chunk_edit_logs").select("*").eq(
        "child_id", child_id
    ).order("edited_at", desc=True).limit(1).execute()
    
    if not status_result.data:
        return None
    
    log_entry = status_result.data[0]
    
    return {
        "log_id": log_entry["log_id"],
        "child_id": log_entry["child_id"],
        "status": log_entry["status"],
        "error_message": log_entry.get("error_message"),
        "edited_at": log_entry["edited_at"],
        "reembedded_at": log_entry.get("reembedded_at")
    }



# Stable API names; writes are isolated from the read-only tree/detail helpers.
list_knowledge_tree = list_knowledge_tree_readable
get_chunk_detail = get_chunk_detail_readable
get_edit_status = get_chunk_edit_status
