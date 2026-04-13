"""Simulační engine pro OPM diagramy."""
from __future__ import annotations
from typing import Dict, List, Optional, Callable
from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtWidgets import QApplication
from simulation.petri_net import PetriNet
from simulation.converter import build_petri_net_from_scene


class SimulationEngine(QObject):
    """Engine pro simulaci Petriho sítě."""
    
    # Signály pro komunikaci s UI
    marking_changed = Signal()  # Emitováno při změně označení
    transition_fired = Signal(str)  # Emitováno při provedení přechodu (transition_id)
    
    def __init__(self, scene):
        super().__init__()
        self.scene = scene
        self.net: Optional[PetriNet] = None
        self.is_running = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.simulation_speed = 1000  # ms mezi kroky
        
        # Mapování place_id -> grafické prvky pro vizualizaci
        self.place_to_items: Dict[str, List] = {}
        
    def build_net(self):
        """Vytvoří Petriho síť z aktuálního diagramu."""
        self.net = build_petri_net_from_scene(self.scene)
        self._build_place_mapping()
        self._initialize_initial_marking()
        self.marking_changed.emit()
        
    def _build_place_mapping(self):
        """Vytvoří mapování mezi místy a grafickými prvky."""
        if not self.net:
            return
            
        self.place_to_items = {}
        
        for place_id, place in self.net.places.items():
            items = []
            
            # Najdi objekt podle object_id
            from graphics.nodes import ObjectItem, StateItem

            if getattr(place, "is_hidden", False):
                self.place_to_items[place_id] = []
                print(f"[Simulator] Hidden place (no graphics): {place_id}")
                continue

            if getattr(place, "is_aggregate", False):
                for item in self.scene.items():
                    if isinstance(item, ObjectItem) and item.node_id == place.object_id:
                        items.append(item)
                        print(
                            f"[Simulator] Mapped aggregate place {place_id} to ObjectItem '{item.label}'"
                        )
                        break
                if not items:
                    print(
                        f"[Simulator] WARNING: ObjectItem for aggregate place {place_id} not found"
                    )
                self.place_to_items[place_id] = items
                continue
            
            # Projdi všechny top-level items ve scéně
            for item in self.scene.items():
                # Hledáme ObjectItem (top-level) nebo StateItem (child)
                if isinstance(item, ObjectItem) and item.node_id == place.object_id:
                    if place.state_label:
                        # Najdi stav mezi child items objektu
                        for child in item.childItems():
                            if isinstance(child, StateItem) and child.label == place.state_label:
                                items.append(child)
                                print(f"[Simulator] Mapped place {place_id} to StateItem '{child.label}' of object '{item.label}'")
                                break
                        else:
                            print(f"[Simulator] WARNING: StateItem '{place.state_label}' not found for object '{item.label}' (place {place_id})")
                    else:
                        # Objekt bez stavu
                        items.append(item)
                        print(f"[Simulator] Mapped place {place_id} to ObjectItem '{item.label}'")
            
            # Pokud jsme nenašli žádné itemy, zkusme najít StateItem přímo
            # (pro případ, že StateItem je top-level item, což by nemělo být, ale pro jistotu)
            if not items and place.state_label:
                for item in self.scene.items():
                    if isinstance(item, StateItem):
                        parent = item.parentItem()
                        if parent and isinstance(parent, ObjectItem) and parent.node_id == place.object_id:
                            if item.label == place.state_label:
                                items.append(item)
                                print(f"[Simulator] Mapped place {place_id} to StateItem '{item.label}' (found directly)")
                                break
                        
            if not items and not getattr(place, "is_hidden", False):
                print(f"[Simulator] WARNING: No items found for place {place_id} (object_id={place.object_id}, state_label={place.state_label})")
                        
            self.place_to_items[place_id] = items
            
    def _initialize_initial_marking(self):
        """Inicializuje počáteční označení sítě.
        
        Pro OPM: objekty s explicitně definovaným počátečním stavem mají token.
        Pro jednoduchost: všechny stavy mají token (později lze upravit).
        """
        if not self.net:
            return
            
        # Pro C/E sítě: můžeme nastavit počáteční tokeny
        # Pro OPM: inicializujeme podle prvního stavu objektu nebo explicitně
        # Zatím: žádné tokeny (prázdné označení)
        for place_id in self.net.places.keys():
            self.net.set_token(place_id, False)
            
    def set_initial_tokens(self, place_ids: List[str]):
        """Nastaví počáteční tokeny na zadaných místech."""
        if not self.net:
            return
            
        for place_id in self.net.places.keys():
            self.net.set_token(place_id, place_id in place_ids)
            
        self.marking_changed.emit()
        
    def start(self):
        """Spustí simulaci."""
        if not self.net:
            self.build_net()
            
        self.is_running = True
        self.timer.start(self.simulation_speed)
        
    def stop(self):
        """Zastaví simulaci."""
        self.is_running = False
        self.timer.stop()
        
    def step(self):
        """Provede jeden simulační krok (jednofázový průchod).
        
        Najde první přechod, který může proběhnout, a provede ho najednou.
        """
        if not self.net:
            print("[Simulator] No net built")
            return False
        
        # Najdeme všechny přechody, které mohou proběhnout
        fireable = self.net.get_fireable_transitions()
        if not fireable:
            print(f"[Simulator] No fireable transitions")
            return False  # Žádný přechod nemůže proběhnout
            
        # Vybereme první přechod, který může proběhnout (lze změnit na náhodný výběr)
        transition_id = fireable[0]
        print(f"[Simulator] Firing transition: {transition_id}")

        # 1) Najdeme výstupní místa, která patří objektům se "složenými" cílovými stavy.
        output_places = self.net.get_output_places(transition_id)
        output_place_objs: Dict[str, List] = {}
        for pid in output_places:
            place = self.net.places.get(pid)
            if not place:
                continue
            if place.state_label is None:
                continue
            output_place_objs.setdefault(place.object_id, []).append(pid)

        ambiguous_object_ids = {
            object_id
            for object_id, place_ids in output_place_objs.items()
            if len(place_ids) > 1
        }

        # 2) Před samotným přesunem tokenu se uživatele zeptáme na cílové stavy.
        #    U objektů bez více stavů nebo s jedním stavem vybereme vše.
        selected_place_ids: set[str] = set()

        # Place_id pro výstupní objekty se stavy
        input_place_ids = set(self.net.get_input_places(transition_id))

        # Připravíme automatické vybrání pro "ne-ambiguos" výstupy
        for pid in output_places:
            place = self.net.places.get(pid)
            if not place:
                continue
            # Objekt bez stavů — jedno místo (není agregát)
            if place.state_label is None and not getattr(place, "is_aggregate", False):
                selected_place_ids.add(pid)
                continue
            # Jeden cílový stav u daného objektu — není mezi ambiguous
            if place.state_label is not None and place.object_id not in ambiguous_object_ids:
                selected_place_ids.add(pid)
                continue

        # Cache objektových labelů pro dialog
        if not hasattr(self, "_object_label_cache"):
            self._object_label_cache: Dict[str, str] = {}

        def get_object_label(object_id: str) -> str:
            if object_id in self._object_label_cache:
                return self._object_label_cache[object_id]
            from graphics.nodes import ObjectItem
            label = object_id
            for item in self.scene.items():
                if isinstance(item, ObjectItem) and getattr(item, "node_id", None) == object_id:
                    label = getattr(item, "label", object_id)
                    break
            self._object_label_cache[object_id] = label
            return label

        # Pro každý ambiguos objekt spustíme dialog postupně
        if ambiguous_object_ids:
            from ui.dialogs import ObjectStateSelectionDialog

            for object_id in sorted(ambiguous_object_ids):
                candidate_pids = output_place_objs.get(object_id, [])
                # Seřadíme stavy stabilně podle state_label
                candidate_place_ids = sorted(
                    candidate_pids,
                    key=lambda pid: (self.net.places.get(pid).state_label or "")
                )

                state_entries = []
                for pid in candidate_place_ids:
                    place = self.net.places.get(pid)
                    if not place or place.state_label is None:
                        continue
                    # Disabled checkbox pokud místo už má token a nebude odebráno tímto přechodem
                    enabled = (not self.net.has_token(pid)) or (pid in input_place_ids)
                    state_entries.append((place.state_label, pid, enabled))

                if not state_entries:
                    continue

                dlg = ObjectStateSelectionDialog(
                    object_label=get_object_label(object_id),
                    state_entries=state_entries,
                    parent=QApplication.activeWindow(),
                )

                from PySide6.QtWidgets import QDialog
                if dlg.exec() != QDialog.Accepted:
                    print(f"[Simulator] Selection cancelled for object {object_id}")
                    return False

                selected_from_dialog = dlg.get_selected_place_ids()
                selected_place_ids.update(selected_from_dialog)

        # 3) Teď teprve provedeme fázi 1 (odebrání tokenů z inputů)
        if not self.net.activate_transition(transition_id):
            print(f"[Simulator] Failed to activate transition: {transition_id}")
            return False

        # 4) A dokončíme fázi 2: přidáme tokeny jen do vybraných output míst
        if not self.net.complete_transition_selected(transition_id, list(selected_place_ids)):
            print(f"[Simulator] Failed to complete transition with selected outputs: {transition_id}")
            return False

        print(f"[Simulator] Transition fired successfully")
        self.transition_fired.emit(transition_id)
        self.marking_changed.emit()
        return True
        
    def _step(self):
        """Interní krok pro timer."""
        if not self.step():
            # Pokud není žádný přechod, zastav simulaci
            self.stop()
            
    def reset(self):
        """Resetuje simulaci na počáteční stav."""
        self.stop()
        if self.net:
            # Resetujeme na prázdné označení
            for place_id in self.net.places.keys():
                self.net.set_token(place_id, False)
            self.marking_changed.emit()
            
    def get_marking(self) -> Dict[str, bool]:
        """Vrátí aktuální označení sítě."""
        if not self.net:
            return {}
        return {pid: self.net.has_token(pid) for pid in self.net.places.keys()}
        
    def get_enabled_transitions(self) -> List[str]:
        """Vrátí seznam ID aktivních přechodů."""
        if not self.net:
            return []
        return self.net.get_enabled_transitions()
        
    def get_fireable_transitions(self) -> List[str]:
        """Vrátí seznam ID přechodů, které mohou proběhnout."""
        if not self.net:
            return []
        return self.net.get_fireable_transitions()
        
    def get_blocked_transitions(self) -> List[str]:
        """Vrátí seznam ID blokovaných přechodů (procesní zádrhely)."""
        if not self.net:
            return []
        return self.net.get_blocked_transitions()
    
    def get_waiting_transitions(self) -> List[str]:
        """Vrátí seznam ID přechodů, které čekají na vstupy."""
        if not self.net:
            return []
        return self.net.get_waiting_transitions()

