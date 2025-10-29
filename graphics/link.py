"""Grafická reprezentace vazeb (linků) mezi uzly v OPM diagramu.

Implementuje:
- LinkItem: Čára propojující dva uzly s příslušnými markery (šipky, kruhy, atd.)
- LabelHandle: Přesouvatelný text pro typ vazby a label
- Automatické výpočty kotevních bodů na obdélnících/elipsách
- Různé styly vazeb (procedurální/strukturální) s příslušnými markery
"""
from __future__ import annotations
import math
from typing import Tuple
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPen, QPainter, QPolygonF, QPixmap, QTransform
from PySide6.QtWidgets import (
    QGraphicsPathItem, QGraphicsItem, QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QGraphicsRectItem, QStyle
)


# Načtení ikon pro strukturální vztahy
_STRUCTURAL_ICONS = {}

def _load_structural_icons():
    """Načte PNG ikony pro strukturální vztahy ze složky ui/icons/"""
    if _STRUCTURAL_ICONS:
        return  # Už načteno
    
    icons_dir = Path(__file__).parent.parent / "ui" / "icons"
    
    # Mapování typu vazby na název souboru (kvůli různým pravopisům)
    icon_files = {
        "aggregation": "aggregation",
        "exhibition": "exhibition", 
        "generalization": "generalization",
        "instantiation": "instatiation"  # Soubor má překlep, ale zachováváme ho
    }
    
    for link_type, filename in icon_files.items():
        png_path = icons_dir / f"{filename}.png"
        if png_path.exists():
            pixmap = QPixmap(str(png_path))
            _STRUCTURAL_ICONS[link_type] = pixmap
        else:
            _STRUCTURAL_ICONS[link_type] = None


class LabelHandle(QGraphicsSimpleTextItem):
    """
    Přesouvatelný textový popisek vazby (typ vazby nebo vlastní label).
    
    Umožňuje uživateli přemístit popisek pro lepší čitelnost diagramu.
    """
    def __init__(self, link: "LinkItem", kind: str, text: str):
        super().__init__(text, link)
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
            a, b = self.link.endpoints()
            mid_scene = (a + b) / 2
            my_scene = self.mapToScene(QPointF(0, 0))
            off = my_scene - mid_scene
            if self.kind == "type":
                self.link._type_offset = off
            else:
                self.link._label_offset = off
        return super().itemChange(change, value)

class LinkItem(QGraphicsPathItem):
    STYLE_MAP = {
        "input": {"arrow": "dst"},
        "consumption": {"arrow": "dst"},
        "output": {"arrow": "dst"},
        "result": {"arrow": "dst"},
        "effect": {"arrow": "both"},
        "agent": {"circle": ("filled", "dst")},
        "instrument": {"circle": ("hollow", "dst")},
        "aggregation": {"marker": ("diamond_filled", "dst")},
        "exhibition": {"marker": ("square_open", "dst")},
        "generalization": {"marker": ("triangle_open", "dst"), "arrow_flip": True},
        "instantiation": {"marker": ("circle_filled", "dst")},
    }
    
    CARDINALITY_TYPES = {"aggregation", "exhibition", "generalization", "instantiation"}

    def __init__(self, src: QGraphicsItem, dst: QGraphicsItem, link_type: str="input", label: str=""):
        super().__init__()
        _load_structural_icons()  # Načteme ikony při první inicializaci
        self.setZValue(1)
        self.setFlags(QGraphicsItem.ItemIsSelectable)
        self.src = src
        self.card_src = ""
        self.dst = dst
        self.card_dst = ""
        self.link_type = link_type
        self.label = label
        self.setPen(QPen(Qt.black, 2))

        self._a = QPointF()
        self._b = QPointF()
        self._label_bounds = QRectF()
        self._type_offset  = QPointF(6, -4)
        self._label_offset = QPointF(6, 10)

        # Typ vazby se nezobrazuje, pouze vlastní label
        self.ti_type  = None
        self.ti_label = LabelHandle(self, "label", self.label) if self.label else None
        
        self.ti_card_src = QGraphicsSimpleTextItem("", self)
        self.ti_card_src.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.ti_card_src.setZValue(3)

        self.ti_card_dst = QGraphicsSimpleTextItem("", self)
        self.ti_card_dst.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.ti_card_dst.setZValue(3)
        
        self.update_path()

        # backrefs
        for n in (self.src, self.dst):
            if getattr(n, "_links", None) is None:
                n._links = []
            n._links.append(self)

    # geometry helpers
    def _center(self, item: QGraphicsItem) -> QPointF:
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            return item.mapToScene(item.rect().center())
        br = item.mapToScene(item.boundingRect()).boundingRect()
        return br.center()

    def _anchor_on_rect(self, item: QGraphicsRectItem, toward: QPointF) -> QPointF:
        c = self._center(item); r = item.rect()
        hw, hh = r.width()/2, r.height()/2
        dx = toward.x() - c.x(); dy = toward.y() - c.y()
        if abs(dx) < 1e-6 and abs(dy) < 1e-6: return c
        tx = float('inf') if abs(dx) < 1e-6 else hw/abs(dx)
        ty = float('inf') if abs(dy) < 1e-6 else hh/abs(dy)
        t = min(tx, ty)
        return QPointF(c.x()+dx*t, c.y()+dy*t)

    def _anchor_on_ellipse(self, item: QGraphicsEllipseItem, toward: QPointF) -> QPointF:
        c = self._center(item); r = item.rect()
        rx, ry = r.width()/2, r.height()/2
        dx = toward.x() - c.x(); dy = toward.y() - c.y()
        if abs(dx) < 1e-6 and abs(dy) < 1e-6: return c
        t = 1.0 / math.sqrt((dx*dx)/(rx*rx) + (dy*dy)/(ry*ry))
        return QPointF(c.x()+dx*t, c.y()+dy*t)

    def _anchor_for_item(self, item: QGraphicsItem, toward: QPointF) -> QPointF:
        if isinstance(item, QGraphicsEllipseItem):
            return self._anchor_on_ellipse(item, toward)
        elif isinstance(item, QGraphicsRectItem):
            return self._anchor_on_rect(item, toward)
        return self._center(item)

    def endpoints(self) -> Tuple[QPointF, QPointF]:
        c_src = self._center(self.src); c_dst = self._center(self.dst)
        a_src = self._anchor_for_item(self.src, c_dst)
        a_dst = self._anchor_for_item(self.dst, c_src)
        return a_src, a_dst

    def update_path(self) -> None:
        a, b = self.endpoints()
        self._a, self._b = a, b
        self.prepareGeometryChange()
        path = QPainterPath(a); path.lineTo(b)
        self.setPath(path)
        self._position_text()

    def boundingRect(self):
        br = super().boundingRect()
        return br.adjusted(-12, -12, 12, 12)

    def _style(self):
        return self.STYLE_MAP.get(self.link_type, self.STYLE_MAP["input"])

    def _point_near(self, a: QPointF, b: QPointF, end: str, offset: float=14) -> QPointF:
        dx = b.x()-a.x(); dy = b.y()-a.y()
        L = math.hypot(dx, dy) or 1.0; ux, uy = dx/L, dy/L
        return QPointF(a.x()+ux*offset, a.y()+uy*offset) if end=="src" else QPointF(b.x()-ux*offset, b.y()-uy*offset)

    def _position_text(self):
        a, b = self.endpoints()
        mid = (a+b)/2
        if getattr(self, "ti_type", None):
            self.ti_type.setPos(self.mapFromScene(mid + self._type_offset))
        if getattr(self, "ti_label", None):
            self.ti_label.setPos(self.mapFromScene(mid + self._label_offset))
            
        # --- kardinality ---
        if self.link_type in self.CARDINALITY_TYPES:
            a, b = self.endpoints()
            v = b - a
            L = math.hypot(v.x(), v.y()) or 1
            ux, uy = v.x()/L, v.y()/L
            
            if self.ti_card_src and self.card_src:
                self.ti_card_src.setText(self.card_src)
                # posun od začátku hrany, trochu dovnitř linku (t=0.15)
                pos = QPointF(a.x() + ux*30, a.y() + uy*30)
                self.ti_card_src.setPos(self.mapFromScene(pos))
                
            if self.ti_card_dst and self.card_dst:
                self.ti_card_dst.setText(self.card_dst)
                # posun od konce hrany, trochu dovnitř linku (t=0.15)
                pos = QPointF(b.x() - ux*30, b.y() - uy*30)
                self.ti_card_dst.setPos(self.mapFromScene(pos))
        else:
            if self.ti_card_src: 
                self.ti_card_src.setText("")
            if self.ti_card_dst: 
                self.ti_card_dst.setText("")

    def _draw_marker(self, painter: QPainter, pos: QPointF, angle: float, kind: str):
        painter.save(); painter.translate(pos)
        fill = not kind.endswith("_open")
        base = kind.replace("_open", "").replace("_filled", "")
        if base == "triangle": painter.rotate(math.degrees(angle))
        elif base == "bar":   painter.rotate(math.degrees(angle + math.pi/2))
        if base not in ("bar","plus","cross"):
            painter.setBrush(Qt.black if fill else Qt.white)
        if base == "circle":    painter.drawEllipse(QRectF(-5,-5,10,10))
        elif base == "square":  painter.drawRect(QRectF(-5,-5,10,10))
        elif base == "diamond": painter.drawPolygon(QPolygonF([QPointF(0,-6),QPointF(6,0),QPointF(0,6),QPointF(-6,0)]))
        elif base == "triangle":painter.drawPolygon(QPolygonF([QPointF(0,0),QPointF(-10,-6),QPointF(-10,6)]))
        elif base == "bar":     painter.drawLine(QPointF(0,-6), QPointF(0,6))
        elif base == "plus":    (painter.drawLine(QPointF(-5,0),QPointF(5,0)), painter.drawLine(QPointF(0,-5),QPointF(0,5)))
        elif base == "cross":   (painter.drawLine(QPointF(-5,-5),QPointF(5,5)), painter.drawLine(QPointF(-5,5),QPointF(5,-5)))
        painter.restore()

    def paint(self, painter: QPainter, option, widget=None):
        from PySide6.QtGui import QPen
        selected = bool(option.state & QStyle.State_Selected)
        pen = QPen(Qt.blue if selected else Qt.black, 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        a, b = self.endpoints()
        angle = math.atan2(b.y()-a.y(), b.x()-a.x())
        mid = QPointF((a.x() + b.x())/2, (a.y() + b.y())/2)

        # místo konců kreslíme do středu
        style = self._style()
        link_type = self.link_type
        
        def draw_arrow_at(point: QPointF, ang: float, open: bool=False):
            arrow_size = 10
            p1 = point + QPointF(-arrow_size*math.cos(ang - math.pi/6), -arrow_size*math.sin(ang - math.pi/6))
            p2 = point + QPointF(-arrow_size*math.cos(ang + math.pi/6), -arrow_size*math.sin(ang + math.pi/6))
            poly = QPolygonF([point, p1, p2])
            # OPM standard: bílá výplň s černým ohraničením (nebo modrá když je vybraná)
            if selected:
                painter.setBrush(Qt.blue)
            else:
                painter.setBrush(Qt.white)
            painter.drawPolygon(poly)
            
        if link_type in {"aggregation", "exhibition", "generalization", "instantiation"}:
            # kreslíme do středu
            # Zkusíme použít PNG ikonu
            icon_pixmap = _STRUCTURAL_ICONS.get(link_type)
            
            if icon_pixmap and not icon_pixmap.isNull():
                # Vykreslíme ikonu
                painter.save()
                
                # Přesuneme se do středu vazby
                painter.translate(mid)
                
                # Rotace podle směru vazby
                rotation_angle = math.degrees(angle)
                painter.rotate(rotation_angle)
                
                # Vykreslíme ikonu vystředěnou
                icon_size = icon_pixmap.size()
                painter.drawPixmap(
                    -icon_size.width() // 2,
                    -icon_size.height() // 2,
                    icon_pixmap
                )
                
                painter.restore()
            else:
                # Fallback na původní programatické kreslení
                if style.get("arrow"):
                    draw_arrow_at(mid, angle)
                if style.get("marker"):
                    kind, _end = style["marker"]
                    ang = angle + (math.pi if link_type == "generalization" else 0.0)
                    self._draw_marker(painter, mid, ang, kind)
                if style.get("circle"):
                    fill_kind, _end = style["circle"]
                    pos = mid
                    painter.save()
                    painter.setBrush((Qt.blue if selected else Qt.black) if fill_kind=="filled" else Qt.white)
                    painter.drawEllipse(QRectF(pos.x()-5, pos.y()-5, 10, 10))
                    painter.restore()
        else:
            # původní chování – kreslení na konce
            am = style.get("arrow")
            if am == "dst": draw_arrow_at(b, angle)
            elif am == "src": draw_arrow_at(a, angle + math.pi)
            elif am == "both": (draw_arrow_at(b, angle), draw_arrow_at(a, angle + math.pi))

            marker = style.get("marker")
            if marker:
                kind, end = marker
                self._draw_marker(painter, self._point_near(a, b, end, 12), angle, kind)

            circle = style.get("circle")
            if circle:
                fill_kind, end = circle
                pos = self._point_near(a, b, end, 10)
                painter.save()
                painter.setBrush((Qt.blue if selected else Qt.black) if fill_kind=="filled" else Qt.white)
                painter.drawEllipse(QRectF(pos.x()-5, pos.y()-5, 10, 10))
                painter.restore()

    # simple API
    def set_link_type(self, lt: str):
        if lt != self.link_type:
            self.link_type = lt
            if getattr(self, "ti_type", None):
                self.ti_type.setText(self.link_type)
            self.update()

    def set_label(self, text: str):
        """Nastaví label vazby (kompatibilní s SetLabelCommand)."""
        self.label = text
        if text:
            if getattr(self, "ti_label", None) is None:
                # Vytvořit nový label handle
                self.ti_label = LabelHandle(self, "label", text)
                self._position_text()
            else:
                # Aktualizovat existující
                self.ti_label.setText(text)
        else:
            # Smazat label pokud je prázdný
            if getattr(self, "ti_label", None) is not None:
                self.scene().removeItem(self.ti_label)
                self.ti_label = None
        self.update()
        
    def set_card_src(self, text: str):
        self.card_src = text
        if self.ti_card_src:
            self.ti_card_src.setText(text)
        self.update()

    def set_card_dst(self, text: str):
        self.card_dst = text
        if self.ti_card_dst:
            self.ti_card_dst.setText(text)
        self.update()

    def remove_refs(self):
        for n in (self.src, self.dst):
            if getattr(n, "_links", None) is not None:
                try: n._links.remove(self)
                except ValueError: pass