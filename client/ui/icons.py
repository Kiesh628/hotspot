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


def create_eye_icon(visible: bool = True, size: int = 20) -> QIcon:
    """
    Renders a vector eye icon for password show/hide toggle.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    color = QColor("#a1a1aa") if visible else QColor("#71717a")
    pen = QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Eye outline (two arcs or oval)
    eye_rect = QRectF(size * 0.15, size * 0.28, size * 0.7, size * 0.44)
    painter.drawRoundedRect(eye_rect, size * 0.35, size * 0.22)

    # Pupil
    painter.setBrush(color)
    painter.drawEllipse(QPointF(size * 0.5, size * 0.5), size * 0.12, size * 0.12)

    # Slash if hidden
    if not visible:
        slash_pen = QPen(QColor("#ef4444"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(slash_pen)
        painter.drawLine(QPointF(size * 0.18, size * 0.82), QPointF(size * 0.82, size * 0.18))

    painter.end()
    return QIcon(pixmap)


def create_sidebar_icon(visible: bool = True, size: int = 20) -> QIcon:
    """
    Renders a vector icon representing a window sidebar partition toggle.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    color = QColor("#a1a1aa") if visible else QColor("#52525b")
    pen = QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Outer window frame
    frame = QRectF(size * 0.15, size * 0.15, size * 0.7, size * 0.7)
    painter.drawRoundedRect(frame, size * 0.1, size * 0.1)

    # Vertical partition dividing canvas and sidebar
    partition_x = size * 0.62
    painter.drawLine(QPointF(partition_x, size * 0.15), QPointF(partition_x, size * 0.85))

    # Fill sidebar portion if visible
    if visible:
        painter.fillRect(QRectF(partition_x, size * 0.15, size * 0.23, size * 0.7), QColor(96, 165, 250, 90))

    painter.end()
    return QIcon(pixmap)
