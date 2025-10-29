"""Generátor unikátních ID pro prvky v diagramu."""
import itertools


# Globální čítač pro generování unikátních ID
# Používá itertools.count pro nekonečnou sekvenci čísel začínající od 1
_id_counter = itertools.count(1)

def next_id(prefix: str) -> str:
    """
    Vygeneruje nové unikátní ID s daným prefixem.
    
    Args:
        prefix: Prefix ID (např. "object", "process", "state", "link")
    
    Returns:
        Unikátní ID ve formátu "{prefix}_{číslo}" (např. "object_1", "process_2")
    """
    return f"{prefix}_{next(_id_counter)}"