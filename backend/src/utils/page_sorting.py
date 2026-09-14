"""
Utility functions for smart page sorting with proper numeric interleaving.
"""

def smart_page_sort_key(page: str) -> tuple:
    """
    Generate sort key for proper page ordering with numeric interleaving.
    
    Examples:
    - "1" → (0, 1)
    - "12-13" → (0, 12) 
    - "iv" → (1, "iv")
    
    Result: ["1", "12-13", "20"] ✓ (proper interleaving)
    """
    page = page.strip()
    
    # Handle pure numeric pages
    if page.isdigit():
        return (0, int(page))
    
    # Handle numeric ranges like "12-13" or "12 - 13"
    if "-" in page:
        start_part = page.split("-")[0].strip()
        if start_part.isdigit():
            return (0, int(start_part))  # Same tier as pure numeric
    
    # Non-numeric pages fall to last tier
    return (1, page.lower())


def sort_pages(pages: list[str]) -> list[str]:
    """
    Sort pages using smart numeric interleaving.
    
    Args:
        pages: List of page strings to sort
        
    Returns:
        Sorted list with proper numeric ordering
    """
    return sorted(pages, key=smart_page_sort_key)