"""Panel pro ovládání simulace OPM diagramu."""
from __future__ import annotations
from typing import Optional, Dict, List, Tuple
import io
from PySide6.QtCore import Qt, QTimer, QRectF, QBuffer, QIODevice
from PySide6.QtGui import QImage, QPainter
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
    QSpinBox,
    QFileDialog,
    QMessageBox,
)
from simulation.simulator import SimulationEngine
from simulation.petri_net import Place


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
        
        # Delay mezi kroky simulace (pro export GIF)
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay (ms):", self))
        self.spin_delay = QSpinBox(self)
        self.spin_delay.setMinimum(50)
        self.spin_delay.setMaximum(5000)
        self.spin_delay.setValue(500)
        self.spin_delay.setSuffix(" ms")
        self.spin_delay.setToolTip("Delay between simulation steps for GIF export")
        delay_layout.addWidget(self.spin_delay)
        layout.addLayout(delay_layout)
        
        # Tlačítko pro export simulace jako GIF
        self.btn_export_gif = QPushButton("Export Simulation as GIF", self)
        self.btn_export_gif.clicked.connect(self._on_export_gif)
        self.btn_export_gif.setEnabled(False)
        layout.addWidget(self.btn_export_gif)
        
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
            print("[UI] WARNING: Cannot reset - no main_window or scene")
            return
        
        # Vždy aktualizujeme referenci na scénu (může se změnit po importu JSONu)
        if not self.simulator:
            self.simulator = SimulationEngine(self.main_window.scene)
            self.set_simulator(self.simulator)
        else:
            # Aktualizujeme referenci na scénu (může se změnit po importu)
            self.simulator.scene = self.main_window.scene
        
        print(f"[UI] Resetting simulation. Scene has {len(self.main_window.scene.items())} items")
        
        # Vytvoří nebo obnoví síť
        self.simulator.build_net()
        
        if not self.simulator.net:
            print("[UI] ERROR: Failed to build Petri net")
            self.lbl_status.setText("Status: Build failed")
            return
        
        print(f"[UI] Petri net built: {len(self.simulator.net.places)} places, {len(self.simulator.net.transitions)} transitions")
        print(f"[UI] Place mapping: {len(self.simulator.place_to_items)} mappings")
        
        self.lbl_status.setText("Status: Built")
        self.btn_step.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.btn_export_gif.setEnabled(True)
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
            if not items:
                print(f"[UI] WARNING: No items found for place {place_id} ({place.label})")
                # Zkusme znovu vytvořit mapování pro tento place
                # (může se stát, že se přidaly stavy po vytvoření sítě)
                self.simulator._build_place_mapping()
                items = self.simulator.place_to_items.get(place_id, [])
                if items:
                    print(f"[UI] Rebuilt mapping, found {len(items)} items")
                else:
                    print(f"[UI] Still no items after rebuild, skipping")
                    continue
            else:
                print(f"[UI] Updating token for place {place_id} ({place.label}): has_token={has_token}, items={len(items)}")
            
            # Kontrola: pokud má place state_label=None, ale objekt má stavy, varování
            if place.state_label is None and items:
                from graphics.nodes import ObjectItem, StateItem
                for item in items:
                    if isinstance(item, ObjectItem):
                        states = [ch for ch in item.childItems() if isinstance(ch, StateItem)]
                        if states:
                            print(f"[UI] WARNING: Place {place_id} is for object without states, but object '{item.label}' has {len(states)} states. Please press Reset to rebuild the network.")
            
            for item in items:
                if hasattr(item, 'has_token'):
                    from graphics.nodes import ObjectItem, StateItem
                    item_type = "StateItem" if isinstance(item, StateItem) else "ObjectItem" if isinstance(item, ObjectItem) else "Unknown"
                    print(f"[UI] Setting has_token={has_token} on {item_type} '{item.label if hasattr(item, 'label') else 'N/A'}'")
                    item.has_token = has_token
                    # Přinutíme aktualizaci scény
                    # Pro child items (např. StateItem) musíme použít mapToScene
                    # aby se správně aktualizovala oblast ve scénových souřadnicích
                    if item.scene():
                        # Získej bounding rect ve scénových souřadnicích
                        scene_rect = item.mapToScene(item.boundingRect()).boundingRect()
                        item.scene().update(scene_rect)
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
        
        # Seskupte místa podle objektu pro lepší organizaci
        places_by_object: Dict[str, List[Tuple[str, Place]]] = {}
        for place_id, place in self.simulator.net.places.items():
            obj_id = place.object_id
            if obj_id not in places_by_object:
                places_by_object[obj_id] = []
            places_by_object[obj_id].append((place_id, place))
        
        print(f"[UI] Building token checkboxes for {len(self.simulator.net.places)} places across {len(places_by_object)} objects")
        
        # Vytvoříme checkboxy seskupené podle objektu
        # Seřadíme objekty podle názvu
        for obj_id in sorted(places_by_object.keys(), key=lambda oid: places_by_object[oid][0][1].label.split(" at state")[0]):
            places = places_by_object[obj_id]
            # Seřadíme místa - nejdřív objekt bez stavu, pak stavy
            places.sort(key=lambda p: (p[1].state_label is None, p[1].state_label or ""))
            
            for place_id, place in places:
                checkbox = QCheckBox(place.label, self.tokens_widget)
                checkbox.setChecked(False)  # Výchozí: žádný token
                # Připojíme signál pro automatické nastavení tokenu při změně
                checkbox.stateChanged.connect(
                    lambda checked, pid=place_id: self._on_token_checkbox_changed(pid, checked)
                )
                self.token_checkboxes[place_id] = checkbox
                self.tokens_layout.insertWidget(self.tokens_layout.count() - 1, checkbox)  # Před stretch
                print(f"[UI] Added checkbox for place {place_id}: {place.label}")
            
        self.group_tokens.setVisible(len(self.token_checkboxes) > 0)
        print(f"[UI] Total checkboxes created: {len(self.token_checkboxes)}")
    
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
    
    def _on_export_gif(self):
        """Exportuje simulaci jako GIF animaci."""
        if not self.simulator or not self.simulator.net:
            QMessageBox.warning(self, "Export Error", "Simulation not built. Please press Reset first.")
            return
        
        # Vybereme soubor pro uložení
        from persistence.json_io import safe_base_filename
        base = safe_base_filename(self.main_window._current_tab_title() if hasattr(self.main_window, '_current_tab_title') else None)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Simulation GIF", f"{base}_simulation.gif", "GIF (*.gif)"
        )
        if not path:
            return
        
        # Uložíme počáteční stav
        initial_marking = self.simulator.get_marking().copy()
        
        # Získáme delay mezi kroky
        delay_ms = self.spin_delay.value()
        delay_seconds = delay_ms / 1000.0
        
        try:
            # Zkusíme použít imageio pro vytvoření GIF
            try:
                import imageio
                use_imageio = True
            except ImportError:
                # Zkusíme pillow
                try:
                    from PIL import Image
                    use_imageio = False
                except ImportError:
                    QMessageBox.warning(
                        self, "Export Error",
                        "Please install imageio or pillow:\n"
                        "pip install imageio\n"
                        "or\n"
                        "pip install pillow"
                    )
                    return
            
            # Získáme scénu pro export
            if not self.main_window or not hasattr(self.main_window, 'scene'):
                QMessageBox.warning(self, "Export Error", "Cannot access scene. Please ensure the main window is available.")
                return
            
            scene = self.main_window.scene
            rb = scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            
            # Vypneme mřížku pro export
            original_grid_state = scene._draw_grid
            scene.set_draw_grid(False)
            
            frames = []
            max_steps = 100  # Maximální počet kroků pro zabránění zacyklení
            
            self.lbl_status.setText("Status: Recording...")
            self.btn_export_gif.setEnabled(False)
            
            # Uložíme první snímek (počáteční stav)
            img = self._capture_frame(scene, rb)
            frames.append(img)
            
            # Provedeme simulaci krok za krokem
            step_count = 0
            while step_count < max_steps:
                # Provedeme jeden krok
                result = self.simulator.step()
                if not result:
                    # Žádný další krok není možný
                    break
                
                # Aktualizujeme UI
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
                
                # Počkáme na delay (pro vizualizaci)
                from PySide6.QtCore import QEventLoop, QTimer as QtTimer
                loop = QEventLoop()
                QtTimer.singleShot(delay_ms, loop.quit)
                loop.exec()
                
                # Uložíme snímek
                img = self._capture_frame(scene, rb)
                frames.append(img)
                step_count += 1
                
                # Aktualizujeme UI znovu
                QApplication.processEvents()
            
            # Vrátíme počáteční stav
            for place_id, has_token in initial_marking.items():
                self.simulator.net.set_token(place_id, has_token)
            self.simulator.marking_changed.emit()
            
            # Vrátíme původní stav mřížky
            scene.set_draw_grid(original_grid_state)
            
            # Vytvoříme GIF
            import numpy as np
            if use_imageio:
                # imageio - očekává numpy arrays
                imageio.mimsave(path, frames, duration=delay_seconds, loop=0)
            else:
                # pillow - očekává PIL Images
                if frames:
                    # Převod numpy arrays na PIL Images
                    from PIL import Image
                    pil_frames = [Image.fromarray(frame) if isinstance(frame, np.ndarray) else frame for frame in frames]
                    
                    if pil_frames:
                        pil_frames[0].save(
                            path,
                            save_all=True,
                            append_images=pil_frames[1:] if len(pil_frames) > 1 else [],
                            duration=delay_ms,
                            loop=0
                        )
            
            QMessageBox.information(
                self, "Export Complete",
                f"Simulation exported as GIF:\n{path}\n\n{len(frames)} frames recorded."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export GIF:\n{str(e)}")
            # Vrátíme počáteční stav i při chybě
            if self.simulator and self.simulator.net:
                for place_id, has_token in initial_marking.items():
                    self.simulator.net.set_token(place_id, has_token)
                self.simulator.marking_changed.emit()
            if hasattr(scene, 'set_draw_grid'):
                scene.set_draw_grid(original_grid_state)
        finally:
            self.lbl_status.setText("Status: Export complete")
            self.btn_export_gif.setEnabled(True)
    
    def _capture_frame(self, scene, bounding_rect):
        """Zachytí jeden snímek scény jako QImage a převede na formát pro GIF."""
        img = QImage(int(bounding_rect.width()), int(bounding_rect.height()), QImage.Format_ARGB32_Premultiplied)
        img.fill(0x00FFFFFF)
        painter = QPainter(img)
        scene.render(painter, target=QRectF(0, 0, bounding_rect.width(), bounding_rect.height()), source=bounding_rect)
        painter.end()
        
        # Převedeme QImage na formát použitelný pro GIF
        # QImage -> RGB format
        img_rgb = img.convertToFormat(QImage.Format_RGB888)
        width = img_rgb.width()
        height = img_rgb.height()
        
        # Převedeme na numpy array pomocí bytes
        import numpy as np
        
        # Převedeme QImage na numpy array pomocí buffer metody
        # (nejspolehlivější způsob)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        img_rgb.save(buffer, "PNG")
        buffer.close()
        
        # Načteme data pomocí Pillow nebo imageio
        try:
            from PIL import Image
            pil_img = Image.open(io.BytesIO(buffer.data()))
            arr = np.array(pil_img)
            # Pokud je to RGBA, převedeme na RGB
            if arr.shape[2] == 4:
                arr = arr[:, :, :3]
        except ImportError:
            # Pokud není PIL, použijeme imageio
            try:
                import imageio
                arr = imageio.imread(io.BytesIO(buffer.data()))
                # Pokud je to RGBA, převedeme na RGB
                if len(arr.shape) == 3 and arr.shape[2] == 4:
                    arr = arr[:, :, :3]
            except ImportError:
                # Fallback: přímá konverze z QImage (méně spolehlivá)
                byte_data = img_rgb.bits()
                if byte_data:
                    byte_data.setsize(img_rgb.byteCount())
                    arr = np.frombuffer(byte_data, dtype=np.uint8, count=width * height * 3)
                    arr = arr.reshape((height, width, 3))
                else:
                    raise RuntimeError("Cannot convert QImage to numpy array")
        
        # Vracíme numpy array (použijeme ho pro imageio i pillow)
        return arr

