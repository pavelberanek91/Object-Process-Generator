"""C/E Petriho síť pro simulaci OPM diagramu.

C/E (Condition/Event) Petriho síť je jednoduchý typ Petriho sítě, kde:
- Každé místo může obsahovat maximálně jeden token (0 nebo 1)
- Přechody jsou okamžité (bez času)
- Tokeny reprezentují objekty ve stavech
"""
from __future__ import annotations
from typing import Dict, Set, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Place:
    """Místo v Petriho síti - reprezentuje stav objektu."""
    id: str
    label: str  # "Object at state State" nebo "Object"
    object_id: str  # ID objektu
    state_label: Optional[str] = None  # Název stavu (None pokud objekt bez stavu)
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class Transition:
    """Přechod v Petriho síti - reprezentuje proces."""
    id: str
    label: str  # Název procesu
    process_id: str  # ID procesu
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class Arc:
    """Oblouk mezi místem a přechodem."""
    place_id: str
    transition_id: str
    arc_type: str  # "input" (consumes), "output" (yields), "test" (requires)
    weight: int = 1  # Pro C/E sítě je vždy 1
    
    def __hash__(self):
        return hash((self.place_id, self.transition_id, self.arc_type))


class PetriNet:
    """C/E Petriho síť pro simulaci OPM diagramu."""
    
    def __init__(self):
        self.places: Dict[str, Place] = {}
        self.transitions: Dict[str, Transition] = {}
        self.arcs: Set[Arc] = set()
        self.marking: Dict[str, bool] = {}  # place_id -> bool (True = má token)
        
    def add_place(self, place: Place):
        """Přidá místo do sítě."""
        self.places[place.id] = place
        self.marking[place.id] = False  # Počáteční označení = žádný token
        
    def add_transition(self, transition: Transition):
        """Přidá přechod do sítě."""
        self.transitions[transition.id] = transition
        
    def add_arc(self, arc: Arc):
        """Přidá oblouk do sítě."""
        self.arcs.add(arc)
        
    def set_token(self, place_id: str, has_token: bool):
        """Nastaví token v místě."""
        if place_id in self.places:
            self.marking[place_id] = has_token
            
    def has_token(self, place_id: str) -> bool:
        """Zkontroluje, zda má místo token."""
        return self.marking.get(place_id, False)
        
    def get_input_places(self, transition_id: str) -> List[str]:
        """Vrátí seznam vstupních míst pro přechod (input a test oblouky)."""
        return [arc.place_id for arc in self.arcs 
                if arc.transition_id == transition_id 
                and arc.arc_type in ("input", "test")]
        
    def get_output_places(self, transition_id: str) -> List[str]:
        """Vrátí seznam výstupních míst pro přechod."""
        return [arc.place_id for arc in self.arcs 
                if arc.transition_id == transition_id 
                and arc.arc_type == "output"]
        
    def is_enabled(self, transition_id: str) -> bool:
        """Zkontroluje, zda je přechod aktivní (všechna vstupní místa mají tokeny)."""
        input_places = self.get_input_places(transition_id)
        if not input_places:
            return False  # Přechod bez vstupů není aktivní
        return all(self.has_token(pid) for pid in input_places)
        
    def can_fire(self, transition_id: str) -> bool:
        """Zkontroluje, zda může přechod proběhnout (je aktivní + výstupy jsou volné)."""
        if not self.is_enabled(transition_id):
            return False
            
        # Pro C/E sítě: výstupní místa musí být volná (nemají token)
        output_places = self.get_output_places(transition_id)
        return all(not self.has_token(pid) for pid in output_places)
        
    def fire_transition(self, transition_id: str) -> bool:
        """Provede přechod (pokud je to možné).
        
        Returns:
            True pokud se přechod provedl, False jinak
        """
        if not self.can_fire(transition_id):
            return False
            
        # Odebereme tokeny ze vstupních míst (pouze z input, ne z test)
        for arc in self.arcs:
            if arc.transition_id == transition_id and arc.arc_type == "input":
                self.set_token(arc.place_id, False)
                
        # Přidáme tokeny do výstupních míst
        for arc in self.arcs:
            if arc.transition_id == transition_id and arc.arc_type == "output":
                self.set_token(arc.place_id, True)
                
        return True
        
    def get_enabled_transitions(self) -> List[str]:
        """Vrátí seznam ID aktivních přechodů."""
        return [tid for tid in self.transitions.keys() if self.is_enabled(tid)]
        
    def get_fireable_transitions(self) -> List[str]:
        """Vrátí seznam ID přechodů, které mohou proběhnout."""
        return [tid for tid in self.transitions.keys() if self.can_fire(tid)]
        
    def get_blocked_transitions(self) -> List[str]:
        """Vrátí seznam ID blokovaných přechodů (aktivní, ale nemohou proběhnout)."""
        enabled = set(self.get_enabled_transitions())
        fireable = set(self.get_fireable_transitions())
        return list(enabled - fireable)

