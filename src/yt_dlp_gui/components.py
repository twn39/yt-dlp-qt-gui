from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox


class Switch(QCheckBox):
    """自定义切换开关组件"""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(24)
        self.setMinimumWidth(80)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 切换开关的尺寸
        tw, th = 36, 18
        ty = (self.height() - th) / 2

        # 绘制轨道
        track_rect = QRect(0, int(ty), tw, th)
        if self.isChecked():
            track_color = QColor("#4A90E2")  # Accent Blue
            thumb_pos = tw - th + 2
        else:
            track_color = QColor("#333333")  # Subtle Dark
            thumb_pos = 2

        painter.setBrush(track_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, th / 2, th / 2)

        # 绘制滑块
        thumb_rect = QRect(thumb_pos, int(ty) + 2, th - 4, th - 4)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(thumb_rect)

        # 绘制文本
        if self.text():
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                tw + 10,
                0,
                self.width() - tw - 10,
                self.height(),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.text(),
            )
