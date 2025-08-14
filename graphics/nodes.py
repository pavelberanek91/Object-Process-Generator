from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QPen, QPainter
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem, QStyle
)
from constants import next_id
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
        self.setPen(QPen(Qt.black, 2))
        self._init_resize() # přidá gripy

    def boundingRect(self) -> QRectF:
        m = 8
        return super().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 12, 12)
        painter.drawText(self.rect(), Qt.AlignCenter, self.label)
        if option.state & QStyle.State_Selected:
            sel = QPen(Qt.blue, 2, Qt.DashLine)
            sel.setCosmetic(True)
            painter.setPen(sel)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(-6, -6, 6, 6), 12, 12)

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
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())
        painter.drawText(self.rect(), Qt.AlignCenter, self.label)
        if option.state & QStyle.State_Selected:
            sel = QPen(Qt.blue, 2, Qt.DashLine)
            sel.setCosmetic(True)
            painter.setPen(sel)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.rect().adjusted(-6, -6, 6, 6))

class StateItem(BaseNodeItem, QGraphicsRectItem):
    def __init__(self, parent_obj: ObjectItem, rect: QRectF, label: str = "State"):
        super().__init__(rect, parent=parent_obj)
        self.init_node("state", label)
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black, 1.5))
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

    def boundingRect(self) -> QRectF:
        m = 6
        return super().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(self.pen()); painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), 8, 8)
        painter.drawText(self.rect(), Qt.AlignCenter, self.label)
        if option.state & QStyle.State_Selected:
            sel = QPen(Qt.blue, 1.5, Qt.DashLine); sel.setCosmetic(True)
            painter.setPen(sel); painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(-4, -4, 4, 4), 8, 8)