"""Generování vlastních ikon pro toolbar a UI.

Vytváří vektorové ikony přímo v kódu pomocí QPainter pro:
- Tvary prvků (object, process, state, link)
- Nástroje (cursor, delete, zoom in/out, reset zoom)
"""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QPainterPath
import math


def icon_shape(kind: str, size: int = 22) -> QIcon:
    """
    Vytvoří vektorovou ikonu pro daný typ prvku/nástroje.
    
    Args:
        kind: Typ ikony ("object", "process", "state", "link", "cursor", "delete", 
              "zoom_in", "zoom_out", "reset_zoom")
        size: Velikost ikony v pixelech (výchozí 22)
    
    Returns:
        QIcon s vykreslenou ikonou
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(Qt.black, 2)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    if kind == "cursor":
        arm_len=4
        thickness=2
        gap=2
        s = float(size)
        c = s / 2.0
        L = float(arm_len if arm_len is not None else max(4, int(s * 0.35)))
        t = float(max(1, thickness))
        g = float(max(0, gap))
        h = t / 2.0

        path = QPainterPath()

        # Horní rameno (obdélník)
        path.moveTo(c - h, c - g - L)
        path.lineTo(c + h, c - g - L)
        path.lineTo(c + h, c - g)
        path.lineTo(c - h, c - g)
        path.closeSubpath()

        # Dolní rameno
        path.moveTo(c - h, c + g)
        path.lineTo(c + h, c + g)
        path.lineTo(c + h, c + g + L)
        path.lineTo(c - h, c + g + L)
        path.closeSubpath()

        # Levé rameno
        path.moveTo(c - g - L, c - h)
        path.lineTo(c - g,     c - h)
        path.lineTo(c - g,     c + h)
        path.lineTo(c - g - L, c + h)
        path.closeSubpath()

        # Pravé rameno
        path.moveTo(c + g,     c - h)
        path.lineTo(c + g + L, c - h)
        path.lineTo(c + g + L, c + h)
        path.lineTo(c + g,     c + h)
        path.closeSubpath()

        # vykreslení
        p.setPen(Qt.NoPen)      # čistá výplň
        # případně: p.setPen(QPen(Qt.black, 1)) pro obrys
        p.setBrush(Qt.black)
        p.drawPath(path)

    if kind == "object":
        r = QRectF(3, 4, size - 6, size - 8)
        p.drawRoundedRect(r, 4, 4)

    elif kind == "process":
        r = QRectF(3, 4, size - 6, size - 8)
        p.drawEllipse(r)

    elif kind == "state":
        r = QRectF(5, 7, size - 10, size - 14)
        p.drawRoundedRect(r, 4, 4)

    elif kind == "link":
        path = QPainterPath(QPointF(4, size - 6))
        path.lineTo(size - 8, 6)
        p.drawPath(path)
        # šipka
        ax, ay = size - 8, 6
        bx, by = size - 14, 12
        ang = math.atan2(ay - by, ax - bx)
        L = 7
        p.drawLine(ax, ay, ax - L * math.cos(ang + math.pi / 6), ay - L * math.sin(ang + math.pi / 6))
        p.drawLine(ax, ay, ax - L * math.cos(ang - math.pi / 6), ay - L * math.sin(ang - math.pi / 6))

    elif kind == "delete":
        thickness  = 3
        gap  = 0
        arm_len = None
        s = float(size)
        c = QPointF(s/2.0, s/2.0)
        L = float(arm_len if arm_len is not None else max(4, int(s * 0.35)))
        t = float(max(1, thickness))
        g = float(max(0, gap))
        h = t / 2.0

        # Jednotkové směry pro diagonály: u = směr, v = kolmice (pro šířku pruhu)
        inv = 2**0.5
        u1 = QPointF(1.0/inv,  1.0/inv)   # směr "\"
        v1 = QPointF(-1.0/inv, 1.0/inv)   # kolmice k u1
        u2 = QPointF(1.0/inv, -1.0/inv)   # směr "/"
        v2 = QPointF( 1.0/inv, 1.0/inv)   # kolmice k u2

        def add_arm_rect(path: QPainterPath, u: QPointF, v: QPointF, sign: float):
            """Jeden obdélníkový „půl-pruh“ od mezery po konec ramene."""
            start = c + u * (sign * g)
            end   = c + u * (sign * (g + L))
            p1 = start + v * h
            p2 = end   + v * h
            p3 = end   - v * h
            p4 = start - v * h
            path.moveTo(p1); path.lineTo(p2); path.lineTo(p3); path.lineTo(p4); path.closeSubpath()

        # Sestavíme cestu ze 4 obdélníčků (2 diagonály × 2 směry od středu)
        path = QPainterPath()
        add_arm_rect(path, u1, v1, +1.0)
        add_arm_rect(path, u1, v1, -1.0)
        add_arm_rect(path, u2, v2, +1.0)
        add_arm_rect(path, u2, v2, -1.0)

        # vykreslení
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.red)
        p.drawPath(path)

    elif kind in ("zoom_in", "zoom_out"):
        # lupa
        cx, cy, r = size / 2 - 3, size / 2 - 3, size / 2 - 6
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.drawLine(cx + r - 1, cy + r - 1, size - 3, size - 3)  # držátko
        # plus/minus
        p.drawLine(cx - r / 2 + 1, cy, cx + r / 2 - 1, cy)
        if kind == "zoom_in":
            p.drawLine(cx, cy - r / 2 + 1, cx, cy + r / 2 - 1)

    elif kind == "reset_zoom":
        # def make_icon_R(size: int = 24, color=Qt.black) -> QIcon: TODO: takhle to chci refaktorovat

        # Vnitřní box pro R (mírný okraj od hran ikony)
        m  = size * 0.15
        bx = m
        by = m
        bw = size - 2*m
        bh = size - 2*m

        # Geometrie R (poměrově, aby se dalo snadno doladit)
        x0          = bx + bw * 0.10          # svislý dřík – X
        top         = by + bh * 0.05          # horní Y
        bot         = by + bh * 0.95          # dolní Y
        mid         = by + bh * 0.58          # napojení misky/nohy
        bowl_right  = bx + bw * 0.60          # pravý okraj misky
        bowl_topY   = by + bh * 0.10
        bowl_midY   = by + bh * 0.36
        leg_end_x   = bx + bw * 0.60          # konec šikmé nohy (X)

        # 1) svislý dřík
        path = QPainterPath()
        path.moveTo(x0, top)
        path.lineTo(x0, bot)
        p.drawPath(path)

        # 2) horní „mísa“ – dvě kvadratické Beziérky
        bowl = QPainterPath()
        bowl.moveTo(x0, top)
        bowl.quadTo(bowl_right, bowl_topY, bowl_right, bowl_midY)
        bowl.quadTo(bowl_right, mid, x0, mid)
        p.drawPath(bowl)

        # 3) šikmá noha
        leg = QPainterPath()
        leg.moveTo(x0, mid)
        leg.lineTo(leg_end_x, bot)
        p.drawPath(leg)

    p.end()
    return QIcon(pm)


def icon_std(scene, sp):
    """Nativní systémová ikonka (QStyle)."""
    return scene.style().standardIcon(sp)