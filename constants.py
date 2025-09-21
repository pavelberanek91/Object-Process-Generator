from __future__ import annotations

GRID_SIZE = 25
NODE_W, NODE_H = 140, 70
STATE_W, STATE_H = 100, 28

# konstanty pro resize prvků
HANDLE_SIZE = 10          # velikost táhla v px (ignoruje zoom)
MIN_NODE_W  = 80          # minimální šířka uzlu při resize
MIN_NODE_H  = 50          # minimální výška uzlu při resize

LINK_TYPES = [
    # procedural
    "input", "consumption", "output", "result", "effect", "agent", "instrument",
    # structural
    "aggregation", "exhibition", "generalization", "instantiation",
]

PROCEDURAL_TYPES = {"input", "consumption", "output", "result", "effect", "agent", "instrument"}
STRUCTURAL_TYPES  = {"aggregation", "exhibition", "generalization", "instantiation"}

class Mode:
    SELECT = "select"
    ADD_OBJECT = "add_object"
    ADD_PROCESS = "add_process"
    ADD_STATE = "add_state"
    ADD_LINK = "add_link"