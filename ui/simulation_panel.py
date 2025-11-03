"""Panel pro ovládání simulace OPM diagramu."""
from __future__ import annotations
from typing import Optional, Dict
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QScrollArea,
    QGroupBox,
)
from simulation.simulator import SimulationEngine


class SimulationPanel(QDockWidget):
    """Dock widget pro ovládání simulace."""
    
    def __init__(self, parent=None):
        super().__init__("Simulation", parent)
        self.main_window = parent
        self.simulator: Optional[SimulationEngine] = None
        self.token_checkboxes: Dict[str, QCheckBox] = {}  # place_id -> checkbox
        self._init_ui()
        
    def _init_ui(self):
        """Inicializace UI panelu."""
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        
        # Tlačítko Reset (build + reset)
        self.btn_reset = QPushButton("Reset", self)
        self.btn_reset.clicked.connect(self._on_reset)
        layout.addWidget(self.btn_reset)
        
        # Tlačítka pro simulaci
        sim_layout = QHBoxLayout()
        
        self.btn_step = QPushButton("Step", self)
        self.btn_step.clicked.connect(self._on_step)
        self.btn_step.setEnabled(False)
        sim_layout.addWidget(self.btn_step)
        
        self.btn_play = QPushButton("Play", self)
        self.btn_play.clicked.connect(self._on_play)
        self.btn_play.setEnabled(False)
        sim_layout.addWidget(self.btn_play)
        
        self.btn_pause = QPushButton("Pause", self)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_pause.setEnabled(False)
        sim_layout.addWidget(self.btn_pause)
        
        layout.addLayout(sim_layout)
        
        # Informace o stavu
        self.lbl_status = QLabel("Status: Not built", self)
        layout.addWidget(self.lbl_status)
        
        # Skupina pro nastavení počátečních tokenů
        self.group_tokens = QGroupBox("Initial Tokens", self)
        self.group_tokens.setVisible(False)
        tokens_layout = QVBoxLayout()
        
        self.scroll_tokens = QScrollArea(self)
        self.scroll_tokens.setWidgetResizable(True)
        self.scroll_tokens.setMaximumHeight(150)
        
        self.tokens_widget = QWidget()
        self.tokens_layout = QVBoxLayout(self.tokens_widget)
        self.tokens_layout.addStretch()
        self.scroll_tokens.setWidget(self.tokens_widget)
        
        tokens_layout.addWidget(self.scroll_tokens)
        
        self.group_tokens.setLayout(tokens_layout)
        layout.addWidget(self.group_tokens)
        
        # Seznam aktivních přechodů (ty, které mohou proběhnout)
        self.lbl_enabled = QLabel("Ready to fire (green):", self)
        layout.addWidget(self.lbl_enabled)
        
        self.list_enabled = QListWidget(self)
        self.list_enabled.setMaximumHeight(100)
        layout.addWidget(self.list_enabled)
        
        # Seznam čekajících přechodů (čekají na vstupy)
        self.lbl_waiting = QLabel("Waiting for inputs (yellow):", self)
        layout.addWidget(self.lbl_waiting)
        
        self.list_waiting = QListWidget(self)
        self.list_waiting.setMaximumHeight(100)
        layout.addWidget(self.list_waiting)
        
        # Seznam blokovaných přechodů (procesní zádrhely)
        self.lbl_blocked = QLabel("Blocked transitions (bottlenecks - red):", self)
        layout.addWidget(self.lbl_blocked)
        
        self.list_blocked = QListWidget(self)
        self.list_blocked.setMaximumHeight(100)
        layout.addWidget(self.list_blocked)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        self.setWidget(widget)
        
    def set_simulator(self, simulator: SimulationEngine):
        """Nastaví simulátor a připojí signály."""
        self.simulator = simulator
        if simulator:
            simulator.marking_changed.connect(self._on_marking_changed)
            simulator.transition_fired.connect(self._on_transition_fired)
            # Vytvoříme vlastní wrapper pro emitování signálu
            self.marking_changed = lambda: simulator.marking_changed.emit()
            
    def _on_reset(self):
        """Vytvoří Petriho síť z diagramu a resetuje simulaci."""
        if not self.main_window or not self.main_window.scene:
            return
            
        if not self.simulator:
            self.simulator = SimulationEngine(self.main_window.scene)
            self.set_simulator(self.simulator)
            
        # Vytvoří nebo obnoví síť
        self.simulator.build_net()
        self.lbl_status.setText("Status: Built")
        self.btn_step.setEnabled(True)
        self.btn_play.setEnabled(True)
        self._build_tokens_list()
        
        # Resetuje tokeny na prázdné
        if self.simulator.net:
            for place_id in self.simulator.net.places.keys():
                self.simulator.net.set_token(place_id, False)
            if hasattr(self, 'marking_changed'):
                self.marking_changed()
        
        self._update_token_checkboxes()
        self._update_lists()
            
    def _on_step(self):
        """Provede jeden krok simulace."""
        if self.simulator:
            result = self.simulator.step()
            if not result:
                # Pokud není žádný přechod, zobrazíme zprávu
                self.lbl_status.setText("Status: No transitions available")
            
    def _on_play(self):
        """Spustí kontinuální simulaci."""
        if self.simulator:
            self.simulator.start()
            self.btn_play.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_step.setEnabled(False)
            self.lbl_status.setText("Status: Running")
            
    def _on_pause(self):
        """Pozastaví simulaci."""
        if self.simulator:
            self.simulator.stop()
            self.btn_play.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_step.setEnabled(True)
            self.lbl_status.setText("Status: Paused")
            
    def _on_marking_changed(self):
        """Aktualizuje vizualizaci při změně označení."""
        if not self.simulator or not self.simulator.net:
            return
            
        # Aktualizuj vizualizaci tokenů
        marking = self.simulator.get_marking()
        
        for place_id, has_token in marking.items():
            place = self.simulator.net.places.get(place_id)
            if not place:
                continue
                
            # Najdi grafické prvky pro toto místo
            items = self.simulator.place_to_items.get(place_id, [])
            for item in items:
                if hasattr(item, 'has_token'):
                    item.has_token = has_token
                    # Přinutíme aktualizaci scény
                    if item.scene():
                        item.scene().update(item.boundingRect())
                    item.update()  # Překresli
        
        # Aktualizujeme checkboxy (bez emitování signálu, aby se nezacyklil)
        self._update_token_checkboxes_silent()
        self._update_lists()
    
    def marking_changed(self):
        """Wrapper pro emitování signálu marking_changed."""
        # Tato metoda se volá místo přímého emitování signálu
        # aby se zabránilo zacyklení
        if self.simulator:
            self.simulator.marking_changed.emit()
        
    def _on_transition_fired(self, transition_id: str):
        """Aktualizuje UI při provedení přechodu."""
        transition = self.simulator.net.transitions.get(transition_id)
        if transition:
            self.lbl_status.setText(f"Status: Fired {transition.label}")
            
    def _update_lists(self):
        """Aktualizuje seznamy aktivních, čekajících a blokovaných přechodů."""
        if not self.simulator or not self.simulator.net:
            return
            
        # Získáme všechny seznamy
        enabled = self.simulator.get_enabled_transitions()
        fireable = self.simulator.get_fireable_transitions()
        blocked = self.simulator.get_blocked_transitions()
        waiting = self.simulator.get_waiting_transitions()
        
        print(f"[UI] Enabled transitions: {enabled}")
        print(f"[UI] Fireable transitions: {fireable}")
        print(f"[UI] Blocked transitions: {blocked}")
        print(f"[UI] Waiting transitions: {waiting}")
        
        # Aktualizuj seznam aktivních přechodů (jen ty, které mohou proběhnout)
        self.list_enabled.clear()
        for tid in fireable:
            transition = self.simulator.net.transitions.get(tid)
            if transition:
                item = QListWidgetItem(transition.label)
                item.setForeground(Qt.green)  # Zeleně pro ready-to-fire
                self.list_enabled.addItem(item)
        
        # Aktualizuj seznam čekajících přechodů (čekají na vstupy)
        self.list_waiting.clear()
        for tid in waiting:
            transition = self.simulator.net.transitions.get(tid)
            if transition:
                item = QListWidgetItem(transition.label)
                item.setForeground(Qt.darkYellow)  # Žlutě pro čekající
                self.list_waiting.addItem(item)
                
        # Aktualizuj seznam blokovaných přechodů (procesní zádrhely)
        self.list_blocked.clear()
        for tid in blocked:
            transition = self.simulator.net.transitions.get(tid)
            if transition:
                item = QListWidgetItem(transition.label)
                item.setForeground(Qt.red)  # Červeně pro zádrhely
                self.list_blocked.addItem(item)
                
        # Pokud není žádný blokovaný, ale jsou enabled, zobrazíme informaci
        if not blocked and enabled:
            print(f"[UI] All enabled transitions are fireable (no bottlenecks)")
        elif not blocked and not enabled:
            print(f"[UI] No enabled transitions")
    
    def _build_tokens_list(self):
        """Vytvoří seznam checkboxů pro nastavení počátečních tokenů."""
        if not self.simulator or not self.simulator.net:
            return
            
        # Odstraníme staré checkboxy
        for checkbox in self.token_checkboxes.values():
            self.tokens_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.token_checkboxes.clear()
        
        # Vytvoříme nové checkboxy pro každé místo
        for place_id, place in sorted(self.simulator.net.places.items(), key=lambda x: x[1].label):
            checkbox = QCheckBox(place.label, self.tokens_widget)
            checkbox.setChecked(False)  # Výchozí: žádný token
            # Připojíme signál pro automatické nastavení tokenu při změně
            checkbox.stateChanged.connect(
                lambda checked, pid=place_id: self._on_token_checkbox_changed(pid, checked)
            )
            self.token_checkboxes[place_id] = checkbox
            self.tokens_layout.insertWidget(self.tokens_layout.count() - 1, checkbox)  # Před stretch
            
        self.group_tokens.setVisible(len(self.token_checkboxes) > 0)
    
    def _on_token_checkbox_changed(self, place_id: str, checked: int):
        """Automaticky nastaví token při změně checkboxu."""
        if not self.simulator or not self.simulator.net:
            return
            
        # checked je Qt.Checked (2) nebo Qt.Unchecked (0)
        has_token = (checked == 2)
        
        # Nastavíme token v místě
        self.simulator.net.set_token(place_id, has_token)
        
        # Aktualizujeme vizualizaci
        if hasattr(self, 'marking_changed'):
            self.marking_changed()
        
        # Aktualizujeme status
        marking = self.simulator.get_marking()
        token_count = sum(1 for has_token in marking.values() if has_token)
        self.lbl_status.setText(f"Status: {token_count} token(s) set")
        
        # Aktualizujeme seznamy přechodů (aby se zobrazily blokované přechody)
        self._update_lists()
    
    def _update_token_checkboxes(self):
        """Aktualizuje checkboxy podle aktuálního označení sítě."""
        self._update_token_checkboxes_silent()
    
    def _update_token_checkboxes_silent(self):
        """Aktualizuje checkboxy bez emitování signálů (aby se nezacyklil)."""
        if not self.simulator or not self.simulator.net:
            return
            
        marking = self.simulator.get_marking()
        for place_id, checkbox in self.token_checkboxes.items():
            has_token = marking.get(place_id, False)
            # Dočasně odpojíme signál, aby se nezacyklil
            checkbox.blockSignals(True)
            checkbox.setChecked(has_token)
            checkbox.blockSignals(False)

