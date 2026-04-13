"""C/E Petriho síť pro simulaci OPM diagramu.

C/E (Condition/Event) Petriho síť je jednoduchý typ Petriho sítě, kde:
- Každé místo může obsahovat maximálně jeden token (0 nebo 1)
- Přechody jsou okamžité (bez času)
- Tokeny reprezentují objekty ve stavech
"""
from __future__ import annotations
from typing import Dict, Set, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Place:
    """Místo v Petriho síti - reprezentuje stav objektu."""
    id: str
    label: str  # "Object at state State" nebo "Object"
    object_id: str  # ID objektu
    state_label: Optional[str] = None  # Název stavu (None pokud objekt bez stavu)
    # Agregát pro objekt se stavy: odkazy na tělo objektu (ne na konkrétní stav).
    # Token je vždy nanejvýš v jednom z {agregát, stavy daného objektu}.
    is_aggregate: bool = False
    
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

    def get_input_test_places(self, transition_id: str) -> List[str]:
        """Vrátí místa napojená oblouky input nebo test (spotřeba + podmínky)."""
        return [
            arc.place_id
            for arc in self.arcs
            if arc.transition_id == transition_id and arc.arc_type in ("input", "test")
        ]

    def _place_ids_for_object(self, object_id: str) -> List[str]:
        """Všechna místa daného objektu (stavy + případný agregát)."""
        return [pid for pid, pl in self.places.items() if pl.object_id == object_id]

    def _sat_set_for_place(self, place_id: str) -> Set[str]:
        """Místa, na kterých může ležet token, aby byl splněn vstup/test z place_id."""
        pl = self.places.get(place_id)
        if not pl:
            return set()
        if pl.is_aggregate:
            return set(self._place_ids_for_object(pl.object_id))
        return {place_id}

    def is_enabled(self, transition_id: str) -> bool:
        """Zkontroluje, zda je přechod aktivní.

        Pro každý objekt na vstupu/testu: sjednocení splňovačů všech oblouků tohoto objektu
        musí obsahovat místo s tokenem (OR mezi alternativními vstupy, např. c1 nebo c2).
        Agregát splňuje kterékoli místo daného objektu. Různé objekty = AND.
        """
        input_test_arcs = [
            arc
            for arc in self.arcs
            if arc.transition_id == transition_id and arc.arc_type in ("input", "test")
        ]
        if not input_test_arcs:
            return False

        by_object: Dict[str, List[Arc]] = {}
        for arc in input_test_arcs:
            pl = self.places.get(arc.place_id)
            if not pl:
                return False
            by_object.setdefault(pl.object_id, []).append(arc)

        for _object_id, arcs in by_object.items():
            sat_union: Set[str] = set()
            for arc in arcs:
                sat_union |= self._sat_set_for_place(arc.place_id)
            if not any(self.has_token(pid) for pid in sat_union):
                return False
        return True
        
    def can_fire(self, transition_id: str) -> bool:
        """Zkontroluje, zda může přechod proběhnout (je aktivní + výstupy jsou volné).
        
        Pro input-output link pairs (stejný objekt, různé stavy) je důležité,
        že po odebrání tokenu ze vstupního stavu bude výstupní stav volný.
        """
        if not self.is_enabled(transition_id):
            return False
            
        # Pro C/E sítě: výstupní místa musí být volná (nemají token)
        output_places = self.get_output_places(transition_id)
        # Pokud přechod nemá výstupní místa, nemůže proběhnout (pro C/E sítě)
        if not output_places:
            return False  # Přechod bez výstupů není validní pro C/E síť
        
        # Zkontrolujeme, zda jsou výstupní místa volná
        blocked_outputs = [pid for pid in output_places if self.has_token(pid)]
        if not blocked_outputs:
            return True  # Všechna výstupní místa jsou volná
        
        # Pro input-output link pairs: zkontrolujeme, zda jsou to různá místa stejného objektu
        # Pokud ano, povolíme provedení (token bude odebrán ze vstupu před přidáním do výstupu)
        input_places = self.get_input_test_places(transition_id)
        input_place_objects = {self.places[pid].object_id for pid in input_places if pid in self.places}
        output_place_objects = {self.places[pid].object_id for pid in output_places if pid in self.places}
        
        # Pokud jsou vstupní a výstupní místa ze stejného objektu, povolíme provedení
        if input_place_objects & output_place_objects:
            print(f"[PetriNet.can_fire] Input-output link pair detected for same object, allowing fire")
            return True
        
        return False
        
    def fire_transition(self, transition_id: str) -> bool:
        """Provede přechod (pokud je to možné) — jednofázové API bez výběru výstupů.

        Nepoužívat u přechodů s více alternativními výstupními stavy stejného objektu
        (tam je potřeba SimulationEngine.step() s dialogem).
        
        Returns:
            True pokud se přechod provedl, False jinak
        """
        if not self.can_fire(transition_id):
            return False
        output_places = self.get_output_places(transition_id)
        by_obj: Dict[str, List[str]] = {}
        for pid in output_places:
            pl = self.places.get(pid)
            if pl and pl.state_label is not None:
                by_obj.setdefault(pl.object_id, []).append(pid)
        if any(len(pids) > 1 for pids in by_obj.values()):
            print(
                "[PetriNet.fire_transition] Ambiguous state outputs for same object; "
                "use SimulationEngine.step()."
            )
            return False
        if not self.activate_transition(transition_id):
            return False
        return self.complete_transition_selected(transition_id, output_places)
    
    def activate_transition(self, transition_id: str) -> bool:
        """Aktivuje přechod - fáze 1: odebere tokeny ze vstupů.
        
        Pro input-output link pairs (stejný objekt, různé stavy) je důležité,
        že kontrolujeme jen is_enabled(), ne can_fire(), protože výstupní místa
        se uvolní až po odebrání tokenu ze vstupního stavu.

        Odebrání: pro každý objekt, který má na přechodu oblouk input,
        se odebere token z jediného místa tohoto objektu, kde token je
        (OR mezi stavy a agregátem). Test oblouky token nemažou.
        
        Returns:
            True pokud se přechod aktivoval, False jinak
        """
        # Kontrolujeme jen, zda je přechod aktivní (vstupy mají tokeny)
        # Nekontrolujeme can_fire(), protože výstupní místa se uvolní až po aktivaci
        if not self.is_enabled(transition_id):
            return False
            
        # Odebereme tokeny ze vstupních míst (pouze z input, ne z test)
        input_arcs = [arc for arc in self.arcs if arc.transition_id == transition_id and arc.arc_type == "input"]
        by_object: Dict[str, List[str]] = {}
        for arc in input_arcs:
            pl = self.places.get(arc.place_id)
            if not pl:
                continue
            by_object.setdefault(pl.object_id, []).append(arc.place_id)

        print(f"[PetriNet.activate_transition] Removing tokens for {len(by_object)} object(s) with input arcs:")
        for object_id in sorted(by_object.keys()):
            sat_union: Set[str] = set()
            for pid in by_object[object_id]:
                sat_union |= self._sat_set_for_place(pid)
            holders = [pid for pid in sat_union if self.has_token(pid)]
            if not holders:
                print(f"[PetriNet.activate_transition] ERROR: no token for object {object_id}")
                return False
            pid = holders[0]
            place = self.places.get(pid)
            place_label = place.label if place else pid
            print(f"  - {place_label} (place_id={pid})")
            self.set_token(pid, False)
                
        return True
    
    def complete_transition(self, transition_id: str) -> bool:
        """Dokončí přechod - fáze 2: přidá tokeny do výstupů.
        
        Pro input-output link pairs (stejný objekt, různé stavy) je důležité,
        že po aktivaci (odebrání tokenu ze vstupního stavu) je výstupní stav volný.
        
        Returns:
            True pokud se přechod dokončil, False jinak
        """
        # Zkontrolujeme, zda má přechod výstupní místa
        output_places = self.get_output_places(transition_id)
        if not output_places:
            print(f"[PetriNet.complete_transition] Transition {transition_id} has no output places")
            return False
        
        # Zkontrolujeme, zda jsou výstupní místa volná
        # Pro input-output link pairs: po aktivaci (odebrání tokenu ze vstupu) by měla být volná
        blocked_outputs = [pid for pid in output_places if self.has_token(pid)]
        if blocked_outputs:
            print(f"[PetriNet.complete_transition] Transition {transition_id} blocked: output places {blocked_outputs} have tokens")
            # Pro input-output link pairs: zkontrolujeme, zda jsou to různá místa stejného objektu
            # Pokud ano, měli bychom povolit dokončení (token byl odebrán ze vstupu při aktivaci)
            input_places = self.get_input_test_places(transition_id)
            input_place_objects = {self.places[pid].object_id for pid in input_places if pid in self.places}
            output_place_objects = {self.places[pid].object_id for pid in output_places if pid in self.places}
            
            # Pokud jsou vstupní a výstupní místa ze stejného objektu, povolíme dokončení
            if input_place_objects & output_place_objects:
                print(f"[PetriNet.complete_transition] Input-output link pair detected for same object, allowing completion")
            else:
                return False
            
        # Přidáme tokeny do výstupních míst
        output_arcs = [arc for arc in self.arcs if arc.transition_id == transition_id and arc.arc_type == "output"]
        print(f"[PetriNet.complete_transition] Adding tokens to {len(output_arcs)} output places:")
        for arc in output_arcs:
            place = self.places.get(arc.place_id)
            place_label = place.label if place else arc.place_id
            print(f"  - {place_label} (place_id={arc.place_id})")
            self.set_token(arc.place_id, True)
                
        return True

    def complete_transition_selected(self, transition_id: str, selected_place_ids: List[str]) -> bool:
        """
        Dokončí přechod s možností vybrat jen některá výstupní místa.

        Používá se v UI režimu, kdy uživatel rozhoduje, do kterých stavů objektu
        se token má přesunout.
        """
        # Normalize vybraných place_id na existující výstupní místa
        all_output_places = set(self.get_output_places(transition_id))
        selected = [pid for pid in selected_place_ids if pid in all_output_places]
        if not selected:
            return False

        # Přechod ve fázi 1 už tokeny z input míst odebere, takže "blocked" konflikty
        # by měly typicky nastat jen tehdy, pokud už tokeny v cílových místech zůstaly.
        # V C/E síti je to považováno za problém (nepřidáváme další token do obsazeného místa).
        blocked_outputs = [pid for pid in selected if self.has_token(pid)]
        if blocked_outputs:
            return False

        output_arcs = [
            arc for arc in self.arcs
            if arc.transition_id == transition_id and arc.arc_type == "output" and arc.place_id in all_output_places
        ]
        output_arcs_selected = [arc for arc in output_arcs if arc.place_id in selected]

        for arc in output_arcs_selected:
            self.set_token(arc.place_id, True)

        return True
        
    def get_enabled_transitions(self) -> List[str]:
        """Vrátí seznam ID aktivních přechodů."""
        return [tid for tid in self.transitions.keys() if self.is_enabled(tid)]
        
    def get_fireable_transitions(self) -> List[str]:
        """Vrátí seznam ID přechodů, které mohou proběhnout."""
        return [tid for tid in self.transitions.keys() if self.can_fire(tid)]
        
    def get_blocked_transitions(self) -> List[str]:
        """Vrátí seznam ID blokovaných přechodů (aktivní, ale nemohou proběhnout kvůli výstupům)."""
        enabled = set(self.get_enabled_transitions())
        fireable = set(self.get_fireable_transitions())
        blocked = list(enabled - fireable)
        
        print(f"[PetriNet.get_blocked_transitions] Enabled: {enabled}")
        print(f"[PetriNet.get_blocked_transitions] Fireable: {fireable}")
        print(f"[PetriNet.get_blocked_transitions] Blocked: {blocked}")
        
        if blocked:
            for tid in blocked:
                transition = self.transitions.get(tid)
                output_places = self.get_output_places(tid)
                output_tokens = [self.has_token(pid) for pid in output_places]
                input_places = self.get_input_places(tid)
                input_tokens = [self.has_token(pid) for pid in input_places]
                print(f"[PetriNet] Blocked transition {transition.label if transition else tid}:")
                print(f"  Input places: {input_places} with tokens: {input_tokens}")
                print(f"  Output places: {output_places} with tokens: {output_tokens}")
                print(f"  is_enabled: {self.is_enabled(tid)}")
                print(f"  can_fire: {self.can_fire(tid)}")
        return blocked
    
    def get_waiting_transitions(self) -> List[str]:
        """Vrátí seznam ID přechodů, které čekají na vstupy (nejsou aktivní)."""
        all_transitions = set(self.transitions.keys())
        enabled = set(self.get_enabled_transitions())
        waiting = list(all_transitions - enabled)
        
        # Filtrujeme jen ty, které mají alespoň jeden vstup (jinak jsou nevalidní)
        waiting_with_inputs = [
            tid for tid in waiting
            if self.get_input_places(tid)
        ]
        
        return waiting_with_inputs

