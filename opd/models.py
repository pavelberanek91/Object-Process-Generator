from dataclasses import dataclass
from typing import Optional


@dataclass
class DiagramNode:
    id: str
    kind: str
    label: str
    x: float
    y: float
    w: float
    h: float
    parent_id: Optional[str] = None


@dataclass
class DiagramLink:
    id: str
    src: str
    dst: str
    link_type: str
    label: str = ""
    type_dx: float = 6.0
    type_dy: float = -6.0
    label_dx: float = 6.0
    label_dy: float = 12.0