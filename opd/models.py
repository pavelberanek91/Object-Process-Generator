"""Datové modely pro reprezentaci OPD (Object-Process Diagram) prvků."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class DiagramNode:
    """
    Reprezentuje jeden uzel v diagramu (objekt, proces nebo stav).
    
    Attributes:
        id: Unikátní identifikátor uzlu
        kind: Typ uzlu ("object", "process", "state")
        label: Textový popisek uzlu
        x: X souřadnice středu uzlu ve scéně
        y: Y souřadnice středu uzlu ve scéně
        w: Šířka uzlu
        h: Výška uzlu
        parent_id: ID rodičovského uzlu (pouze pro stavy, které jsou vždy uvnitř objektu)
        parent_process_id: ID rodičovského procesu (pro podprocesy a objekty v in-zoom view)
        essence: Podstata ("physical" nebo "informatical", pouze pro objekty a procesy)
        affiliation: Příslušnost ("systemic" nebo "environmental", pouze pro objekty a procesy)
    """
    id: str
    kind: str
    label: str
    x: float
    y: float
    w: float
    h: float
    parent_id: Optional[str] = None
    parent_process_id: Optional[str] = None
    essence: str = "physical"
    affiliation: str = "systemic"


@dataclass
class DiagramLink:
    """
    Reprezentuje vazbu (link) mezi dvěma uzly v diagramu.
    
    Attributes:
        id: Unikátní identifikátor vazby
        src: ID zdrojového uzlu
        dst: ID cílového uzlu
        link_type: Typ vazby (např. "consumption", "result", "aggregation")
        label: Volitelný textový popisek vazby
        type_dx: X offset pozice textu typu vazby od středu linky
        type_dy: Y offset pozice textu typu vazby od středu linky
        label_dx: X offset pozice textu labelu od středu linky
        label_dy: Y offset pozice textu labelu od středu linky
        card_src: Kardinalita u zdroje (pro strukturální vazby, např. "1", "0..*")
        card_dst: Kardinalita u cíle (pro strukturální vazby)
    """
    id: str
    src: str
    dst: str
    link_type: str
    label: str = ""
    type_dx: float = 6.0
    type_dy: float = -6.0
    label_dx: float = 6.0
    label_dy: float = 12.0
    card_src: str = ""  # Kardinalita u zdroje
    card_dst: str = ""  # Kardinalita u cíle