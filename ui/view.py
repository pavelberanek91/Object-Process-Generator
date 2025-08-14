from __future__ import annotations
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsView, QGraphicsItem, QGraphicsPathItem
from constants import Mode, NODE_W, NODE_H, STATE_W, STATE_H
from graphics.nodes import ObjectItem

class EditorView(QGraphicsView):
    def __init__(self, scene, app):
        super().__init__(scene)
        self.app = app
        self.setRenderHints(self.renderHints() | self.renderHints().Antialiasing)
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
            self.app.zoom_in() if event.angleDelta().y() > 0 else self.app.zoom_out()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        mode = self.app.mode
        if mode == Mode.ADD_OBJECT:
            self.app.add_object(scene_pos); return
        elif mode == Mode.ADD_PROCESS:
            self.app.add_process(scene_pos); return
        elif mode == Mode.ADD_STATE:
            item = self.scene().itemAt(scene_pos, self.transform())
            if isinstance(item, ObjectItem):
                self.app.add_state(item, scene_pos); return
        elif mode == Mode.ADD_LINK:
            self.app.handle_link_click(scene_pos); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        mode = self.app.mode
        if mode in (Mode.ADD_OBJECT, Mode.ADD_PROCESS):
            self.update_ghost(scene_pos); self.clear_temp_link()
        elif mode == Mode.ADD_STATE:
            self.update_ghost(scene_pos); self.clear_temp_link()
        elif mode == Mode.ADD_LINK:
            if self.app.pending_link_src is not None:
                self.update_temp_link(scene_pos)
            else:
                self.clear_temp_link()
            self.clear_ghost()
        else:
            self.clear_ghost(); self.clear_temp_link()
        super().mouseMoveEvent(event)

    def clear_overlays(self):
        self.clear_ghost(); self.clear_temp_link()

    def clear_ghost(self):
        if self.ghost_item is not None:
            self.scene().removeItem(self.ghost_item); self.ghost_item = None; self.ghost_kind = None

    def update_ghost(self, scene_pos: QPointF):
        from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
        mode = self.app.mode
        if mode == Mode.ADD_OBJECT:
            if self.ghost_kind != 'object':
                self.clear_ghost()
                gi = QGraphicsRectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
                gi.setPen(QPen(Qt.darkGray, 2, Qt.DashLine)); gi.setBrush(Qt.NoBrush)
                gi.setZValue(10); gi.setFlag(QGraphicsItem.ItemIsSelectable, False)
                gi.setAcceptedMouseButtons(Qt.NoButton)
                self.scene().addItem(gi); self.ghost_item = gi; self.ghost_kind = 'object'
            self.ghost_item.setPos(self.app.snap(scene_pos))
        elif mode == Mode.ADD_PROCESS:
            if self.ghost_kind != 'process':
                self.clear_ghost()
                gi = QGraphicsEllipseItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
                gi.setPen(QPen(Qt.darkGray, 2, Qt.DashLine)); gi.setBrush(Qt.NoBrush)
                gi.setZValue(10); gi.setFlag(QGraphicsItem.ItemIsSelectable, False)
                gi.setAcceptedMouseButtons(Qt.NoButton)
                self.scene().addItem(gi); self.ghost_item = gi; self.ghost_kind = 'process'
            self.ghost_item.setPos(self.app.snap(scene_pos))
        elif mode == Mode.ADD_STATE:
            item = self.scene().itemAt(scene_pos, self.transform())
            if not isinstance(item, ObjectItem):
                self.clear_ghost(); return
            p = item.mapFromScene(self.app.snap(scene_pos)); r = item.rect()
            x = min(max(p.x() - STATE_W/2, r.left()+6),  r.right()-STATE_W-6)
            y = min(max(p.y() - STATE_H/2, r.top()+6),   r.bottom()-STATE_H-6)
            rect = QRectF(x, y, STATE_W, STATE_H)
            if self.ghost_kind != 'state' or (self.ghost_item and self.ghost_item.parentItem() is not item):
                self.clear_ghost()
                gi = QGraphicsRectItem(rect, parent=item)
                gi.setPen(QPen(Qt.darkGray, 1.5, Qt.DashLine)); gi.setBrush(Qt.NoBrush)
                gi.setZValue(10); gi.setFlag(QGraphicsItem.ItemIsSelectable, False)
                gi.setAcceptedMouseButtons(Qt.NoButton)
                self.ghost_item = gi; self.ghost_kind = 'state'
            else:
                self.ghost_item.setRect(rect)

    def clear_temp_link(self):
        if self.temp_link is not None:
            self.scene().removeItem(self.temp_link); self.temp_link = None

    def update_temp_link(self, scene_pos: QPointF):
        src = self.app.pending_link_src
        if src is None: self.clear_temp_link(); return
        a = src.mapToScene(src.boundingRect()).boundingRect().center()
        path = QPainterPath(a); path.lineTo(scene_pos)
        if self.temp_link is None:
            self.temp_link = QGraphicsPathItem()
            self.temp_link.setPen(QPen(Qt.darkGray, 1, Qt.DashLine))
            self.temp_link.setZValue(-2)
            self.temp_link.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.temp_link.setAcceptedMouseButtons(Qt.NoButton)
            self.scene().addItem(self.temp_link)
        self.temp_link.setPath(path)

    def keyPressEvent(self, event):
        if (event.key() == Qt.Key_Escape 
                and self.app.mode == Mode.ADD_LINK 
                and self.app.pending_link_src is not None):
            self.app.cancel_link_creation()
            event.accept()
            return
        super().keyPressEvent(event)