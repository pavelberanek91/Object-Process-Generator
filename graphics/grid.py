from __future__ import annotations
import math
from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene
from constants import GRID_SIZE

class GridScene(QGraphicsScene):
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        left = int(math.floor(rect.left())) - (int(math.floor(rect.left())) % GRID_SIZE)
        top  = int(math.floor(rect.top()))  - (int(math.floor(rect.top()))  % GRID_SIZE)
        lines = []
        for x in range(left, int(rect.right()) + GRID_SIZE, GRID_SIZE):
            lines.append((QPointF(x, rect.top()), QPointF(x, rect.bottom())))
        for y in range(top, int(rect.bottom()) + GRID_SIZE, GRID_SIZE):
            lines.append((QPointF(rect.left(), y), QPointF(rect.right(), y)))
        painter.setPen(QPen(Qt.lightGray, 0))
        for a, b in lines:
            painter.drawLine(a, b)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)