from __future__ import annotations
from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QBrush, QPen, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem, QStyle
)
from utils.ids import next_id
from graphics.resize import ResizableMixin


class BaseNodeItem:
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
    def __init__(self, rect: QRectF, label: str = "Object"):
        super().__init__(rect)
        self.init_node("object", label)
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(QColor(0, 128, 0), 2))  # tmavě zelený obrys
        self._init_resize()  # přidá gripy

    def boundingRect(self) -> QRectF:
        m = 8
        return super().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 12, 12)

        # dostupná oblast pro text (pokud má stavy, posuneme text nahoru)
        states = [ch for ch in self.childItems() if isinstance(ch, StateItem)]
        rect_for_text = self.rect()
        if states:
            st_h = states[0].rect().height() + 6  # výška stavů + mezera
            rect_for_text = rect_for_text.adjusted(0, 0, 0, -st_h)

        # text (tučný Arial, černý)
        font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(font)
        painter.setPen(Qt.black)
        painter.drawText(rect_for_text, Qt.AlignCenter, self.label)

        if option.state & QStyle.State_Selected:
            sel = QPen(Qt.blue, 2, Qt.DashLine)
            sel.setCosmetic(True)
            painter.setPen(sel)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(-6, -6, 6, 6), 12, 12)

    def mouseDoubleClickEvent(self, event):
        # dvojklik kamkoli do objektu = přidání stavu
        if event.button() == Qt.LeftButton:
            from app import App  # lazy import, aby se nezacyklil
            App.instance().add_state(self, event.scenePos())
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
    def __init__(self, rect: QRectF, label: str = "Process"):
        super().__init__(rect)
        self.init_node("process", label)
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black, 2))
        self._init_resize()  # přidá gripy

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

    def paint(self, painter: QPainter, option, widget=None):
        # vykresli obrys (modrý)
        painter.setPen(QPen(QColor(0, 0, 128), 3))
        painter.setBrush(self.brush())
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

        # registruj se k rodiči - pro redu command at funguje presun s rodicem
        if not hasattr(parent_obj, "_states"):
            parent_obj._states = []
        parent_obj._states.append(self)

        # voláme bez argumentů, jako u ObjectItem a ProcessItem
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

        if option.state & QStyle.State_Selected:
            sel = QPen(Qt.blue, 1.5, Qt.DashLine)
            sel.setCosmetic(True)
            painter.setPen(sel)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(-4, -4, 4, 4), 8, 8)
