"""Grafické prvky pro uzly diagramu (objekty, procesy, stavy).

Implementuje tři typy uzlů:
- ObjectItem: Obdélník se zaoblenými rohy (zelený obrys)
- ProcessItem: Elipsa (modrý obrys)
- StateItem: Malý obdélník uvnitř objektu (hnědý obrys)
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QBrush, QPen, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem, QStyle
)
from utils.ids import next_id
from graphics.resize import ResizableMixin


class BaseNodeItem:
    """
    Společná funkc ionalita pro všechny typy uzlů.
    
    Zajišťuje:
    - Inicializaci node_id a labelu
    - Nastavení flagů (movable, selectable)
    - Aktualizaci vazeb při změně pozice
    - Zobrazení/skrytí resize handles
    """
    def init_node(self, kind: str, label: str):
        self.kind = kind
        self.node_id = next_id(kind)
        self.label = label
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def itemChange(self, change, value):
        res = super().itemChange(change, value)

        if change == QGraphicsItem.ItemSelectedHasChanged:
            # zobraz/skrýj táhla podle výběru – jen pokud mixin existuje
            if hasattr(self, "_set_handles_visible"):
                self._set_handles_visible(bool(self.isSelected()))
            print(f"[Node] {self.kind} '{self.label}' selection changed: {bool(self.isSelected())}")
            self.update()

        if change in (
            QGraphicsItem.ItemPositionHasChanged,
            QGraphicsItem.ItemPositionChange,
            QGraphicsItem.ItemSceneHasChanged,
        ):
            # přepočet rozložení táhel – jen pokud mixin existuje
            if hasattr(self, "_layout_handles"):
                self._layout_handles()

            # přepočítej napojené linky
            for ln in getattr(self, "_links", []) or []:
                ln.update_path()

        return res

    def set_label(self, text: str):
        if text == self.label:
            return
        self.label = text
        self.update()


class ObjectItem(ResizableMixin, BaseNodeItem, QGraphicsRectItem):
    """
    Grafická reprezentace objektu v OPM diagramu.
    
    Vizuální znaky:
    - Obdélník s rovnými rohy
    - Zelený obrys (0, 128, 0)
    - Bílá výplň
    - Může obsahovat stavy (StateItem jako potomky)
    - Podporuje změnu velikosti pomocí resize handles
    - Může zobrazovat token (červený kruh) pro simulaci (pouze pokud nemá stavy)
    """
    def __init__(self, rect: QRectF, label: str = "Object", essence: str = "informatical", affiliation: str = "systemic"):
        super().__init__(rect)
        self.init_node("object", label)
        self.essence = essence  # "physical" nebo "informatical"
        self.affiliation = affiliation  # "systemic" nebo "environmental"
        self.parent_process_id = None  # ID procesu, jehož in-zoom view obsahuje tento objekt
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(QColor(0, 128, 0), 2))  # Tmavě zelený obrys
        self._init_resize()  # Přidá resize handles
        
        # Simulace: token v místě (pouze pro objekty bez stavů)
        self.has_token = False

    def boundingRect(self) -> QRectF:
        m = 8
        return super().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter: QPainter, option, widget=None):
        # Nastavení pera podle affiliation
        pen = QPen(self.pen())
        if self.affiliation == "environmental":
            pen.setStyle(Qt.DashLine)
        else:
            pen.setStyle(Qt.SolidLine)
        
        # Stín pro fyzické objekty
        if self.essence == "physical":
            shadow_offset = 8
            painter.setBrush(QColor(80, 80, 80, 120))
            painter.setPen(Qt.NoPen)
            painter.drawRect(self.rect().adjusted(shadow_offset, shadow_offset, shadow_offset, shadow_offset))
        
        painter.setPen(pen)
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

        # dostupná oblast pro text (pokud má stavy, posuneme text nahoru)
        states = [ch for ch in self.childItems() if isinstance(ch, StateItem)]
        rect_for_text = self.rect()
        text_alignment = Qt.AlignCenter  # výchozí: uprostřed
        if states:
            st_h = states[0].rect().height() + 6  # výška stavů + mezera
            top_offset = 4  # odsazení od horního okraje (aby text nebyl přímo u okraje)
            rect_for_text = rect_for_text.adjusted(0, top_offset, 0, -st_h)
            text_alignment = Qt.AlignTop | Qt.AlignHCenter  # u horního konce, horizontálně uprostřed

        # text (tučný Arial, černý)
        font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(font)
        painter.setPen(Qt.black)
        painter.drawText(rect_for_text, text_alignment, self.label)
        
        # Vykresli token (červený kruh) pokud má objekt token a nemá stavy
        if self.has_token and not states:
            token_rect = QRectF(self.rect().right() - 16, self.rect().top() + 4, 12, 12)
            token_red = QColor(220, 50, 50)  # Výrazná, ale ne agresivní červená
            painter.setBrush(QBrush(token_red))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(token_rect)

        if option.state & QStyle.State_Selected:
            sel = QPen(Qt.blue, 2, Qt.DashLine)
            sel.setCosmetic(True)
            painter.setPen(sel)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect().adjusted(-6, -6, 6, 6))

    def mouseDoubleClickEvent(self, event):
        # dvojklik kamkoli do objektu = přidání stavu
        if event.button() == Qt.LeftButton:
            from ui.main_window import MainWindow  # lazy import, aby se nezacyklil
            main_win = MainWindow.instance()
            if main_win:
                main_win.add_state(self, event.scenePos())
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def setRect(self, rect: QRectF):
        """Zabrání zmenšení objektu tak, aby stavy vyčuhovaly ven."""
        states = [ch for ch in self.childItems() if isinstance(ch, StateItem)]
        if states:
            rightmost = max(st.mapToParent(st.rect().topRight()).x() for st in states)
            min_width = rightmost - rect.x() + 12  # +margin
            if rect.width() < min_width:
                rect.setWidth(min_width)

        super().setRect(rect)

    def itemChange(self, change, value):
        res = super().itemChange(change, value)

        if change == QGraphicsItem.ItemPositionHasChanged:
            # update linků objektu (už řeší BaseNodeItem)
            # navíc update linků jeho stavů
            for st in (ch for ch in self.childItems() if isinstance(ch, StateItem)):
                for ln in getattr(st, "_links", []) or []:
                    ln.update_path()

        return res

        # po změně rectu srovnej všechny stavy do řady dole
        #self._layout_states()

    def _layout_states(self):
        """Rozmístí všechny stavy do jedné řady dole podél spodní hrany objektu. - UZ ZBYTECNE (zatim nechavam)"""
        margin = 6
        r = self.rect()
        states = [ch for ch in self.childItems() if isinstance(ch, StateItem)]
        for idx, st in enumerate(states):
            w, h = st.rect().width(), st.rect().height()
            x = r.left() + margin + idx * (w + margin)
            y = r.bottom() - h - margin
            st.setRect(QRectF(x, y, w, h))

    


class ProcessItem(ResizableMixin, BaseNodeItem, QGraphicsEllipseItem):
    """
    Grafická reprezentace procesu v OPM diagramu.
    
    Vizuální znaky:
    - Elipsa (ovál)
    - Tmavě modrý obrys (0, 0, 128)
    - Bílá výplň
    - Podporuje změnu velikosti pomocí resize handles
    - Dvojklik otevře in-zoom view (modelování vnitřku procesu)
    """
    def __init__(self, rect: QRectF, label: str = "Process", essence: str = "informatical", affiliation: str = "systemic"):
        super().__init__(rect)
        self.init_node("process", label)
        self.essence = essence  # "physical" nebo "informatical"
        self.affiliation = affiliation  # "systemic" nebo "environmental"
        self.parent_process_id = None  # ID procesu, jehož in-zoom view obsahuje tento proces
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black, 2))
        self._init_resize()  # Přidá resize handles

    def itemChange(self, change, value):
        res = super().itemChange(change, value)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._set_handles_visible(bool(self.isSelected()))
        if change in (
            QGraphicsItem.ItemPositionHasChanged,
            QGraphicsItem.ItemPositionChange,
            QGraphicsItem.ItemSceneHasChanged,
        ):
            self._layout_handles()
        return res

    def boundingRect(self) -> QRectF:
        m = 8
        return super().boundingRect().adjusted(-m, -m, m, m)

    def mouseDoubleClickEvent(self, event):
        """Dvojklik na proces otevře in-zoom view (modelování vnitřku procesu)."""
        if event.button() == Qt.LeftButton:
            from ui.main_window import MainWindow  # lazy import
            main_win = MainWindow.instance()
            if main_win:
                main_win.create_in_zoom_canvas(self)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _get_process_state(self) -> Optional[str]:
        """Vrátí stav procesu v Petriho síti: 'fireable', 'waiting', 'blocked', nebo None pokud je síť vypnutá."""
        try:
            from ui.main_window import MainWindow
            main_win = MainWindow.instance()
            if not main_win:
                return None
            
            # Najdi simulation panel
            if not hasattr(main_win, 'dock_simulation'):
                return None
            
            sim_panel = main_win.dock_simulation
            # Pokud je síť vypnutá, vrať None
            if not sim_panel or not sim_panel.net_enabled:
                return None
            
            if not sim_panel.simulator or not sim_panel.simulator.net:
                return None
            
            # Najdi transition_id pro tento proces
            transition_id = f"transition_{self.node_id}"
            if transition_id not in sim_panel.simulator.net.transitions:
                return None
            
            # Zkontroluj stav přechodu
            if sim_panel.simulator.net.can_fire(transition_id):
                return 'fireable'
            elif transition_id in sim_panel.simulator.get_blocked_transitions():
                return 'blocked'
            elif transition_id in sim_panel.simulator.get_waiting_transitions():
                return 'waiting'
            else:
                return None
        except Exception:
            return None
    
    def paint(self, painter: QPainter, option, widget=None):
        # Nastavení pera podle affiliation
        pen = QPen(QColor(0, 0, 128), 3)
        if self.affiliation == "environmental":
            pen.setStyle(Qt.DashLine)
        else:
            pen.setStyle(Qt.SolidLine)
        
        # Stín pro fyzické procesy
        if self.essence == "physical":
            shadow_offset = 8
            painter.setBrush(QColor(80, 80, 80, 120))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self.rect().adjusted(shadow_offset, shadow_offset, shadow_offset, shadow_offset))
        
        # Zkontroluj stav procesu a nastav barvu pozadí podle stavu
        # Barvy jsou harmonizované s barvami v seznamech panelu
        state = self._get_process_state()
        if state == 'fireable':
            # Zelená pro fireable (harmonizováno s Qt.green v seznamu)
            # Pro pozadí prvku použijeme světlejší variantu
            fireable_green = QColor(200, 255, 200)  # Světle zelená
            painter.setBrush(QBrush(fireable_green))
        elif state == 'waiting':
            # Žlutá pro čekající (harmonizováno s Qt.darkYellow v seznamu)
            # Pro pozadí prvku použijeme světlejší variantu
            waiting_yellow = QColor(255, 255, 200)  # Světle žlutá
            painter.setBrush(QBrush(waiting_yellow))
        elif state == 'blocked':
            # Červená pro blokované (harmonizováno s Qt.red v seznamu)
            # Pro pozadí prvku použijeme světlejší variantu
            blocked_red = QColor(255, 200, 200)  # Světle červená
            painter.setBrush(QBrush(blocked_red))
        else:
            # Normální bílá barva (síť vypnutá nebo proces není v žádném z těchto stavů)
            painter.setBrush(self.brush())
        
        # vykresli obrys (modrý) a výplň
        painter.setPen(pen)
        painter.drawEllipse(self.rect())

        # vykresli text (černý)
        font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(font)
        painter.setPen(Qt.black)
        painter.drawText(self.rect(), Qt.AlignCenter, self.label)

        if option.state & QStyle.State_Selected:
            sel = QPen(Qt.blue, 2, Qt.DashLine)
            sel.setCosmetic(True)
            painter.setPen(sel)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.rect().adjusted(-6, -6, 6, 6)) 


class StateItem(ResizableMixin, BaseNodeItem, QGraphicsRectItem):
    """
    Grafická reprezentace stavu objektu v OPM diagramu.
    
    Stavy jsou vždy potomky objektů (parent-child relationship).
    
    Vizuální znaky:
    - Malý obdélník se zaoblenými rohy
    - Hnědý obrys (150, 75, 0)
    - Bílá výplň
    - Podporuje změnu velikosti pomocí resize handles
    - Může zobrazovat token (červený kruh) pro simulaci
    """
    def __init__(self, parent_obj: ObjectItem, rect: QRectF, label: str = "State"):
        super().__init__(rect, parent=parent_obj)
        self.init_node("state", label)
        self.state_type = "default"
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(QColor(150, 75, 0), 2))
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        
        # Simulace: token v místě
        self.has_token = False

        # Registruje se k rodiči (potřeba pro redo commands a přesun s rodicem)
        if not hasattr(parent_obj, "_states"):
            parent_obj._states = []
        parent_obj._states.append(self)

        # Inicializace resize handles
        self._init_resize()

    def remove_from_parent(self):
        """Odregistrování stavu od rodiče (při mazání/undo)."""
        if hasattr(self.parent_obj, "_states"):
            try:
                self.parent_obj._states.remove(self)
            except ValueError:
                pass

    def boundingRect(self) -> QRectF:
        m = 6
        return super().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(QPen(QColor(150, 75, 0), 2))
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 8, 8)

        font = QFont("Arial", 10, QFont.Bold)
        painter.setFont(font)
        painter.setPen(Qt.black)
        painter.drawText(self.rect(), Qt.AlignCenter, self.label)
        
        # Vykresli token (červený kruh) pokud má místo token
        if self.has_token:
            token_rect = QRectF(self.rect().right() - 12, self.rect().top() + 2, 10, 10)
            token_red = QColor(220, 50, 50)  # Výrazná, ale ne agresivní červená
            painter.setBrush(QBrush(token_red))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(token_rect)

        if option.state & QStyle.State_Selected:
            sel = QPen(Qt.blue, 1.5, Qt.DashLine)
            sel.setCosmetic(True)
            painter.setPen(sel)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(-4, -4, 4, 4), 8, 8)
