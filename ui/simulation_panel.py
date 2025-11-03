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
        
        # Tlačítka ovládání
        controls_layout = QHBoxLayout()
        
        self.btn_build = QPushButton("Build Net", self)
        self.btn_build.clicked.connect(self._on_build_net)
        controls_layout.addWidget(self.btn_build)
        
        self.btn_reset = QPushButton("Reset", self)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_reset.setEnabled(False)
        controls_layout.addWidget(self.btn_reset)
        
        layout.addLayout(controls_layout)
        
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
        
        self.btn_set_tokens = QPushButton("Set Initial Tokens", self)
        self.btn_set_tokens.clicked.connect(self._on_set_tokens)
        self.btn_set_tokens.setEnabled(False)
        tokens_layout.addWidget(self.btn_set_tokens)
        
        self.group_tokens.setLayout(tokens_layout)
        layout.addWidget(self.group_tokens)
        
        # Seznam aktivních přechodů
        self.lbl_enabled = QLabel("Enabled transitions:", self)
        layout.addWidget(self.lbl_enabled)
        
        self.list_enabled = QListWidget(self)
        self.list_enabled.setMaximumHeight(100)
        layout.addWidget(self.list_enabled)
        
        # Seznam blokovaných přechodů (procesní zádrhely)
        self.lbl_blocked = QLabel("Blocked transitions (bottlenecks):", self)
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
            
    def _on_build_net(self):
        """Vytvoří Petriho síť z diagramu."""
        if not self.main_window or not self.main_window.scene:
            return
            
        if not self.simulator:
            self.simulator = SimulationEngine(self.main_window.scene)
            self.set_simulator(self.simulator)
            
        self.simulator.build_net()
        self.lbl_status.setText("Status: Built")
        self.btn_reset.setEnabled(True)
        self.btn_step.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.btn_set_tokens.setEnabled(True)
        self._build_tokens_list()
        self._update_lists()
        
    def _on_reset(self):
        """Resetuje simulaci."""
        if self.simulator:
            self.simulator.reset()
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
                    
        self._update_token_checkboxes()
        self._update_lists()
        
    def _on_transition_fired(self, transition_id: str):
        """Aktualizuje UI při provedení přechodu."""
        transition = self.simulator.net.transitions.get(transition_id)
        if transition:
            self.lbl_status.setText(f"Status: Fired {transition.label}")
            
    def _update_lists(self):
        """Aktualizuje seznamy aktivních a blokovaných přechodů."""
        if not self.simulator or not self.simulator.net:
            return
            
        # Aktualizuj seznam aktivních přechodů
        self.list_enabled.clear()
        enabled = self.simulator.get_enabled_transitions()
        for tid in enabled:
            transition = self.simulator.net.transitions.get(tid)
            if transition:
                item = QListWidgetItem(transition.label)
                self.list_enabled.addItem(item)
                
        # Aktualizuj seznam blokovaných přechodů (procesní zádrhely)
        self.list_blocked.clear()
        blocked = self.simulator.get_blocked_transitions()
        for tid in blocked:
            transition = self.simulator.net.transitions.get(tid)
            if transition:
                item = QListWidgetItem(transition.label)
                item.setForeground(Qt.red)  # Červeně pro zádrhely
                self.list_blocked.addItem(item)
    
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
            self.token_checkboxes[place_id] = checkbox
            self.tokens_layout.insertWidget(self.tokens_layout.count() - 1, checkbox)  # Před stretch
            
        self.group_tokens.setVisible(len(self.token_checkboxes) > 0)
        
    def _on_set_tokens(self):
        """Nastaví počáteční tokeny podle checkboxů."""
        if not self.simulator or not self.simulator.net:
            return
            
        # Zjistíme, která místa mají být označena
        place_ids_with_tokens = [
            place_id for place_id, checkbox in self.token_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        # Nastavíme tokeny
        self.simulator.set_initial_tokens(place_ids_with_tokens)
        self.lbl_status.setText(f"Status: Tokens set ({len(place_ids_with_tokens)} places)")
    
    def _update_token_checkboxes(self):
        """Aktualizuje checkboxy podle aktuálního označení sítě."""
        if not self.simulator or not self.simulator.net:
            return
            
        marking = self.simulator.get_marking()
        for place_id, checkbox in self.token_checkboxes.items():
            has_token = marking.get(place_id, False)
            checkbox.setChecked(has_token)

