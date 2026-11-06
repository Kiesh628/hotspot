from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush

def create_mic_icon(state: str = "active", size: int = 24) -> QIcon:
    """
    Renders a vector microphone icon.
    state: 'active' (normal white/cyan), 'muted' (grey crossed out), 'error' (red crossed out)
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    color = QColor("#22c55e") if state == "active" else \
            QColor("#9ca3af") if state == "muted" else QColor("#ef4444")
    
    pen = QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Mic Capsule
    capsule_rect = QRectF(size * 0.35, size * 0.15, size * 0.3, size * 0.45)
    painter.drawRoundedRect(capsule_rect, size * 0.15, size * 0.15)

    # Stand arc
    arc_rect = QRectF(size * 0.22, size * 0.28, size * 0.56, size * 0.4)
    painter.drawArc(arc_rect, 0, -180 * 16)

    # Stem and Base
    painter.drawLine(QPointF(size * 0.5, size * 0.68), QPointF(size * 0.5, size * 0.85))
    painter.drawLine(QPointF(size * 0.32, size * 0.85), QPointF(size * 0.68, size * 0.85))

    # Diagonal slash line for muted or error
    if state in ("muted", "error"):
        slash_color = QColor("#ef4444") if state == "error" else QColor("#e5e7eb")
        slash_pen = QPen(slash_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(slash_pen)
        painter.drawLine(QPointF(size * 0.18, size * 0.18), QPointF(size * 0.82, size * 0.82))

    painter.end()
    return QIcon(pixmap)


def create_cam_icon(state: str = "active", size: int = 24) -> QIcon:
    """
    Renders a vector video camera icon.
    state: 'active' (normal white/cyan), 'muted' (grey crossed out), 'error' (red crossed out)
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    color = QColor("#3b82f6") if state == "active" else \
            QColor("#9ca3af") if state == "muted" else QColor("#ef4444")

    pen = QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Camera body
    body_rect = QRectF(size * 0.15, size * 0.25, size * 0.48, size * 0.5)
    painter.drawRoundedRect(body_rect, size * 0.08, size * 0.08)

    # Lens / Triangle projecting to the right
    painter.drawLine(QPointF(size * 0.63, size * 0.38), QPointF(size * 0.85, size * 0.26))
    painter.drawLine(QPointF(size * 0.85, size * 0.26), QPointF(size * 0.85, size * 0.74))
    painter.drawLine(QPointF(size * 0.85, size * 0.74), QPointF(size * 0.63, size * 0.62))

    # Diagonal slash line for muted or error
    if state in ("muted", "error"):
        slash_color = QColor("#ef4444") if state == "error" else QColor("#e5e7eb")
        slash_pen = QPen(slash_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(slash_pen)
        painter.drawLine(QPointF(size * 0.15, size * 0.15), QPointF(size * 0.85, size * 0.85))

    painter.end()
    return QIcon(pixmap)


def create_mode_icon(mode: str = "control", size: int = 24) -> QIcon:
    """
    Renders mode icons:
    'control': Gamepad / controller vector icon
    'select': Cursor pointer / hand vector icon
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if mode == "control":
        # Game Controller
        pen = QPen(QColor("#22c55e"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        # Rounded controller body
        painter.drawRoundedRect(QRectF(size * 0.15, size * 0.28, size * 0.7, size * 0.44), size * 0.2, size * 0.2)
        # D-pad cross on left
        painter.drawLine(QPointF(size * 0.35, size * 0.42), QPointF(size * 0.35, size * 0.58))
        painter.drawLine(QPointF(size * 0.27, size * 0.5), QPointF(size * 0.43, size * 0.5))
        # Buttons on right
        painter.setBrush(QColor("#22c55e"))
        painter.drawEllipse(QPointF(size * 0.63, size * 0.45), size * 0.04, size * 0.04)
        painter.drawEllipse(QPointF(size * 0.71, size * 0.53), size * 0.04, size * 0.04)
    else:
        # Select / Mouse Pointer
        pen = QPen(QColor("#60a5fa"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QColor("#3b82f6"))
        # Arrow pointer polygon
        points = [
            QPointF(size * 0.25, size * 0.15),
            QPointF(size * 0.25, size * 0.75),
            QPointF(size * 0.42, size * 0.60),
            QPointF(size * 0.55, size * 0.85),
            QPointF(size * 0.68, size * 0.78),
            QPointF(size * 0.54, size * 0.54),
            QPointF(size * 0.75, size * 0.54),
        ]
        painter.drawPolygon(points)

    painter.end()
    return QIcon(pixmap)
