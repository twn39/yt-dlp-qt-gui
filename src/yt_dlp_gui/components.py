from PySide6.QtWidgets import (
    QCheckBox, QWidget, QLabel, QProgressBar, QPushButton,
    QHBoxLayout, QVBoxLayout
)
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QColor
import qtawesome as qta

ICON_COLOR = "#E0E0E0"

class Switch(QCheckBox):
    """自定义切换开关组件"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(24)
        self.setMinimumWidth(80)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 切换开关的尺寸
        tw, th = 36, 18
        ty = (self.height() - th) / 2

        # 绘制轨道
        track_rect = QRect(0, int(ty), tw, th)
        if self.isChecked():
            track_color = QColor("#4A90E2") # Accent Blue
            thumb_pos = tw - th + 2
        else:
            track_color = QColor("#333333") # Subtle Dark
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

class TaskItemWidget(QWidget):
    """Modern card-like widget for a single download task"""

    # Signals for interactions
    start_clicked = Signal(int)
    stop_clicked = Signal(int)
    delete_clicked = Signal(int)

    def __init__(self, task_id: int, task_data: dict, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self._setup_ui()
        self.update_data(task_data)

    def _setup_ui(self):
        # Main Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 1. Icon / Type Indicator (Left)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setStyleSheet("""
            background-color: #2A2A2A;
            border-radius: 8px;
            border: 1px solid #333333;
        """)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Default icon
        icon = qta.icon("fa5s.video", color="#666666")
        self.icon_label.setPixmap(icon.pixmap(24, 24))
        layout.addWidget(self.icon_label)

        # 2. Central Info Area
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)

        # Row 1: Title
        self.title_label = QLabel("Loading...")
        self.title_label.setObjectName("task_title")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #E0E0E0;")
        info_layout.addWidget(self.title_label)

        # Row 2: Progress Bar
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(6)
        self.pbar.setTextVisible(False)
        self.pbar.setStyleSheet("""
            QProgressBar {
                background-color: #151515;
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #4A90E2;
                border-radius: 3px;
            }
        """)
        info_layout.addWidget(self.pbar)

        # Row 3: Meta Info (Status, Speed, ETA)
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(15)

        self.status_label = QLabel("Waiting")
        self.status_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")

        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet("color: #666666; font-size: 11px;")

        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet("color: #666666; font-size: 11px;")

        meta_layout.addWidget(self.status_label)
        meta_layout.addWidget(self.speed_label)
        meta_layout.addWidget(self.eta_label)
        meta_layout.addStretch()

        info_layout.addLayout(meta_layout)
        layout.addLayout(info_layout, stretch=1)

        # 3. Actions (Right)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        # Start/Retry Button
        self.btn_start = QPushButton()
        self.btn_start.setIcon(qta.icon("fa5s.play", color="#E0E0E0"))
        self.btn_start.setFixedSize(32, 32)
        self.btn_start.setToolTip("开始/重试")
        self.btn_start.clicked.connect(lambda: self.start_clicked.emit(self.task_id))
        self.btn_start.setStyleSheet(self._get_btn_style())
        actions_layout.addWidget(self.btn_start)

        # Stop Button
        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(qta.icon("fa5s.pause", color="#E0E0E0"))
        self.btn_stop.setFixedSize(32, 32)
        self.btn_stop.setToolTip("暂停/停止")
        self.btn_stop.clicked.connect(lambda: self.stop_clicked.emit(self.task_id))
        self.btn_stop.setStyleSheet(self._get_btn_style())
        actions_layout.addWidget(self.btn_stop)

        # Delete Button
        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(qta.icon("fa5s.trash-alt", color="#FF5252"))
        self.btn_delete.setFixedSize(32, 32)
        self.btn_delete.setToolTip("删除任务")
        self.btn_delete.clicked.connect(lambda: self.delete_clicked.emit(self.task_id))
        self.btn_delete.setStyleSheet(self._get_btn_style())
        self.btn_delete.setProperty("class", "danger")
        actions_layout.addWidget(self.btn_delete)

        layout.addLayout(actions_layout)

    def _get_btn_style(self):
        return """
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #333333;
                border: 1px solid #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """

    def update_data(self, data: dict):
        """Update widget with new task data"""
        if 'title' in data and data['title']:
            self.title_label.setText(data['title'])
        elif 'url' in data:
            self.title_label.setText(data['url'])

        if 'progress' in data and data['progress'] is not None:
            self.pbar.setValue(data['progress'])

        if 'speed' in data:
            self.speed_label.setText(f"{data['speed']}")

        if 'eta' in data:
            self.eta_label.setText(f"剩余: {data['eta']}")

        if 'status' in data:
            self._update_status(data['status'])

    def _update_status(self, status):
        """Update status label and icon"""
        status_map = {
            "downloading": ("正在下载", "#4A90E2", "fa5s.download"),
            "finished": ("已完成", "#4CAF50", "fa5s.check"),
            "error": ("错误", "#F44336", "fa5s.exclamation-circle"),
            "merging": ("合并中...", "#FF9800", "fa5s.object-group"),
            "cancelled": ("已取消", "#9E9E9E", "fa5s.ban"),
            "waiting": ("等待中", "#888888", "fa5s.clock")
        }

        text, color, icon_name = status_map.get(status, (status, "#888888", "fa5s.question"))

        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px;")

        # Update main icon based on status
        if status == "finished":
            icon = qta.icon(icon_name, color=color)
            self.icon_label.setPixmap(icon.pixmap(24, 24))

        # Actions visibility
        is_running = status in ["downloading", "merging"]
        self.btn_start.setVisible(not is_running)
        self.btn_stop.setVisible(is_running)
