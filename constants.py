"""Globální konstanty pro OPM Editor."""
from __future__ import annotations

# === Rozměry a mřížka ===
GRID_SIZE = 25  # Velikost čtverce mřížky v pixelech (pro snap)
NODE_W, NODE_H = 140, 70  # Výchozí šířka a výška objektů a procesů
STATE_W, STATE_H = 100, 28  # Výchozí šířka a výška stavů

# === Konstanty pro resize prvků ===
HANDLE_SIZE = 10  # Velikost táhla pro změnu velikosti v px (ignoruje zoom)
MIN_NODE_W  = 80  # Minimální šířka uzlu při změně velikosti
MIN_NODE_H  = 50  # Minimální výška uzlu při změně velikosti

# === Typy vazeb (linků) v OPM ===
LINK_TYPES = [
    # Procedurální vazby (vztahy mezi procesy a objekty)
    "consumption", "result", "effect", "agent", "instrument",
    # Strukturální vazby (vztahy mezi objekty navzájem)
    "aggregation", "exhibition", "generalization", "instantiation",
]

# Rozdělení typů vazeb pro snadnější validaci
PROCEDURAL_TYPES = {"consumption", "result", "effect", "agent", "instrument"}
STRUCTURAL_TYPES  = {"aggregation", "exhibition", "generalization", "instantiation"}

# === Režimy editoru ===
class Mode:
    """Výčet možných režimů interakce v editoru."""
    SELECT = "select"  # Výběr a přesouvání prvků
    ADD_OBJECT = "add_object"  # Přidávání objektů
    ADD_PROCESS = "add_process"  # Přidávání procesů
    ADD_STATE = "add_state"  # Přidávání stavů
    ADD_LINK = "add_link"  # Přidávání vazeb (linků)