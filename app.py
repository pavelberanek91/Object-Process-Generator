"""
OPM Editor — MVP Skeleton (PySide6)
-----------------------------------
Single‑file prototype of a minimal OPM diagram editor.

Features (MVP):
- Add Object (rectangle) and Process (ellipse) nodes by clicking on the canvas.
- Add State (rounded rect) inside an Object by selecting the tool and clicking the target Object.
- Create Links between nodes (straight line with arrowhead) with a chosen link type.
- Move/select/delete nodes and links; links auto-update when nodes move.
- Edit label of the selected item in the right dock (press Enter or move focus to apply).
- Save/Load to a simple JSON format; Export to PNG/SVG.
- Snap-to-grid background and zoom in/out/reset.

Planned next (hooks exist):
- Validation of link types per ISO 19450 rules.
- In-zoom/out-zoom (multi-OPD support).
- OPL generation from the current diagram (very basic stub included).

Run:
  python opm_editor.py

Tested with: PySide6>=6.6
"""
from __future__ import annotations

import re
import json
import math
import sys
import itertools
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Tuple

from dotenv import load_dotenv, find_dotenv

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

GRID_SIZE = 25
NODE_W, NODE_H = 140, 70
STATE_W, STATE_H = 100, 28

LINK_TYPES = [
    # --- procedural ---
    "input",
    "consumption",
    "output",
    "result",
    "effect",
    "agent",
    "instrument",
    # --- structural ---
    "aggregation",       # whole is composed of part
    "participation",     # part is part of whole
    "exhibition",        # object exhibits attribute
    "characterization",  # attribute characterizes object
    "generalization",    # generalizes (supertype relation)
    "specialization",    # is a kind of (subtype relation)
    "instantiation",     # is an instance of
    "classification",    # is classified by / classifies
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

# ---------------------------- Graphics primitives ----------------------------

class GridScene(QGraphicsScene):
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        left = int(math.floor(rect.left())) - (int(math.floor(rect.left())) % GRID_SIZE)
        top = int(math.floor(rect.top())) - (int(math.floor(rect.top())) % GRID_SIZE)
        lines = []
        for x in range(left, int(rect.right()) + GRID_SIZE, GRID_SIZE):
            lines.append((QPointF(x, rect.top()), QPointF(x, rect.bottom())))
        for y in range(top, int(rect.bottom()) + GRID_SIZE, GRID_SIZE):
            lines.append((QPointF(rect.left(), y), QPointF(rect.right(), y)))
        painter.setPen(QPen(Qt.lightGray, 0))
        for a, b in lines:
            painter.drawLine(a, b)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        # Group selection outline now handled by a dedicated overlay item for correct invalidation.
        super().drawForeground(painter, rect)

class LinkItem(QGraphicsPathItem):
    STYLE_MAP = {
        # Procedurální ikony
        "input":       {"arrow": "dst"},
        "consumption": {"arrow": "dst"},
        "output":      {"arrow": "dst"},
        "result":      {"arrow": "src"},
        "effect":      {"arrow": "both"},
        "agent":       {"circle": ("filled", "dst")},     # plné kolečko u procesu
        "instrument":  {"circle": ("hollow", "dst")},     # prázdné kolečko u procesu

        # Strukturální ikony
        "aggregation":    {"marker": ("diamond_filled", "dst")},
        "participation":  {"marker": ("diamond_open",   "dst")},
        # Exhibition/Characterization → čtverec u objektu (char: plný, exhib: prázdný)
        "exhibition":     {"marker": ("square_open",    "dst")},
        "characterization":{"marker": ("square_filled", "dst")},
        # Generalization/Specialization → trojúhelník u supertypu (dutý)
        "generalization": {"marker": ("triangle_open",  "dst")},
        "specialization": {"marker": ("triangle_open",  "dst")},
        # Instantiation/Classification → kolečko u třídy (inst plné, class prázdné)
        "instantiation":  {"marker": ("circle_filled",  "dst")},
        "classification": {"marker": ("circle_open",    "dst")},
    }

    def __init__(self, src: QGraphicsItem, dst: QGraphicsItem, link_type: str = "input", label: str = ""):
        super().__init__()
        self.setZValue(1)  # nad uzly, aby byly vidět šipky a markery
        self.setFlags(QGraphicsItem.ItemIsSelectable)
        self.src = src
        self.dst = dst
        self.link_type = link_type
        self.label = label
        self.setPen(QPen(Qt.black, 2))

        # cache endpointů
        self._a = QPointF()
        self._b = QPointF()
        self._label_bounds = QRectF()

        # implicitní offsety pro texty u Linků, zmenšit pokud se mají objevit blíže Linku
        self._type_offset = QPointF(6, -4)
        self._label_offset = QPointF(6, 10)

         # pohyblivé “handle” popisky
        self.ti_type = LabelHandle(self, "type", self.link_type)
        self.ti_label = LabelHandle(self, "label", f'"{self.label}"') if self.label else None

        self.update_path()

        # textové potomky (ignorují zoom, mají vlastní bounding)
        # self._ti_type  = QGraphicsSimpleTextItem(self.link_type, self)
        # self._ti_type.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        # self._ti_type.setBrush(Qt.black)
        # self._ti_type.setAcceptedMouseButtons(Qt.NoButton)

        # self._ti_label = None
        # if self.label:
        #     self._ti_label = QGraphicsSimpleTextItem(f'"{self.label}"', self)
        #     self._ti_label.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        #     self._ti_label.setBrush(Qt.black)
        #     self._ti_label.setAcceptedMouseButtons(Qt.NoButton)
        # self.update_path()

        # back-references
        for n in (self.src, self.dst):
            if getattr(n, "_links", None) is None:
                n._links = []
            n._links.append(self)

    def set_link_type(self, lt: str):
        """ setter pro typ linku (kvůli správné invalidaci) """
        if lt == self.link_type:
            return
        self.link_type = lt
        self.ti_type.setText(self.link_type)
        self.update()

    def set_label_text(self, text: str):
        """ setter pro label (kvůli správné invalidaci) """
        if text == self.label:
            return
        self.label = text
        # správa child textu
        if text:
            if self._ti_label is None:
                self.ti_label = LabelHandle(self, "label", f'"{text}"')
            else:
                self._ti_label.setText(f'"{text}"')
        else:
            if self._ti_label is not None:
                self.scene().removeItem(self._ti_label)
                self._ti_label = None
        self._position_text()
        self.update()

    def remove_refs(self):
        for n in (self.src, self.dst):
            if getattr(n, "_links", None) is not None:
                try:
                    n._links.remove(self)
                except ValueError:
                    pass

    # --- anchoring helpers (hranice tvarů) ---
    def _center(self, item: QGraphicsItem) -> QPointF:
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            return item.mapToScene(item.rect().center())
        br = item.mapToScene(item.boundingRect()).boundingRect()
        return br.center()

    def _anchor_on_rect(self, item: QGraphicsRectItem, toward: QPointF) -> QPointF:
        c = self._center(item)
        r = item.rect()
        hw, hh = r.width()/2.0, r.height()/2.0
        dx = toward.x() - c.x()
        dy = toward.y() - c.y()
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return c
        tx = float('inf') if abs(dx) < 1e-6 else hw/abs(dx)
        ty = float('inf') if abs(dy) < 1e-6 else hh/abs(dy)
        t = min(tx, ty)
        return QPointF(c.x() + dx*t, c.y() + dy*t)

    def _anchor_on_ellipse(self, item: QGraphicsEllipseItem, toward: QPointF) -> QPointF:
        c = self._center(item)
        r = item.rect()
        rx, ry = r.width()/2.0, r.height()/2.0
        dx = toward.x() - c.x()
        dy = toward.y() - c.y()
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return c
        t = 1.0 / math.sqrt((dx*dx)/(rx*rx) + (dy*dy)/(ry*ry))
        return QPointF(c.x() + dx*t, c.y() + dy*t)

    def _anchor_for_item(self, item: QGraphicsItem, toward: QPointF) -> QPointF:
        if isinstance(item, QGraphicsEllipseItem):
            return self._anchor_on_ellipse(item, toward)
        elif isinstance(item, QGraphicsRectItem):
            return self._anchor_on_rect(item, toward)
        return self._center(item)

    def endpoints(self) -> Tuple[QPointF, QPointF]:
        c_src = self._center(self.src)
        c_dst = self._center(self.dst)
        a_src = self._anchor_for_item(self.src, c_dst)
        a_dst = self._anchor_for_item(self.dst, c_src)
        return a_src, a_dst

    def update_path(self) -> None:
        a, b = self.endpoints()
        self._a, self._b = a, b
        self.prepareGeometryChange()
        #self._recalc_text_bounds()
        path = QPainterPath(a)
        path.lineTo(b)
        self.setPath(path)
        self._position_text()

    def boundingRect(self) -> QRectF:
        br = super().boundingRect()
        return br.adjusted(-12, -12, 12, 12)  # šipky/markery

    # --- styling helpers ---
    def _style(self):
        return self.STYLE_MAP.get(self.link_type, self.STYLE_MAP["input"])

    def _point_near(self, a: QPointF, b: QPointF, end: str, offset: float = 14) -> QPointF:
        dx = b.x() - a.x(); dy = b.y() - a.y()
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        if end == "src":
            return QPointF(a.x() + ux*offset, a.y() + uy*offset)
        else:
            return QPointF(b.x() - ux*offset, b.y() - uy*offset)

    def _draw_marker(self, painter: QPainter, pos: QPointF, angle: float, kind: str):
        """
        kind ∈ {"circle_filled","circle_open","square_filled","square_open",
                "diamond_filled","diamond_open","triangle_filled","triangle_open","bar","plus","cross"}
        """
        painter.save()
        painter.translate(pos)

        # Urči fill a základní tvar
        fill = True
        base = kind
        if kind.endswith("_open"):
            fill = False
            base = kind[:-5]
        elif kind.endswith("_filled"):
            fill = True
            base = kind[:-7]

        # Rotace: triangle zarovnáme do směru linky; bar kolmo; ostatní bez rotace
        if base == "triangle":
            painter.rotate(math.degrees(angle))
        elif base == "bar":
            painter.rotate(math.degrees(angle + math.pi/2))

        # Pen/Brush
        # (bar/plus/cross jsou jen čáry → brush netřeba)
        if base not in ("bar", "plus", "cross"):
            painter.setBrush(Qt.black if fill else Qt.white)

        if base == "circle":
            painter.drawEllipse(QRectF(-5, -5, 10, 10))
        elif base == "square":
            painter.drawRect(QRectF(-5, -5, 10, 10))
        elif base == "diamond":
            poly = QPolygonF([QPointF(0, -6), QPointF(6, 0), QPointF(0, 6), QPointF(-6, 0)])
            painter.drawPolygon(poly)
        elif base == "triangle":
            poly = QPolygonF([QPointF(0, 0), QPointF(-10, -6), QPointF(-10, 6)])
            painter.drawPolygon(poly)
        elif base == "bar":
            painter.drawLine(QPointF(0, -6), QPointF(0, 6))
        elif base == "plus":
            painter.drawLine(QPointF(-5, 0), QPointF(5, 0))
            painter.drawLine(QPointF(0, -5), QPointF(0, 5))
        elif base == "cross":
            painter.drawLine(QPointF(-5, -5), QPointF(5, 5))
            painter.drawLine(QPointF(-5, 5), QPointF(5, -5))

        painter.restore()

    def _recalc_text_bounds(self):
        """ Pomocná metoda na přepočet textových bounds """
        mid = (self._a + self._b) / 2
        fm = QFontMetricsF(QApplication.font())
        rects = []

        if self.link_type:
            t = self.link_type
            w = fm.horizontalAdvance(t); h = fm.height()
            p = mid + QPointF(6, -6)
            rects.append(QRectF(p.x(), p.y() - h, w, h))

        if self.label:
            t = f'"{self.label}"'
            w = fm.horizontalAdvance(t); h = fm.height()
            p = mid + QPointF(6, 12)
            rects.append(QRectF(p.x(), p.y() - h, w, h))

        if rects:
            r = rects[0]
            for rr in rects[1:]:
                r = r.united(rr)
            self._label_bounds = r.adjusted(-4, -4, 4, 4)
        else:
            self._label_bounds = QRectF()

    def _position_text(self):
        """ pomocna funkce na pozicovani textu u Linků """
        a, b = self.endpoints()
        mid = (a + b) / 2

        # typ vazby
        if hasattr(self, "ti_type") and self.ti_type:
            self.ti_type.setPos(self.mapFromScene(mid + self._type_offset))

        # volitelný label
        if hasattr(self, "ti_label") and self.ti_label:
            self.ti_label.setPos(self.mapFromScene(mid + self._label_offset))

    def paint(self, painter: QPainter, option, widget=None):
        style = self._style()
        selected = bool(option.state & QStyle.State_Selected)

        pen = QPen(Qt.blue if selected else Qt.black, 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Line
        painter.drawPath(self.path())

        # Endpoints & angle
        a, b = self.endpoints()
        angle = math.atan2(b.y() - a.y(), b.x() - a.x())

        # Arrowheads (triangle)
        def draw_arrow_at(point: QPointF, ang: float, open: bool = False):
            arrow_size = 10
            p1 = point + QPointF(-arrow_size * math.cos(ang - math.pi / 6), -arrow_size * math.sin(ang - math.pi / 6))
            p2 = point + QPointF(-arrow_size * math.cos(ang + math.pi / 6), -arrow_size * math.sin(ang + math.pi / 6))
            poly = QPolygonF([point, p1, p2])
            painter.setBrush(Qt.NoBrush if open and not selected else (Qt.blue if selected else Qt.black))
            painter.drawPolygon(poly)

        arrow_mode = style.get("arrow")
        if arrow_mode == "dst":
            draw_arrow_at(b, angle)
        elif arrow_mode == "src":
            draw_arrow_at(a, angle + math.pi)
        elif arrow_mode == "both":
            draw_arrow_at(b, angle)
            draw_arrow_at(a, angle + math.pi)

        # Structural marker:
        marker = style.get("marker")
        if marker:
            kind, end = marker
            pos = self._point_near(a, b, end, 12)
            # u strukturálních tvarů orientujeme trojúhelník do směru linky:
            self._draw_marker(painter, pos, angle if "triangle" in kind else angle, kind)

        # Lollipop markers (agent/instrument)
        circle = style.get("circle")
        if circle:
            fill_kind, end = circle
            pos = self._point_near(a, b, end, 10)
            painter.save()
            painter.setBrush((Qt.blue if selected else Qt.black) if fill_kind == "filled" else Qt.white)
            painter.drawEllipse(QRectF(pos.x()-5, pos.y()-5, 10, 10))
            painter.restore()
    

class BaseNodeItem:
    """Mixin for common node behavior."""
    def init_node(self, kind: str, label: str):
        self.kind = kind
        self.node_id = next_id(kind)
        self.label = label
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def itemChange(self, change, value):
        # Ensure our update runs; handle both 'about to change' and 'has changed'
        res = super().itemChange(change, value)
        if change in (
            QGraphicsItem.ItemPositionHasChanged,
            QGraphicsItem.ItemPositionChange,
            QGraphicsItem.ItemSceneHasChanged,
        ):
            for ln in getattr(self, "_links", []) or []:
                ln.update_path()
        if change == QGraphicsItem.ItemSelectedHasChanged:
            # Force repaint so selection halo disappears immediately
            self.update()
        return res

    def set_label(self, text: str):
        if text == self.label:
            return
        self.label = text
        self.update()

class ObjectItem(BaseNodeItem, QGraphicsRectItem):
    def __init__(self, rect: QRectF, label: str = "Object"):
        super().__init__(rect)
        self.init_node("object", label)
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black, 2))

    def set_label(self, text: str):
        if text == self.label:
            return
        self.label = text
        self.update()

    def boundingRect(self) -> QRectF:
        # Expand to include the selection halo so deselection repaints cleanly
        m = 8
        return super().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter: QPainter, option, widget=None):
        # Base shape
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 12, 12)
        
        # Label
        painter.drawText(self.rect(), Qt.AlignCenter, self.label)
        
        # Selection halo (outer, dashed) — draw within expanded bounding rect
        if option.state & QStyle.State_Selected:
            sel_pen = QPen(Qt.blue, 2, Qt.DashLine)
            sel_pen.setCosmetic(True)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(-6, -6, 6, 6), 12, 12)

class ProcessItem(BaseNodeItem, QGraphicsEllipseItem):
    def __init__(self, rect: QRectF, label: str = "Process"):
        super().__init__(rect)
        self.init_node("process", label)
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black, 2))

    def boundingRect(self) -> QRectF:
        m = 8
        return super().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())
        painter.drawText(self.rect(), Qt.AlignCenter, self.label)
        if option.state & QStyle.State_Selected:
            sel_pen = QPen(Qt.blue, 2, Qt.DashLine)
            sel_pen.setCosmetic(True)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.rect().adjusted(-6, -6, 6, 6))

class StateItem(BaseNodeItem, QGraphicsRectItem):
    def __init__(self, parent_obj: ObjectItem, rect: QRectF, label: str = "State"):
        super().__init__(rect, parent=parent_obj)
        self.init_node("state", label)
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black, 1.5))
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )

    def boundingRect(self) -> QRectF:
        m = 6
        return super().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 8, 8)
        painter.drawText(self.rect(), Qt.AlignCenter, self.label)
        if option.state & QStyle.State_Selected:
            sel_pen = QPen(Qt.blue, 1.5, Qt.DashLine)
            sel_pen.setCosmetic(True)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(-4, -4, 4, 4), 8, 8)

class LabelHandle(QGraphicsSimpleTextItem):
    def __init__(self, link: "LinkItem", kind: str, text: str):
        super().__init__(text, link)  # parent = link → dědí pohyb linky
        self.link = link
        self.kind = kind  # "type" | "label"
        self.setZValue(3)
        self.setBrush(Qt.black)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            # přepočítat offset vůči středu linky (ve scénických souřadnicích)
            a, b = self.link.endpoints()
            mid_scene = (a + b) / 2
            my_scene = self.mapToScene(QPointF(0, 0))
            off = my_scene - mid_scene
            if self.kind == "type":
                self.link._type_offset = off
            else:
                self.link._label_offset = off
        return super().itemChange(change, value)

# ---------------------------- Editor main window -----------------------------

class EditorView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, app: "MainWindow"):
        super().__init__(scene)
        self.app = app
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRubberBandSelectionMode(Qt.IntersectsItemBoundingRect)
        self.setMouseTracking(True)
        self.ghost_item = None
        self.ghost_kind = None
        self.temp_link = None

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.app.zoom_in()
            else:
                self.app.zoom_out()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        if self.app.mode == Mode.ADD_OBJECT:
            self.app.add_object(scene_pos)
            return
        elif self.app.mode == Mode.ADD_PROCESS:
            self.app.add_process(scene_pos)
            return
        elif self.app.mode == Mode.ADD_STATE:
            item = self.scene().itemAt(scene_pos, self.transform())
            if isinstance(item, ObjectItem):
                self.app.add_state(item, scene_pos)
                return
        elif self.app.mode == Mode.ADD_LINK:
            self.app.handle_link_click(scene_pos)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        mode = self.app.mode
        if mode in (Mode.ADD_OBJECT, Mode.ADD_PROCESS):
            self.update_ghost(scene_pos)
            self.clear_temp_link()
        elif mode == Mode.ADD_STATE:
            self.update_ghost(scene_pos)  # only shows when over object
            self.clear_temp_link()
        elif mode == Mode.ADD_LINK:
            if self.app.pending_link_src is not None:
                self.update_temp_link(scene_pos)
            else:
                self.clear_temp_link()
            self.clear_ghost()
        else:
            self.clear_ghost()
            self.clear_temp_link()
        super().mouseMoveEvent(event)

    def clear_overlays(self):
        self.clear_ghost()
        self.clear_temp_link()

    def clear_ghost(self):
        if self.ghost_item is not None:
            self.scene().removeItem(self.ghost_item)
            self.ghost_item = None
            self.ghost_kind = None

    def update_ghost(self, scene_pos: QPointF):
        mode = self.app.mode
        if mode == Mode.ADD_OBJECT:
            if self.ghost_kind != 'object':
                self.clear_ghost()
                from PySide6.QtWidgets import QGraphicsRectItem
                gi = QGraphicsRectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
                gi.setPen(QPen(Qt.darkGray, 2, Qt.DashLine))
                gi.setBrush(Qt.NoBrush)
                gi.setZValue(10)
                gi.setFlag(QGraphicsItem.ItemIsSelectable, False)
                gi.setAcceptedMouseButtons(Qt.NoButton)
                self.scene().addItem(gi)
                self.ghost_item = gi
                self.ghost_kind = 'object'
            self.ghost_item.setPos(self.app.snap(scene_pos))
        elif mode == Mode.ADD_PROCESS:
            if self.ghost_kind != 'process':
                self.clear_ghost()
                from PySide6.QtWidgets import QGraphicsEllipseItem
                gi = QGraphicsEllipseItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
                gi.setPen(QPen(Qt.darkGray, 2, Qt.DashLine))
                gi.setBrush(Qt.NoBrush)
                gi.setZValue(10)
                gi.setFlag(QGraphicsItem.ItemIsSelectable, False)
                gi.setAcceptedMouseButtons(Qt.NoButton)
                self.scene().addItem(gi)
                self.ghost_item = gi
                self.ghost_kind = 'process'
            self.ghost_item.setPos(self.app.snap(scene_pos))
        elif mode == Mode.ADD_STATE:
            # Only preview when hovering an ObjectItem
            item = self.scene().itemAt(scene_pos, self.transform())
            if not isinstance(item, ObjectItem):
                self.clear_ghost()
                return
            # compute local pos within object and clamp
            p = item.mapFromScene(self.app.snap(scene_pos))
            r = item.rect()
            x = min(max(p.x() - STATE_W/2, r.left()+6), r.right()-STATE_W-6)
            y = min(max(p.y() - STATE_H/2, r.top()+6), r.bottom()-STATE_H-6)
            rect = QRectF(x, y, STATE_W, STATE_H)
            if self.ghost_kind != 'state' or (self.ghost_item and self.ghost_item.parentItem() is not item):
                self.clear_ghost()
                from PySide6.QtWidgets import QGraphicsRectItem
                gi = QGraphicsRectItem(rect, parent=item)
                gi.setPen(QPen(Qt.darkGray, 1.5, Qt.DashLine))
                gi.setBrush(Qt.NoBrush)
                gi.setZValue(10)
                gi.setFlag(QGraphicsItem.ItemIsSelectable, False)
                gi.setAcceptedMouseButtons(Qt.NoButton)
                self.ghost_item = gi
                self.ghost_kind = 'state'
            else:
                # move existing within parent
                self.ghost_item.setRect(rect)

    def clear_temp_link(self):
        if self.temp_link is not None:
            self.scene().removeItem(self.temp_link)
            self.temp_link = None

    def update_temp_link(self, scene_pos: QPointF):
        src = self.app.pending_link_src
        if src is None:
            self.clear_temp_link()
            return
        a = src.mapToScene(src.boundingRect()).boundingRect().center()
        path = QPainterPath(a)
        path.lineTo(scene_pos)
        if self.temp_link is None:
            self.temp_link = QGraphicsPathItem()
            self.temp_link.setPen(QPen(Qt.darkGray, 1, Qt.DashLine))
            self.temp_link.setZValue(-2)
            self.temp_link.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.temp_link.setAcceptedMouseButtons(Qt.NoButton)
            self.scene().addItem(self.temp_link)
        self.temp_link.setPath(path)

@dataclass
class DiagramNode:
    id: str
    kind: str  # object|process|state
    label: str
    x: float
    y: float
    w: float
    h: float
    parent_id: Optional[str] = None  # for states

@dataclass
class DiagramLink:
    id: str
    src: str
    dst: str
    link_type: str
    label: str = ""
    type_dx: float = 6.0
    type_dy: float = -6.0
    label_dx: float = 6.0
    label_dy: float = 12.0

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OPM Editor — MVP")
        self.mode = Mode.SELECT
        self._scale = 1.0
        self.pending_link_src: Optional[QGraphicsItem] = None

        # default link type for newly created links
        self.default_link_type = LINK_TYPES[0]
        # guard to avoid recursive updates when programmatically changing combo
        self._suppress_combo = False

        self.scene = GridScene(self)
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.view = EditorView(self.scene, self)
        self.setCentralWidget(self.view)

        self.create_toolbar()
        self.create_prop_dock()
        self.scene.selectionChanged.connect(self.sync_selected_to_props)

    # ---------------------- UI creation ----------------------
    def create_toolbar(self):
        tb = QToolBar("Tools")
        self.addToolBar(Qt.TopToolBarArea, tb)

        act_select = QAction("Select/Move", self)
        act_select.triggered.connect(lambda: self.set_mode(Mode.SELECT))
        tb.addAction(act_select)

        tb.addSeparator()
        act_obj = QAction("Add Object", self)
        act_obj.triggered.connect(lambda: self.set_mode(Mode.ADD_OBJECT))
        tb.addAction(act_obj)

        tb.addSeparator()
        act_proc = QAction("Add Process", self)
        act_proc.triggered.connect(lambda: self.set_mode(Mode.ADD_PROCESS))
        tb.addAction(act_proc)

        tb.addSeparator()
        act_state = QAction("Add State", self)
        act_state.triggered.connect(lambda: self.set_mode(Mode.ADD_STATE))
        tb.addAction(act_state)

        tb.addSeparator()
        act_link = QAction("Add Link", self)
        act_link.triggered.connect(lambda: self.set_mode(Mode.ADD_LINK))
        tb.addAction(act_link)

        # Make tools checkable and exclusive, reflect current mode
        act_select.setCheckable(True)
        act_obj.setCheckable(True)
        act_proc.setCheckable(True)
        act_state.setCheckable(True)
        act_link.setCheckable(True)
        group = QActionGroup(self)
        group.setExclusive(True)
        for a in (act_select, act_obj, act_proc, act_state, act_link):
            group.addAction(a)
        act_select.setChecked(True)
        self._action_group = group
        self.actions = {
            Mode.SELECT: act_select,
            Mode.ADD_OBJECT: act_obj,
            Mode.ADD_PROCESS: act_proc,
            Mode.ADD_STATE: act_state,
            Mode.ADD_LINK: act_link,
        }

        tb.addSeparator()
        act_delete = QAction("Delete", self)
        act_delete.triggered.connect(self.delete_selected)
        tb.addAction(act_delete)

        tb.addSeparator()
        act_clear_all = QAction("Clear All", self)
        act_clear_all.triggered.connect(self.clear_all)
        tb.addAction(act_clear_all)

        tb.addSeparator()
        act_zoom_in = QAction("Zoom +", self)
        act_zoom_in.triggered.connect(self.zoom_in)
        tb.addAction(act_zoom_in)

        tb.addSeparator()
        act_zoom_out = QAction("Zoom -", self)
        act_zoom_out.triggered.connect(self.zoom_out)
        tb.addAction(act_zoom_out)

        tb.addSeparator()
        act_zoom_reset = QAction("Reset Zoom", self)
        act_zoom_reset.triggered.connect(self.zoom_reset)
        tb.addAction(act_zoom_reset)

        tb.addSeparator()
        act_save = QAction("Save JSON", self)
        act_save.triggered.connect(self.save_json)
        tb.addAction(act_save)

        tb.addSeparator()
        act_load = QAction("Load JSON", self)
        act_load.triggered.connect(self.load_json)
        tb.addAction(act_load)

        tb.addSeparator()
        act_png = QAction("Export PNG", self)
        act_png.triggered.connect(lambda: self.export_image("png"))
        tb.addAction(act_png)

        tb.addSeparator()
        act_svg = QAction("Export SVG", self)
        act_svg.triggered.connect(lambda: self.export_image("svg"))
        tb.addAction(act_svg)

        tb.addSeparator()
        act_import_opl = QAction("Create OPL", self)
        act_import_opl.triggered.connect(self.import_opl_dialog)
        tb.addAction(act_import_opl)

        tb.addSeparator()
        act_nl2opl = QAction("Generate OPL", self)
        act_nl2opl.triggered.connect(self.open_nl_to_opl_dialog)
        tb.addAction(act_nl2opl)

    def create_prop_dock(self):
        dock = QDockWidget("Properties", self)
        panel = QWidget()
        form = QFormLayout(panel)
        self.ed_label = QLineEdit()
        self.ed_label.setPlaceholderText("Label…")
        self.ed_label.editingFinished.connect(self.apply_label_change)
        form.addRow("Label", self.ed_label)

        self.cmb_link_type = QComboBox()
        self.cmb_link_type.addItems(LINK_TYPES)
        self.cmb_link_type.setCurrentText(self.default_link_type)
        self.cmb_link_type.currentTextChanged.connect(self.handle_link_type_combo_change)
        self.lbl_link_type = QLabel("Link type (for new links)")
        form.addRow(self.lbl_link_type, self.cmb_link_type)

        self.btn_generate_opl = QPushButton("Generate OPL (preview)")
        self.btn_generate_opl.clicked.connect(self.preview_opl)
        form.addRow(self.btn_generate_opl)

        panel.setLayout(form)
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def set_mode(self, mode: str):
        self.mode = mode
        # Toggle toolbar button
        try:
            self.actions[mode].setChecked(True)
        except Exception:
            pass
        # Cursor & drag behavior
        if mode == Mode.SELECT:
            self.view.setCursor(Qt.ArrowCursor)
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
            self.view.clear_overlays()
        else:
            self.view.setCursor(Qt.CrossCursor)
            self.view.setDragMode(QGraphicsView.NoDrag)
        self.statusBar().showMessage(f"Mode: {mode}")
        if mode != Mode.ADD_LINK:
            self.pending_link_src = None
            self.view.clear_temp_link()

    def keyPressEvent(self, event):
        # Allow Delete/Backspace to remove any rubber-band selected items
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    # ---------------------- Node ops ----------------------
    def add_object(self, pos: QPointF):
        rect = QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H)
        item = ObjectItem(rect)
        item.setPos(self.snap(pos))
        self.scene.addItem(item)

    def add_process(self, pos: QPointF):
        rect = QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H)
        item = ProcessItem(rect)
        item.setPos(self.snap(pos))
        self.scene.addItem(item)

    def add_state(self, obj: ObjectItem, pos_in_scene: QPointF):
        p = obj.mapFromScene(self.snap(pos_in_scene))
        # keep state within object rect
        r = obj.rect()
        x = min(max(p.x() - STATE_W/2, r.left()+6), r.right()-STATE_W-6)
        y = min(max(p.y() - STATE_H/2, r.top()+6), r.bottom()-STATE_H-6)
        s = StateItem(obj, QRectF(x, y, STATE_W, STATE_H))
        self.scene.addItem(s)

    def allowed_link(self, src_item: QGraphicsItem, dst_item: QGraphicsItem, link_type: str) -> tuple[bool, str]:
        """Zkontroluje, zda je (src→dst, typ) povolený podle OPM.
        Vrací (OK, zpráva_pro_uživatele_pokud_ne)."""
        lt = (link_type or "").lower()
        s_kind = getattr(src_item, "kind", None)      # "object" | "process" | "state"|None
        d_kind = getattr(dst_item, "kind", None)

        if lt in PROCEDURAL_TYPES:
            # Procedurální smí jen Object↔Process (nikoli Object↔Object ani Process↔Process)
            if s_kind == "object" and d_kind == "process" and lt in {"input", "consumption", "agent", "instrument", "effect"}:
                return True, ""
            if s_kind == "process" and d_kind == "object" and lt in {"output", "result", "effect"}:
                return True, ""
            return False, ("Procedurální vazba musí spojovat Object↔Process. "
                       "Povolené směry: Object→Process [input|consumption|agent|instrument|effect]; "
                       "Process→Object [output|result|effect].")

        if lt in STRUCTURAL_TYPES:
            # Strukturální povolíme pro Object↔Object i Process↔Process (nikoli křížem)
            if s_kind in {"object", "process"} and s_kind == d_kind:
                return True, ""
            return False, "Strukturální vazba musí být Object↔Object nebo Process↔Process (ne křížem)."

        # Neznámé typy neomezujeme (nebo si sem můžeš doplnit vlastní pravidla)
        return True, ""

    def handle_link_click(self, pos: QPointF):
        item = self.scene.itemAt(pos, self.view.transform())
        if not isinstance(item, (ObjectItem, ProcessItem)):
            return
        if self.pending_link_src is None:
            self.pending_link_src = item
            self.statusBar().showMessage("Choose target node…")
        else:
            if item is self.pending_link_src:
                self.pending_link_src = None
                return
            ok, msg = self.allowed_link(self.pending_link_src, item, self.default_link_type)
            if not ok:
                QApplication.beep()
                QMessageBox.warning(self, "Neplatná vazba", msg)
                self.pending_link_src = None
                return

            link = LinkItem(self.pending_link_src, item, self.default_link_type)
            self.scene.addItem(link)
            self.pending_link_src = None
            self.statusBar().clearMessage()

    def delete_selected(self):
        for it in list(self.scene.selectedItems()):
            if isinstance(it, LinkItem):
                it.remove_refs()
                self.scene.removeItem(it)
            elif isinstance(it, (ObjectItem, ProcessItem, StateItem)):
                # Remove connected links
                for ln in list(getattr(it, "_links", []) or []):
                    ln.remove_refs()
                    self.scene.removeItem(ln)
                self.scene.removeItem(it)

    def clear_all(self):
        self.view.clear_overlays()
        self.pending_link_src = None
        self.scene.clear()

    # ---------------------- Selection outline ----------------------
    # ---------------------- Zoom & helpers ----------------------
    def zoom_in(self):
        # Zoom toward mouse cursor
        self._scale = min(self._scale * 1.2, 5.0)
        self.view.scale(1.2, 1.2)

    def zoom_out(self):
        self._scale = max(self._scale / 1.2, 0.2)
        self.view.scale(1/1.2, 1/1.2)

    def zoom_reset(self):
        self._scale = 1.0
        self.view.resetTransform()

    def snap(self, p: QPointF) -> QPointF:
        return QPointF(
            round(p.x() / GRID_SIZE) * GRID_SIZE,
            round(p.y() / GRID_SIZE) * GRID_SIZE,
        )

    # ---------------------- Properties panel ----------------------
    def selected_item(self) -> Optional[QGraphicsItem]:
        sel = self.scene.selectedItems()
        return sel[0] if sel else None

    def sync_selected_to_props(self):
        sel = self.scene.selectedItems()
        it = sel[0] if sel else None
        if isinstance(it, (ObjectItem, ProcessItem, StateItem)):
            self.ed_label.setText(it.label)
        elif isinstance(it, LinkItem):
            self.ed_label.setText(it.label)
        else:
            self.ed_label.clear()
        # Update link-type UI depending on selection
        link_items = [x for x in sel if isinstance(x, LinkItem)]
        self._suppress_combo = True
        if link_items:
            # When links are selected, reflect their (first) type and indicate scope
            self.cmb_link_type.setCurrentText(link_items[0].link_type)
            self.lbl_link_type.setText("Link type (selected links)")
        else:
            # No links selected => combo controls default for new links
            self.cmb_link_type.setCurrentText(self.default_link_type)
            self.lbl_link_type.setText("Link type (for new links)")
        self._suppress_combo = False

    def apply_label_change(self):
        it = self.selected_item()
        text = self.ed_label.text()
        if isinstance(it, (ObjectItem, ProcessItem, StateItem)):
            it.set_label(text)
        elif isinstance(it, LinkItem):
            it.set_label_text(text)

    # --- Link type editing ---
    def handle_link_type_combo_change(self, text: str):
        # Pokud jsou vybrané linky → zkusíme všem změnit typ; pokud by některému typ nevyhovoval, neprovedeme nic a vrátíme combobox.
        if getattr(self, "_suppress_combo", False):
            return

        links = [it for it in self.scene.selectedItems() if isinstance(it, LinkItem)]
        if not links:
            # nic není vybráno → nastavíme jen default pro nově kreslené linky
            self.default_link_type = text
            return

        # Ověř, zda je nový typ pro všechny vybrané linky povolený
        invalid = []
        for ln in links:
            ok, msg = self.allowed_link(ln.src, ln.dst, text)
            if not ok:
                invalid.append(msg)

        if invalid:
            # neaplikuj změnu, vrať combobox a ukaž důvod (první zprávu)
            self._suppress_combo = True
            # nastav zpět na typ prvního linku (nebo na původní text, pokud chceš)
            self.cmb_link_type.setCurrentText(links[0].link_type)
            self._suppress_combo = False
            QApplication.beep()
            QMessageBox.warning(self, "Neplatný typ vazby", invalid[0])
            return

        # Vše ok → aplikuj nový typ všem vybraným linkům
        for ln in links:
            ln.set_link_type(text)

    def _opl_split_names(self, s: str) -> List[str]:
        # Rozdělí "A, B and C" | "A and B" | "A, B, C"
        s = s.strip().strip(".")
        # nejdřív nahradíme " and " za čárku (ale jen poslední "and")
        s = re.sub(r"\s+and\s+", ", ", s)
        parts = [p.strip().strip('"') for p in s.split(",")]
        return [p for p in (x for x in parts) if p]

    def _norm(self, name: str) -> str:
        return name.strip().strip('"')

    def import_opl_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Import OPL")
        txt = QTextEdit(dlg)
        txt.setPlaceholderText("Vlož sem OPL věty, každou na samostatný řádek.")

        btn_ok = QPushButton("Importovat", dlg)
        btn_cancel = QPushButton("Zrušit", dlg)
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)

        v = QVBoxLayout()
        v.addWidget(txt)
        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(btn_ok)
        h.addWidget(btn_cancel)
        v.addLayout(h)
        dlg.setLayout(v)
        dlg.resize(640, 420)

        if dlg.exec() == QDialog.Accepted:
            self.build_from_opl(txt.toPlainText())

    def build_from_opl(self, text: str):
        # --- mapy stávajících uzlů podle labelu (abychom nepřidávali duplicitně) ---
        by_label: Dict[str, QGraphicsItem] = {}
        kind_of: Dict[str, str] = {}  # "object" | "process"
        for it in self.scene.items():
            if isinstance(it, ObjectItem) or isinstance(it, ProcessItem):
                by_label[it.label] = it
                kind_of[it.label] = it.kind

        # --- jednoduché umístění nových uzlů (do 2 řad) ---
        # počátky řad odvoď lehce doprava od aktuální scény, ať se to nemotá
        items_rect = self.scene.itemsBoundingRect() if self.scene.items() else QRectF(-200, -150, 400, 300)
        base_x = items_rect.right() + 150  # nové věci dáme doprava; když nic není, vyjde z defaultu
        proc_i = 0
        obj_i = 0
        def next_proc_pos() -> QPointF:
            nonlocal proc_i
            p = self.snap(QPointF(base_x + proc_i * 200, -150))
            proc_i += 1
            return p

        def next_obj_pos() -> QPointF:
            nonlocal obj_i
            p = self.snap(QPointF(base_x + obj_i * 200, 130))
            obj_i += 1
            return p

        def get_or_create_process(name: str) -> QGraphicsItem:
            name = self._norm(name)
            it = by_label.get(name)
            if it and isinstance(it, ProcessItem):
                return it
            if it and isinstance(it, ObjectItem):
                # kolize druhu – ponecháme existující, ale dál bereme jako process
                return it
            item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name)
            item.setPos(next_proc_pos())
            self.scene.addItem(item)
            by_label[name] = item
            kind_of[name] = "process"
            return item

        def get_or_create_object(name: str) -> QGraphicsItem:
            name = self._norm(name)
            it = by_label.get(name)
            if it and isinstance(it, ObjectItem):
                return it
            if it and isinstance(it, ProcessItem):
                return it
            item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name)
            item.setPos(next_obj_pos())
            self.scene.addItem(item)
            by_label[name] = item
            kind_of[name] = "object"
            return item

        def ensure_link(src: QGraphicsItem, dst: QGraphicsItem, lt: str, label: str = ""):
            # vyhnout se duplicitě stejného (src,dst,typ)
            for it in self.scene.items():
                if isinstance(it, LinkItem) and it.src is src and it.dst is dst and it.link_type == lt:
                    return it
            ln = LinkItem(src, dst, lt, label)
            self.scene.addItem(ln)
            return ln

        # --- regexy (singular/plural varianty) ---
        # Procedurální:
        re_consumes  = re.compile(r'^\s*(?P<p>.+?)\s+consume(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
        re_inputs    = re.compile(r'^\s*(?P<p>.+?)\s+take(?:s)?\s+(?P<objs>.+?)\s+as\s+input\.\s*$', re.I)
        re_yields    = re.compile(r'^\s*(?P<p>.+?)\s+yield(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
        re_handles   = re.compile(r'^\s*(?P<agents>.+?)\s+handle(?:s)?\s+(?P<p>.+?)\.\s*$', re.I)
        re_requires  = re.compile(r'^\s*(?P<p>.+?)\s+require(?:s)?\s+(?P<objs>.+?)\.\s*$', re.I)
        re_affects   = re.compile(r'^\s*(?P<x>.+?)\s+affect(?:s)?\s+(?P<y>.+?)\.\s*$', re.I)

        # Strukturální:
        re_composed  = re.compile(r'^\s*(?P<whole>.+?)\s+is\s+composed\s+of\s+(?P<parts>.+?)\.\s*$', re.I)
        re_charac    = re.compile(r'^\s*(?P<obj>.+?)\s+is\s+characterized\s+by\s+(?P<attrs>.+?)\.\s*$', re.I)
        re_exhibits  = re.compile(r'^\s*(?P<obj>.+?)\s+exhibit(?:s)?\s+(?P<attrs>.+?)\.\s*$', re.I)
        re_gener     = re.compile(r'^\s*(?P<super>.+?)\s+generalize(?:s)?\s+(?P<subs>.+?)\.\s*$', re.I)
        re_instances = re.compile(r'^\s*(?P<class>.+?)\s+has\s+instances\s+(?P<insts>.+?)\.\s*$', re.I)

        ignored: List[str] = []

        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue

            m = re_consumes.match(line)
            if m:
                p = get_or_create_process(m.group("p"))
                for o in self._opl_split_names(m.group("objs")):
                    ensure_link(get_or_create_object(o), p, "consumption")
                continue

            m = re_inputs.match(line)
            if m:
                p = get_or_create_process(m.group("p"))
                for o in self._opl_split_names(m.group("objs")):
                    ensure_link(get_or_create_object(o), p, "input")
                continue

            m = re_yields.match(line)
            if m:
                p = get_or_create_process(m.group("p"))
                for o in self._opl_split_names(m.group("objs")):
                    ensure_link(p, get_or_create_object(o), "output")  # "yields" mapujeme na "output"
                continue

            m = re_handles.match(line)
            if m:
                p = get_or_create_process(m.group("p"))
                for a in self._opl_split_names(m.group("agents")):
                    ensure_link(get_or_create_object(a), p, "agent")
                continue

            m = re_requires.match(line)
            if m:
                p = get_or_create_process(m.group("p"))
                for inst in self._opl_split_names(m.group("objs")):
                    ensure_link(get_or_create_object(inst), p, "instrument")
                continue

            m = re_affects.match(line)
            if m:
                x = self._norm(m.group("x")); y = self._norm(m.group("y"))
                # jednoduchá heuristika podle toho, co už ve scéně je
                if kind_of.get(x) == "process" or kind_of.get(y) == "object":
                    ensure_link(get_or_create_process(x), get_or_create_object(y), "effect")
                elif kind_of.get(x) == "object" or kind_of.get(y) == "process":
                    ensure_link(get_or_create_object(x), get_or_create_process(y), "effect")
                else:
                    ensure_link(get_or_create_process(x), get_or_create_object(y), "effect")
                continue

            # --- strukturální ---
            m = re_composed.match(line)
            if m:
                whole = get_or_create_object(m.group("whole"))
                for part in self._opl_split_names(m.group("parts")):
                    # part → whole
                    ensure_link(get_or_create_object(part), whole, "aggregation")
                continue

            m = re_charac.match(line)
            if m:
                obj = get_or_create_object(m.group("obj"))
                for attr in self._opl_split_names(m.group("attrs")):
                    ensure_link(obj, get_or_create_object(attr), "characterization")
                continue

            m = re_exhibits.match(line)
            if m:
                obj = get_or_create_object(m.group("obj"))
                for attr in self._opl_split_names(m.group("attrs")):
                    ensure_link(obj, get_or_create_object(attr), "exhibition")
                continue

            m = re_gener.match(line)
            if m:
                sup = get_or_create_object(m.group("super"))
                for sub in self._opl_split_names(m.group("subs")):
                    # sub → super (v našem preview takto interpretujeme generalization)
                    ensure_link(get_or_create_object(sub), sup, "generalization")
                continue

            m = re_instances.match(line)
            if m:
                cls = get_or_create_object(m.group("class"))
                for inst in self._opl_split_names(m.group("insts")):
                    # instance → class
                    ensure_link(get_or_create_object(inst), cls, "instantiation")
                continue

            ignored.append(line)

        if ignored:
            QMessageBox.information(
                self, "Import OPL",
                "Některé řádky nebyly rozpoznány a byly přeskočeny:\n\n• " + "\n• ".join(ignored)
            )
    
    def open_nl_to_opl_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("NL → OPL")
        inp = QTextEdit(dlg)
        inp.setPlaceholderText("Popiš proces/vztahy v přirozeném jazyce (CZ/EN).")

        out = QTextEdit(dlg)
        out.setPlaceholderText("Sem se vygeneruje OPL. Můžeš ho ještě ručně upravit.")
        out.setReadOnly(False)

        btn_gen = QPushButton("Vygenerovat OPL", dlg)
        btn_import = QPushButton("Importovat do diagramu", dlg)
        btn_cancel = QPushButton("Zrušit", dlg)

        def do_generate():
            nl = inp.toPlainText().strip()
            if not nl:
                QMessageBox.information(self, "NL → OPL", "Zadej text.")
                return
            try:
                opl = self.nl_to_opl(nl)
            except Exception as e:
                QMessageBox.warning(self, "NL → OPL", f"Generování selhalo:\n{e}")
                return
            out.setPlainText(opl)

        def do_import():
            opl = out.toPlainText().strip()
            if not opl:
                QMessageBox.information(self, "NL → OPL", "Není co importovat.")
                return
            self.build_from_opl(opl)      # používá tvůj existující parser → vykreslí
            dlg.accept()

        btn_gen.clicked.connect(do_generate)
        btn_import.clicked.connect(do_import)
        btn_cancel.clicked.connect(dlg.reject)

        lay = QVBoxLayout()
        lay.addWidget(QLabel("Natural Language input"))
        lay.addWidget(inp)
        lay.addWidget(QLabel("Generated OPL (editable)"))
        lay.addWidget(out)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn_gen)
        row.addWidget(btn_import)
        row.addWidget(btn_cancel)
        lay.addLayout(row)
        dlg.setLayout(lay)
        dlg.resize(720, 520)
        dlg.exec()

    def nl_to_opl(self, nl_text: str) -> str:
        """
        Pošli `prompt` do libovolného LLM a vrať POUZE OPL věty (po jedné na řádek).
        Šablony (musí přesně sedět na náš importér):
        - {P} consumes {O[, O2, ...]}.
        - {P} takes {O[, O2, ...]} as input.
        - {P} yields {O[, O2, ...]}.
        - {P} affects {O[, O2, ...]}.
        - {A[, A2, ...]} handle {P}.
        - {P} requires {O[, O2, ...]}.
        - {Whole} is composed of {Part[, Part2, ...]}.
        - {Obj} is characterized by {Attr[, Attr2, ...]}.
        - {Obj} exhibits {Attr[, Attr2, ...]}.
        - {Super} generalizes {Sub[, Sub2, ...]}.
        - {Class} has instances {i1[, i2, ...]}.
        Pravidla:
        - Používej přesně tyto tvary, zakončené tečkou.
        - Názvy přenech v uvozovkách jen pokud je uživatel sám dal; jinak bez uvozovek.
        - Vstup může být česky, výstup OPL v angličtině podle šablon výše.
        """
        SYSTEM_OPL_GUIDE = (
            "You are an OPM assistant. Convert the user description to strict OPL sentences.\n"
            "Allowed templates (exact wording, one sentence per line, each ending with a period):\n"
            "- {{P}} consumes {{O[, O2, ...]}}.\n"
            "- {{P}} takes {{O[, O2, ...]}} as input.\n"
            "- {{P}} yields {{O[, O2, ...]}}.\n"
            "- {{P}} affects {{O[, O2, ...]}}.\n"
            "- {{A[, A2, ...]}} handle {{P}}.\n"
            "- {{P}} requires {{O[, O2, ...]}}.\n"
            "- {{Whole}} is composed of {{Part[, Part2, ...]}}.\n"
            "- {{Obj}} is characterized by {{Attr[, Attr2, ...]}}.\n"
            "- {{Obj}} exhibits {{Attr[, Attr2, ...]}}.\n"
            "- {{Super}} generalizes {{Sub[, Sub2, ...]}}.\n"
            "- {{Class}} has instances {{i1[, i2, ...]}}.\n\n"
            "Rules:\n"
            "- Output ONLY OPL sentences above, nothing else (no preface, no code fences).\n"
            "- If input is in Czech or Slovak, translate terms to English labels where reasonable (keep proper nouns).\n"
            "- Merge obvious synonyms (e.g., 'produces' → 'yields', 'uses' → 'requires' or 'consumes' depending on context)."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_OPL_GUIDE),
                ("human", "User description (CZ/EN):\n```text\n{nl}\n```")
            ]
        )

        llm = ChatOpenAI(model="gpt-5-chat-latest", temperature=0)
        try:
            resp = (prompt | llm).invoke({"nl": nl_text})
        except Exception: # pokud selze pripojeni k modelu, tak se spusti heuristicky fallback
            return self._heuristic_nl_to_opl(nl_text)
        
        content = getattr(resp, "content", "")
        # kdyby náhodou přišly code fences
        content = re.sub(r"^```[a-zA-Z]*|```$", "", content.strip(), flags=re.MULTILINE)
        return content.strip()

    def _heuristic_nl_to_opl(self, nl: str) -> str:
        """
        Velmi jednoduchý fallback: zkusí vytáhnout triády typu
        'Process uses A and B to make C' → převede na 'requires' + 'yields'.
        Je to jen nouzové, abys viděl tok NL→OPL→diagram i bez API klíče.
        """
        text = nl.strip()
        lines = []

        # pár triviálních vzorů (CZ/EN), klidně si rozšiř:
        import re
        # uses ... to produce ...
        m = re.search(r'(?P<p>[\w\s"]+?)\s+(uses|používá)\s+(?P<ins>.+?)\s+(to\s+produce|k\s+vytvoření)\s+(?P<outs>.+)', text, re.I)
        if m:
            P = m.group("p").strip('" ')
            INS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ins")) if x.strip()]
            OUTS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("outs")) if x.strip()]
            if INS:
                lines.append(f'{P} requires {", ".join(INS)}.')
            if OUTS:
                lines.append(f'{P} yields {", ".join(OUTS)}.')

        # consumes ...
        m = re.search(r'(?P<p>[\w\s"]+?)\s+(consumes|spotřebovává)\s+(?P<objs>.+)', text, re.I)
        if m:
            P = m.group("p").strip('" ')
            OBJS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("objs")) if x.strip()]
            if OBJS: lines.append(f'{P} consumes {", ".join(OBJS)}.')

        # agents
        m = re.search(r'(?P<ag>[\w\s",]+?)\s+(handle|řídí)\s+(?P<p>[\w\s"]+)', text, re.I)
        if m:
            AGS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ag")) if x.strip()]
            P = m.group("p").strip('" ')
            if AGS: lines.append(f'{", ".join(AGS)} handle {P}.')

        # requires ...
        m = re.search(r'(?P<p>[\w\s"]+?)\s+(requires|vyžaduje)\s+(?P<ins>.+)', text, re.I)
        if m:
            P = m.group("p").strip('" ')
            INS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("ins")) if x.strip()]
            if INS: lines.append(f'{P} requires {", ".join(INS)}.')

        # yields/produces ...
        m = re.search(r'(?P<p>[\w\s"]+?)\s+(yields|produces|vyrábí|generuje)\s+(?P<outs>.+)', text, re.I)
        if m:
            P = m.group("p").strip('" ')
            OUTS = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("outs")) if x.strip()]
            if OUTS: lines.append(f'{P} yields {", ".join(OUTS)}.')

        # affects ...
        m = re.search(r'(?P<x>[\w\s"]+?)\s+(affects|ovlivňuje)\s+(?P<y>[\w\s",]+)', text, re.I)
        if m:
            X = m.group("x").strip('" ')
            Ys = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("y")) if x.strip()]
            if Ys: lines.append(f'{X} affects {", ".join(Ys)}.')

        # structure "is composed of"
        m = re.search(r'(?P<w>[\w\s"]+?)\s+(is composed of|se skládá z)\s+(?P<p>.+)', text, re.I)
        if m:
            W = m.group("w").strip('" ')
            Ps = [x.strip(' ".,') for x in re.split(r',| and | a ', m.group("p")) if x.strip()]
            if Ps: lines.append(f'{W} is composed of {", ".join(Ps)}.')

        # dedupe & vrátit
        clean = []
        seen = set()
        for ln in lines:
            ln = ln.rstrip(".") + "."
            if ln not in seen:
                seen.add(ln)
                clean.append(ln)
        return "\n".join(clean) if clean else ""

    # ---------------------- Persistence ----------------------
    def to_dict(self) -> Dict[str, Any]:
        nodes: List[DiagramNode] = []
        links: List[DiagramLink] = []

        # Nodes (objects & processes)
        for it in self.scene.items():
            if isinstance(it, (ObjectItem, ProcessItem)):
                # ⬅️ klíčová změna: čistý tvar, nikoli boundingRect s halem
                r_scene = it.mapRectToScene(it.rect())
                n = DiagramNode(
                    id=it.node_id,
                    kind=it.kind,
                    label=it.label,
                    x=r_scene.center().x(),
                    y=r_scene.center().y(),
                    w=r_scene.width(),
                    h=r_scene.height(),
                )
                nodes.append(n)

                # States inside this object
                if isinstance(it, ObjectItem):
                    for ch in it.childItems():
                        if isinstance(ch, StateItem):
                            # ⬅️ zjednodušení pro state
                            sr = ch.mapRectToScene(ch.rect())
                            sn = DiagramNode(
                                id=ch.node_id,
                                kind="state",
                                label=ch.label,
                                x=sr.center().x(),
                                y=sr.center().y(),
                                w=sr.width(),
                                h=sr.height(),
                                parent_id=it.node_id,
                            )
                            nodes.append(sn)

        # Links
        for it in self.scene.items():
            if isinstance(it, LinkItem):
                links.append(
                    DiagramLink(
                         id=next_id("link"),
                        src=getattr(it.src, "node_id", ""),
                        dst=getattr(it.dst, "node_id", ""),
                        link_type=it.link_type,
                        label=it.label,
                        type_dx=it._type_offset.x(),
                        type_dy=it._type_offset.y(),
                        label_dx=it._label_offset.x() if it.ti_label else 6.0,
                        label_dy=it._label_offset.y() if it.ti_label else 12.0,
                    )
                )

        return {
            "nodes": [asdict(n) for n in nodes],
            "links": [asdict(l) for l in links],
            "meta": {"format": "opm-mvp-json", "version": 1},
        }

        # Links
        for it in self.scene.items():
            if isinstance(it, LinkItem):
                links.append(
                    DiagramLink(
                        id=next_id("link"),
                        src=getattr(it.src, "node_id", ""),
                        dst=getattr(it.dst, "node_id", ""),
                        link_type=it.link_type,
                        label=it.label,
                    )
                )
        return {
            "nodes": [asdict(n) for n in nodes],
            "links": [asdict(l) for l in links],
            "meta": {"format": "opm-mvp-json", "version": 1},
        }

    def from_dict(self, data: Dict[str, Any]):
        self.scene.clear()
        id_to_item: Dict[str, QGraphicsItem] = {}
        # First pass: objects & processes
        for n in data.get("nodes", []):
            kind = n["kind"]
            if kind not in ("object", "process", "state"):
                continue
            pos = QPointF(n["x"], n["y"])
            if kind == "object":
                item = ObjectItem(QRectF(-n["w"]/2, -n["h"]/2, n["w"], n["h"]), n["label"])
                item.node_id = n["id"]
                item.setPos(pos)
                self.scene.addItem(item)
                id_to_item[n["id"]] = item
        for n in data.get("nodes", []):
            if n["kind"] == "process":
                item = ProcessItem(QRectF(-n["w"]/2, -n["h"]/2, n["w"], n["h"]), n["label"])
                item.node_id = n["id"]
                item.setPos(QPointF(n["x"], n["y"]))
                self.scene.addItem(item)
                id_to_item[n["id"]] = item
        # States as children
        for n in data.get("nodes", []):
            if n["kind"] == "state" and n.get("parent_id") in id_to_item:
                parent = id_to_item[n["parent_id"]]
                # map scene center to parent rect
                local_center = parent.mapFromScene(QPointF(n["x"], n["y"]))
                rect = QRectF(local_center.x()-n["w"]/2, local_center.y()-n["h"]/2, n["w"], n["h"])
                item = StateItem(parent, rect, n["label"])
                item.node_id = n["id"]
                self.scene.addItem(item)
                id_to_item[n["id"]] = item

        # Links
        invalid_count = 0
        for l in data.get("links", []):
            src = id_to_item.get(l["src"])
            dst = id_to_item.get(l["dst"]) 
            if src and dst:
                lt = l.get("link_type", "input")
                ok, msg = self.allowed_link(src, dst, lt)
                if not ok:
                    # přeskoč nevalidní linky ze souboru
                    invalid_count += 1
                    continue
                li = LinkItem(src, dst, l.get("link_type", "input"), l.get("label", ""))
                self.scene.addItem(li)
                # offsety (fallback na defaulty) TODO: mozna se ani neaplikuji a program pri importu bez nich vyhodi chybu
                li._type_offset  = QPointF(l.get("type_dx", 6.0),  l.get("type_dy", -6.0))
                li._label_offset = QPointF(l.get("label_dx", 6.0), l.get("label_dy", 12.0))
                li._position_text()

        if invalid_count:
            QMessageBox.warning(self, "Některé vazby přeskočeny",
                f"{invalid_count} neplatných vazeb bylo při načítání přeskočeno kvůli typu/směru.")

    # File ops
    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Diagram", "diagram.json", "JSON (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Diagram", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.from_dict(data)

    def export_image(self, kind: str = "png"):
        # Simple export via QGraphicsScene API
        if kind == "png":
            path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "diagram.png", "PNG (*.png)")
            if not path:
                return
            # Render to image with scene's bounding rect
            rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            from PySide6.QtGui import QImage
            img = QImage(int(rb.width()), int(rb.height()), QImage.Format_ARGB32_Premultiplied)
            img.fill(0x00FFFFFF)
            painter = QPainter(img)
            self.scene.render(painter, target=QRectF(0, 0, rb.width(), rb.height()), source=rb)
            painter.end()
            img.save(path)
        elif kind == "svg":
            path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "diagram.svg", "SVG (*.svg)")
            if not path:
                return
            from PySide6.QtSvg import QSvgGenerator
            rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            gen = QSvgGenerator()
            gen.setFileName(path)
            gen.setSize(rb.size().toSize())
            gen.setViewBox(rb)
            painter = QPainter(gen)
            self.scene.render(painter, target=rb, source=rb)
            painter.end()
        else:
            QMessageBox.warning(self, "Export", f"Unsupported format: {kind}")

    # ---------------------- OPL (very basic stub) ----------------------
    def preview_opl(self):
        """
        Vygeneruje OPL náhled:
        - agreguje více vstupů/agentů/instrumentů do jedné věty na proces
        - result/output do jedné věty "yields ..."
        - effect do věty "affects ..."
        - object–object linky vypisuje jako "A {label | link_type} B." (placeholder pro strukturální vazby)
        """
        # 1) načteme labely a typy uzlů
        nodes: Dict[str, Tuple[str, str]] = {}
        proc_labels: Dict[str, str] = {}
        for it in self.scene.items():
            if isinstance(it, (ObjectItem, ProcessItem)):
                nodes[it.node_id] = (it.kind, it.label)
                if isinstance(it, ProcessItem):
                    proc_labels[it.node_id] = it.label

        # 2) buckets pro každou proceduru (agregace do jedné věty)
        buckets: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: {
            "consumes": [],
            "inputs": [],
            "yields": [],
            "affects": [],
            "agents": [],
            "instruments": [],
        })
        struct_buckets = {
            "whole_parts": defaultdict(list),   # Whole → [parts]
            "characterized": defaultdict(list), # Object → [attributes]
            "exhibits": defaultdict(list),      # Object → [attributes]
            "generalizes": defaultdict(list),   # Super → [subs]
            "classifies": defaultdict(list),    # Class → [instances]
        }
        structural_lines: List[str] = []

        def opl_join(names: List[str]) -> str:
            if not names:
                return ""
            # dedupe s původním pořadím
            names = list(dict.fromkeys(names))
            return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]

        # 3) projdeme linky a naplníme bucket/structural
        for it in self.scene.items():
            if not isinstance(it, LinkItem):
                continue
            s = getattr(it.src, "node_id", "")
            d = getattr(it.dst, "node_id", "")
            s_kind, s_label = nodes.get(s, ("?", "?"))
            d_kind, d_label = nodes.get(d, ("?", "?"))
            lt = it.link_type

            # Object → Process
            if s_kind == "object" and d_kind == "process":
                if lt == "consumption":
                    buckets[d]["consumes"].append(s_label)
                elif lt == "input":
                    buckets[d]["inputs"].append(s_label)
                elif lt == "agent":
                    buckets[d]["agents"].append(s_label)
                elif lt == "instrument":
                    buckets[d]["instruments"].append(s_label)
                elif lt == "effect":
                    buckets[d]["affects"].append(s_label)

            # Process → Object
            elif s_kind == "process" and d_kind == "object":
                if lt in ("result", "output"):
                    buckets[s]["yields"].append(d_label)
                elif lt == "effect":
                    buckets[s]["affects"].append(d_label)

            # Object ↔ Object a Proces ↔ Proces (placeholder pro strukturální vazby)
            elif s_kind in ("object", "process") and d_kind in ("object", "process"):
                lt_norm = lt.lower()

                if lt_norm in ("aggregation", "participation"):
                    # s = part, d = whole
                    struct_buckets["whole_parts"][d_label].append(s_label)

                elif lt_norm == "characterization":
                    # s = object, d = attribute
                    struct_buckets["characterized"][s_label].append(d_label)

                elif lt_norm == "exhibition":
                    # s = object, d = attribute
                    struct_buckets["exhibits"][s_label].append(d_label)

                elif lt_norm in ("specialization", "generalization"):
                    # s = subtype, d = supertype
                    struct_buckets["generalizes"][d_label].append(s_label)

                elif lt_norm in ("instantiation", "classification"):
                    # s = instance, d = class
                    struct_buckets["classifies"][d_label].append(s_label)

                else:
                    # fallback – kdyby ses trefil na jiný/uživatelský typ
                    # (můžeš klidně vypustit, pokud nechceš žádný fallback)
                    pass

        # 4) složíme OPL věty
        lines: List[str] = []
        for pid, b in buckets.items():
            pname = proc_labels.get(pid)
            if not pname:
                continue
            if b["consumes"]:
                lines.append(f"{pname} consumes {opl_join(b['consumes'])}.")
            if b["inputs"]:
                lines.append(f"{pname} takes {opl_join(b['inputs'])} as input.")
            if b["yields"]:
                lines.append(f"{pname} yields {opl_join(b['yields'])}.")
            if b["affects"]:
                lines.append(f"{pname} affects {opl_join(b['affects'])}.")
            if b["agents"]:
                lines.append(f"{opl_join(b['agents'])} handle {pname}.")
            if b["instruments"]:
                lines.append(f"{pname} requires {opl_join(b['instruments'])}.")

        # Whole–part (aggregation/participation): "Whole is composed of A, B and C."
        for whole, parts in struct_buckets["whole_parts"].items():
            if parts:
                lines.append(f"{whole} is composed of {opl_join(sorted(parts))}.")

        # Characterization: "Object is characterized by A and B."
        for obj, attrs in struct_buckets["characterized"].items():
            if attrs:
                lines.append(f"{obj} is characterized by {opl_join(sorted(attrs))}.")

        # Exhibition: "Object exhibits A and B."
        for obj, attrs in struct_buckets["exhibits"].items():
            if attrs:
                lines.append(f"{obj} exhibits {opl_join(sorted(attrs))}.")

        # Generalization/Specialization: "Super generalizes Sub1, Sub2."
        for sup, subs in struct_buckets["generalizes"].items():
            if subs:
                lines.append(f"{sup} generalizes {opl_join(sorted(subs))}.")

        # Instantiation/Classification: "Class has instances i1, i2."
        for cls, insts in struct_buckets["classifies"].items():
            if insts:
                lines.append(f"{cls} has instances {opl_join(sorted(insts))}.")

        if not lines:
            lines = ["-- OPL preview has no content yet --"]

        # 5) zobrazíme v poscrollovatelném dialogu s možností uložit
        dlg = QDialog(self)
        dlg.setWindowTitle("OPL Preview")
        txt = QTextEdit(dlg)
        txt.setReadOnly(True)
        txt.setPlainText("\n".join(lines))
        btn_close = QPushButton("Close", dlg)
        btn_save = QPushButton("Save…", dlg)

        def do_save():
            path, _ = QFileDialog.getSaveFileName(self, "Save OPL", "opl.txt", "Text (*.txt)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(txt.toPlainText())
        btn_save.clicked.connect(do_save)
        btn_close.clicked.connect(dlg.accept)

        layout = QVBoxLayout()
        layout.addWidget(txt)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn_save)
        row.addWidget(btn_close)
        layout.addLayout(row)
        dlg.setLayout(layout)
        dlg.resize(600, 400)
        dlg.exec()


def main():
    load_dotenv(find_dotenv(), override=True)
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1100, 700)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()