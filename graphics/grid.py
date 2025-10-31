"""Grid-scéna s kreslením snapovací mřížky.

Třída rozšiřuje QGraphicsScene a dokresluje jemnou mřížku na pozadí.
Mřížka je „hairline“ (šířka pera = 0), takže má vždy 1 px bez ohledu na zoom.
"""

from __future__ import annotations
import math
from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene
from constants import GRID_SIZE

class GridScene(QGraphicsScene):
    def __init__(self, parent=None):
        """Inicializuje GridScene s mřížkou zapnutou."""
        super().__init__(parent)
        self._draw_grid = True  # Flag pro zapínání/vypínání mřížky
    
    def set_draw_grid(self, enabled: bool) -> None:
        """Nastaví, zda se má kreslit mřížka."""
        self._draw_grid = enabled
    
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Vykreslí mřížku do pozadí scény."""

        # nejdřív necháme QGraphicsScene udělat své vlastní pozadí (pokud nějaké má)
        super().drawBackground(painter, rect)
        
        # Pokud je mřížka vypnutá, nevykreslujeme ji
        if not self._draw_grid:
            return

        # Zarovnání výchozích souřadnic mřížky na nejbližší nižší násobek GRID_SIZE.
        # Používá se floor() a pak modulo: tím zjistíme, o kolik jsme „odjetí“ od násobku.
        # Výsledkem je 'left'/'top' jako první svislá/vodorovná čára mřížky, která leží vlevo/nahoře od rect.
        left = int(math.floor(rect.left())) - (int(math.floor(rect.left())) % GRID_SIZE)
        top  = int(math.floor(rect.top()))  - (int(math.floor(rect.top()))  % GRID_SIZE)

        # Předpřipravíme si seznam úseček (jako dvojic bodů) pro rychlé vykreslení.
        lines = []

        # Svislé čáry mřížky: od zarovnaného 'left' až o jeden krok za rect.right()
        # (+GRID_SIZE proto, aby se jistě dokreslila i hraniční čára).
        for x in range(left, int(rect.right()) + GRID_SIZE, GRID_SIZE):
            lines.append((QPointF(x, rect.top()), QPointF(x, rect.bottom())))

        # Vodorovné čáry mřížky: analogicky od 'top' po 'bottom'
        for y in range(top, int(rect.bottom()) + GRID_SIZE, GRID_SIZE):
            lines.append((QPointF(rect.left(), y), QPointF(rect.right(), y)))

        # Nastavení pera: šířka 0 = „cosmetic pen“ (hairline),
        # tzn. bude mít vždy 1px bez ohledu na transformace/zoom.
        painter.setPen(QPen(Qt.lightGray, 0))

        # Vykreslení všech připravených čar mřížky.
        for a, b in lines:
            painter.drawLine(a, b)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Volitelné dokreslení do popředí (zde jen passthrough)."""
        super().drawForeground(painter, rect)