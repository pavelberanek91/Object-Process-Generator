from __future__ import annotations
import itertools

GRID_SIZE = 25
NODE_W, NODE_H = 140, 70
STATE_W, STATE_H = 100, 28

LINK_TYPES = [
    # procedural
    "input", "consumption", "output", "result", "effect", "agent", "instrument",
    # structural
    "aggregation", "participation", "exhibition", "characterization",
    "generalization", "specialization", "instantiation", "classification",
]

PROCEDURAL_TYPES = {"input", "consumption", "output", "result", "effect", "agent", "instrument"}
STRUCTURAL_TYPES  = {"aggregation", "participation", "exhibition", "characterization",
                     "generalization", "specialization", "instantiation", "classification"}

class Mode:
    SELECT = "select"
    ADD_OBJECT = "add_object"
    ADD_PROCESS = "add_process"
    ADD_STATE = "add_state"
    ADD_LINK = "add_link"

_id_counter = itertools.count(1)
def next_id(prefix: str) -> str:
    return f"{prefix}_{next(_id_counter)}"