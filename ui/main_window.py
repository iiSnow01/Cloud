import asyncio
import os
import shutil
import tempfile
import time
from datetime import datetime

import qasync
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.downloader import download_file_from_telegram
from core.uploader import upload_file_to_telegram
from db.local_db import get_all_files


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def format_size(size: int) -> str:
    if size >= 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


def parse_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%b %d, %H:%M")
    except Exception:
        return date_str


def visual_for(file_type: str, filename: str) -> tuple[str, str]:
    ext = os.path.splitext(filename.lower())[1]
    if file_type == "folder" or ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        return "ZIP", "#e9ddff"
    if file_type == "image" or ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
        return "IMG", "#fde6d7"
    if file_type == "video" or ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        return "VID", "#ffe0ea"
    if ext == ".pdf":
        return "PDF", "#fde2e2"
    if ext in {".xls", ".xlsx", ".csv"}:
        return "XLS", "#dff7e3"
    return "DOC", "#e5f0ff"


class NoticeBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            """
            QFrame {
                background: #f6f8fb;
                border: 1px solid #d8e0ea;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: none;
                color: #243041;
            }
            QProgressBar {
                background: #dfe7f0;
                border: none;
                border-radius: 4px;
                min-height: 8px;
                max-height: 8px;
            }
            QProgressBar::chunk {
                background: #2b7fff;
                border-radius: 4px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 700;")
        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("font-size: 11px; color: #536273;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()

        layout.addWidget(self.title_label)
        layout.addWidget(self.desc_label)
        layout.addWidget(self.progress_bar)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out)
        self.hide()

    def show_alert(self, title, desc, show_progress=False, auto_hide_ms=3000):
        self.title_label.setText(title)
        self.desc_label.setText(desc)
        self.progress_bar.setVisible(show_progress)
        if show_progress:
            self.progress_bar.setValue(0)
        self.show()
        self.raise_()
        if auto_hide_ms > 0:
            self.hide_timer.start(auto_hide_ms)
        else:
            self.hide_timer.stop()

    def update_progress(self, desc, percent):
        self.desc_label.setText(desc)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(int(percent))
        self.show()

    def fade_out(self):
        self.hide()

    def apply_theme(self, theme_name):
        return


class FileCard(QFrame):
    def __init__(self, msg_id, filename, meta_text, file_type, on_open, on_download, parent=None):
        super().__init__(parent)
        self.msg_id = msg_id
        self.filename = filename
        self.on_open = on_open
        self.on_download = on_download

        short, bg = visual_for(file_type, filename)
        self.setFixedSize(190, 190)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            FileCard {
                background: white;
                border: 1px solid #dfe5ec;
                border-radius: 14px;
            }
            FileCard:hover {
                border: 1px solid #96bfff;
                background: #fbfdff;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.icon_label = QLabel(short)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setStyleSheet(
            f"background: {bg}; border-radius: 12px; color: #223047; font-size: 18px; font-weight: 800;"
        )
        layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.name_label = QLabel(filename)
        self.name_label.setWordWrap(True)
        self.name_label.setFixedHeight(44)
        self.name_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #1f2937;")
        layout.addWidget(self.name_label)

        self.meta_label = QLabel(meta_text)
        self.meta_label.setStyleSheet("font-size: 11px; color: #667789;")
        layout.addWidget(self.meta_label)
        layout.addStretch()

    def update_icon(self, pixmap_path):
        try:
            pixmap = QPixmap(pixmap_path).scaled(
                self.icon_label.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.icon_label.setPixmap(pixmap)
            self.icon_label.setText("")
            self.icon_label.setStyleSheet("border-radius: 12px; background: transparent;")
        except RuntimeError:
            return

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_open(self.msg_id, self.filename)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Open", lambda: self.on_open(self.msg_id, self.filename))
        menu.addAction("Save", lambda: self.on_download(self.msg_id, self.filename))
        menu.exec(event.globalPos())


class RecentItem(QFrame):
    def __init__(self, msg_id, filename, date_text, size_text, file_type, on_open, on_download, parent=None):
        super().__init__(parent)
        self.msg_id = msg_id
        self.filename = filename
        self.on_open = on_open
        self.on_download = on_download

        short, bg = visual_for(file_type, filename)
        self.setStyleSheet(
            """
            RecentItem {
                background: white;
                border: 1px solid #dfe5ec;
                border-radius: 12px;
            }
            RecentItem:hover {
                border: 1px solid #96bfff;
                background: #fbfdff;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.icon_label = QLabel(short)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(46, 46)
        self.icon_label.setStyleSheet(
            f"background: {bg}; border-radius: 10px; color: #223047; font-size: 12px; font-weight: 800;"
        )
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        self.name_label = QLabel(filename)
        self.name_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #1f2937;")
        self.date_label = QLabel(date_text)
        self.date_label.setStyleSheet("font-size: 11px; color: #667789;")
        text_col.addWidget(self.name_label)
        text_col.addWidget(self.date_label)
        layout.addLayout(text_col, 1)

        self.size_label = QLabel(size_text)
        self.size_label.setStyleSheet("font-size: 11px; color: #667789;")
        layout.addWidget(self.size_label)

        open_btn = QPushButton("Open")
        save_btn = QPushButton("Save")
        for btn in (open_btn, save_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(60, 32)
            btn.setStyleSheet(
                """
                QPushButton {
                    background: #f5f8fc;
                    border: 1px solid #d7e0ea;
                    border-radius: 8px;
                    color: #243041;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    border: 1px solid #96bfff;
                    background: #eef5ff;
                }
                """
            )
        open_btn.clicked.connect(lambda: self.on_open(self.msg_id, self.filename))
        save_btn.clicked.connect(lambda: self.on_download(self.msg_id, self.filename))
        layout.addWidget(open_btn)
        layout.addWidget(save_btn)

    def update_icon(self, pixmap_path):
        try:
            pixmap = QPixmap(pixmap_path).scaled(
                self.icon_label.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.icon_label.setPixmap(pixmap)
            self.icon_label.setText("")
            self.icon_label.setStyleSheet("border-radius: 10px; background: transparent;")
        except RuntimeError:
            return


class MacTitleBar(QFrame):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self._drag_offset = None
        self.setFixedHeight(46)
        self.setStyleSheet(
            """
            MacTitleBar {
                background: #ffffff;
                border-bottom: 1px solid #d7e0ea;
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QLabel {
                background: transparent;
                border: none;
                color: #243041;
            }
            QPushButton {
                border: none;
                border-radius: 7px;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        controls = QWidget()
        controls.setFixedWidth(74)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self.min_btn = self._build_dot("#febc2e", "Minimize")
        self.max_btn = self._build_dot("#28c840", "Maximize")
        self.close_btn = self._build_dot("#ff5f57", "Close")
        self.close_btn.clicked.connect(self.window.close)
        self.min_btn.clicked.connect(self.window.showMinimized)
        self.max_btn.clicked.connect(self.toggle_maximize)

        controls_layout.addWidget(self.min_btn)
        controls_layout.addWidget(self.max_btn)
        controls_layout.addWidget(self.close_btn)
        controls_layout.addStretch()

        self.title_label = QLabel(self.window.windowTitle())
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 800;")

        left_spacer = QWidget()
        left_spacer.setFixedWidth(74)

        layout.addWidget(left_spacer)
        layout.addStretch()
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(controls)

    def _build_dot(self, color: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setFixedSize(14, 14)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            f"""
            QPushButton {{
                background: {color};
                border: 1px solid rgba(0, 0, 0, 0.14);
                border-radius: 7px;
            }}
            QPushButton:hover {{
                border: 1px solid rgba(0, 0, 0, 0.28);
            }}
            """
        )
        return button

    def toggle_maximize(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and not self.window.isMaximized()
        ):
            self.window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()
            event.accept()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cloudgram")
        self.resize(1100, 760)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setStyleSheet("QMainWindow { background: #dfe6ee; }")
        self.current_category = "All files"

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("WindowShell")
        shell.setStyleSheet(
            """
            #WindowShell {
                background: #f5f7fb;
                border: 1px solid #d7e0ea;
                border-radius: 16px;
            }
            """
        )
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.title_bar = MacTitleBar(self)
        shell_layout.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(
            "QFrame { background: #eef2f7; border-right: 1px solid #d8e0ea; border-bottom-left-radius: 16px; }"
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 20, 18, 18)
        sidebar_layout.setSpacing(14)

        title = QLabel("Cloudgram")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #18212b;")
        subtitle = QLabel("Telegram file organizer")
        subtitle.setStyleSheet("font-size: 11px; color: #667789;")
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet(
            """
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
                color: #334155;
            }
            QListWidget::item {
                height: 42px;
                border-radius: 10px;
                margin: 2px 0;
                padding-left: 12px;
                font-size: 13px;
                font-weight: 700;
            }
            QListWidget::item:selected {
                background: white;
                border: 1px solid #d7e0ea;
                color: #111827;
            }
            QListWidget::item:hover:!selected {
                background: #e4ebf3;
            }
            """
        )
        for text in ("All files", "Folders", "Gallery", "Uploads"):
            item = QListWidgetItem(text)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        self.nav_list.itemSelectionChanged.connect(self.on_category_changed)
        sidebar_layout.addWidget(self.nav_list)
        sidebar_layout.addStretch()

        self.index_label = QLabel("Local index: 0 files")
        self.index_label.setWordWrap(True)
        self.index_label.setStyleSheet("font-size: 11px; color: #667789;")
        sidebar_layout.addWidget(self.index_label)
        
        phone_desc = os.environ.get("CLOUDGRAM_OWNER_PHONE", "")
        if not phone_desc or phone_desc == "Unknown" or phone_desc == "None":
            phone_desc = "Signed In"
            
        profile_wrap = QWidget()
        profile_layout = QVBoxLayout(profile_wrap)
        profile_layout.setContentsMargins(0, 14, 0, 0)
        profile_layout.setSpacing(6)
        
        phone_label = QLabel(f"\U0001F4F1 {phone_desc}")
        phone_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #1f2937;")
        
        logout_btn = QPushButton("Log out")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setFixedHeight(30)
        logout_btn.setStyleSheet("""
            QPushButton { background: #ffecec; border: 1px solid #f1a8a8; border-radius: 8px; color: #b91c1c; font-size: 11px; font-weight: 600; }
            QPushButton:hover { background: #ffdada; }
        """)
        logout_btn.clicked.connect(self.action_logout)
        
        profile_layout.addWidget(phone_label)
        profile_layout.addWidget(logout_btn)
        sidebar_layout.addWidget(profile_wrap)

        body_layout.addWidget(sidebar)

        content = QFrame()
        content.setStyleSheet("QFrame { background: #f5f7fb; border-bottom-right-radius: 16px; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 22, 24, 22)
        content_layout.setSpacing(14)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        self.hero_title = QLabel("All files")
        self.hero_title.setStyleSheet("font-size: 28px; font-weight: 800; color: #111827;")
        self.hero_subtitle = QLabel("Files already indexed from your Telegram Saved Messages.")
        self.hero_subtitle.setStyleSheet("font-size: 12px; color: #667789;")
        header_text.addWidget(self.hero_title)
        header_text.addWidget(self.hero_subtitle)
        header.addLayout(header_text)
        header.addStretch()

        self.count_label = QLabel("0 items")
        self.count_label.setStyleSheet(
            "background: white; border: 1px solid #d7e0ea; border-radius: 12px; padding: 10px 14px; font-size: 12px; font-weight: 700; color: #243041;"
        )
        header.addWidget(self.count_label)
        content_layout.addLayout(header)

        toolbar = QFrame()
        toolbar.setStyleSheet("QFrame { background: white; border: 1px solid #d7e0ea; border-radius: 14px; }")
        toolbar_row = QHBoxLayout(toolbar)
        toolbar_row.setContentsMargins(14, 14, 14, 14)
        toolbar_row.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search files")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedHeight(42)
        self.search_box.setStyleSheet(
            "QLineEdit { background: #f7f9fc; border: 1px solid #d7e0ea; border-radius: 10px; padding: 0 12px; font-size: 13px; color: #243041; }"
            " QLineEdit:focus { border: 1px solid #7baeff; background: white; }"
        )
        self.search_box.textChanged.connect(self.load_files)
        toolbar_row.addWidget(self.search_box, 1)

        self.sync_btn = QPushButton("Sync Telegram")
        self.upload_btn = QPushButton("Upload")
        for btn in (self.sync_btn, self.upload_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(42)
            btn.setStyleSheet(
                """
                QPushButton {
                    background: #f5f8fc;
                    border: 1px solid #d7e0ea;
                    border-radius: 10px;
                    padding: 0 16px;
                    color: #243041;
                    font-size: 12px;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background: #eef5ff;
                    border: 1px solid #96bfff;
                }
                QPushButton:disabled {
                    color: #94a3b8;
                }
                """
            )
        self.sync_btn.clicked.connect(self.action_sync_telegram)

        self.upload_menu = QMenu(self)
        self.upload_menu.addAction("Upload file(s)", self.action_upload_file)
        self.upload_menu.addAction("Upload folder as zip", self.action_upload_folder)
        self.upload_btn.setMenu(self.upload_menu)
        toolbar_row.addWidget(self.sync_btn)
        toolbar_row.addWidget(self.upload_btn)
        content_layout.addWidget(toolbar)

        self.toast = NoticeBar()
        content_layout.addWidget(self.toast)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(14)

        self.pinned_title = QLabel("Pinned")
        self.pinned_title.setStyleSheet("font-size: 12px; font-weight: 800; color: #667789;")
        self.pinned_wrap = QWidget()
        self.pinned_grid = QGridLayout(self.pinned_wrap)
        self.pinned_grid.setContentsMargins(0, 0, 0, 0)
        self.pinned_grid.setHorizontalSpacing(14)
        self.pinned_grid.setVerticalSpacing(14)

        self.results_title = QLabel("Items")
        self.results_title.setStyleSheet("font-size: 12px; font-weight: 800; color: #667789;")
        self.results_wrap = QWidget()
        self.results_layout = QVBoxLayout(self.results_wrap)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(10)

        self.scroll_layout.addWidget(self.pinned_title)
        self.scroll_layout.addWidget(self.pinned_wrap)
        self.scroll_layout.addWidget(self.results_title)
        self.scroll_layout.addWidget(self.results_wrap)
        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_content)
        content_layout.addWidget(self.scroll_area, 1)

        body_layout.addWidget(content, 1)
        shell_layout.addWidget(body, 1)
        root.addWidget(shell)



    def on_category_changed(self):
        items = self.nav_list.selectedItems()
        if not items:
            return
        self.current_category = items[0].text().strip()
        self.hero_title.setText(self.current_category)
        copy = {
            "All files": "Files already indexed from your Telegram Saved Messages.",
            "Folders": "Archive items synced from Telegram or uploaded as zipped folders.",
            "Gallery": "Photos and videos from Telegram Saved Messages.",
            "Uploads": "Documents and general files from Telegram.",
        }
        self.hero_subtitle.setText(copy.get(self.current_category, "Telegram library"))
        self.load_files()

    def _filter_rows(self, rows):
        query = self.search_box.text().lower().strip()
        filtered = []
        for row in rows:
            _, _, name, _, file_type, _, _, _ = row
            if self.current_category == "Folders" and file_type != "folder":
                continue
            if self.current_category == "Gallery" and file_type not in ("image", "video"):
                continue
            if self.current_category == "Uploads" and file_type != "document":
                continue
            if query and query not in name.lower():
                continue
            filtered.append(row)
        return filtered

    def load_files(self):
        rows = get_all_files()
        filtered_rows = self._filter_rows(rows)
        self.index_label.setText(f"Local index: {len(rows)} files")
        self.count_label.setText(f"{len(filtered_rows)} items")
        self._render_rows(filtered_rows)

    def _render_rows(self, rows):
        clear_layout(self.pinned_grid)
        clear_layout(self.results_layout)

        pinned_rows = [row for row in rows if row[6]]
        other_rows = [row for row in rows if not row[6]]

        self.pinned_title.setVisible(bool(pinned_rows))
        self.pinned_wrap.setVisible(bool(pinned_rows))
        self.results_title.setText("Gallery" if self.current_category == "Gallery" else "Items")

        for index, row in enumerate(pinned_rows):
            _, msg_id, name, size, file_type, date_str, _, _ = row
            card = FileCard(
                msg_id,
                name,
                f"{format_size(size)}   |   {parse_date(date_str)}",
                file_type,
                self.handle_open,
                self.handle_download,
            )
            self.pinned_grid.addWidget(card, index // 4, index % 4)
            if file_type in ("image", "video"):
                self._schedule_coro(self.load_thumbnail(msg_id, card))

        if not other_rows and not pinned_rows:
            empty = QLabel("Nothing to show in this view.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "background: white; border: 1px solid #d7e0ea; border-radius: 14px; padding: 28px; font-size: 13px; color: #667789;"
            )
            self.results_layout.addWidget(empty)
            return

        if self.current_category == "Gallery":
            grid_wrap = QWidget()
            grid = QGridLayout(grid_wrap)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)
            for index, row in enumerate(other_rows):
                _, msg_id, name, size, file_type, date_str, _, _ = row
                card = FileCard(
                    msg_id,
                    name,
                    f"{format_size(size)}   |   {parse_date(date_str)}",
                    file_type,
                    self.handle_open,
                    self.handle_download,
                )
                grid.addWidget(card, index // 4, index % 4)
                if file_type in ("image", "video"):
                    self._schedule_coro(self.load_thumbnail(msg_id, card))
            self.results_layout.addWidget(grid_wrap)
            return

        for row in other_rows:
            _, msg_id, name, size, file_type, date_str, _, _ = row
            item = RecentItem(
                msg_id,
                name,
                parse_date(date_str),
                format_size(size),
                file_type,
                self.handle_open,
                self.handle_download,
            )
            self.results_layout.addWidget(item)
            if file_type in ("image", "video"):
                self._schedule_coro(self.load_thumbnail(msg_id, item))



    @qasync.asyncSlot()
    async def action_logout(self):
        from cloud_auth.login import get_client, SESSION_NAME

        client = get_client()
        try:
            await client.log_out()
        except Exception:
            pass
        try:
            await client.disconnect()
        except Exception:
            pass

        for suffix in (".session", ".session-journal"):
            session_path = f"{SESSION_NAME}{suffix}"
            if os.path.exists(session_path):
                try:
                    os.remove(session_path)
                except Exception:
                    pass

        import sys
        sys.exit(0)

    def _schedule_coro(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                coro.close()
            except Exception:
                pass
            return
        loop.create_task(coro)

    async def load_thumbnail(self, message_id, widget):
        thumb_dir = os.path.join(os.environ.get("TEMP", ""), "cloudgram_thumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"thumb_{message_id}.jpg")
        if not os.path.exists(thumb_path):
            try:
                await download_file_from_telegram(message_id, thumb_path, is_thumbnail=True)
            except Exception:
                return
        if os.path.exists(thumb_path):
            try:
                widget.update_icon(thumb_path)
            except RuntimeError:
                return

    @qasync.asyncSlot()
    async def action_sync_telegram(self):
        self.sync_btn.setEnabled(False)
        self.toast.show_alert("Syncing", "Reading Telegram Saved Messages...", True, 0)
        try:
            from core.syncer import sync_from_telegram

            synced = await sync_from_telegram(
                status_callback=lambda msg: print(f"Sync-Log: {msg}", flush=True)
            )
            self.load_files()
            self.toast.show_alert("Sync complete", f"Imported {synced} item(s) from Telegram.", False, 4000)
        except asyncio.TimeoutError:
            self.toast.show_alert("Sync failed", "Telegram connection timed out.", False, 5000)
        except Exception as e:
            self.toast.show_alert("Sync failed", str(e), False, 5000)
        finally:
            self.sync_btn.setEnabled(True)

    @qasync.asyncSlot()
    async def action_upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select file to upload")
        if file_path:
            await self.do_upload(file_path)

    @qasync.asyncSlot()
    async def action_upload_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select folder to upload")
        if folder_path:
            folder_name = os.path.basename(folder_path) or "Archive"
            temp_zip = os.path.join(tempfile.gettempdir(), folder_name)
            zip_path = shutil.make_archive(temp_zip, "zip", folder_path)
            await self.do_upload(zip_path, override_name=f"{folder_name}.zip", override_type="folder")

    async def do_upload(self, file_path, override_name=None, override_type=None):
        self.upload_btn.setEnabled(False)
        filename = override_name or os.path.basename(file_path)
        self.toast.show_alert("Uploading", f"Preparing {filename}...", True, 0)

        last_time = time.time()
        last_bytes = 0

        def progress_cb(current, total):
            nonlocal last_time, last_bytes
            now = time.time()
            elapsed = now - last_time
            if elapsed > 0.5 or current == total:
                speed = (current - last_bytes) / elapsed if elapsed > 0 else 0
                speed_str = format_size(int(speed)) + "/s" if speed > 0 else "0 B/s"
                pct = (current / total) * 100 if total else 0
                self.toast.update_progress(f"{pct:.1f}% | {speed_str} | {filename}", int(pct))
                last_time = now
                last_bytes = current

        try:
            await upload_file_to_telegram(file_path, progress_callback=progress_cb, override_type=override_type)
            self.load_files()
            self.toast.show_alert("Uploaded", f"{filename} uploaded.", False, 3000)
        except Exception as e:
            self.toast.show_alert("Upload failed", str(e), False, 5000)
        finally:
            self.upload_btn.setEnabled(True)

    @qasync.asyncSlot()
    async def handle_download(self, message_id, filename):
        dest_path, _ = QFileDialog.getSaveFileName(self, "Save file", filename)
        if not dest_path:
            return

        self.toast.show_alert("Downloading", f"Saving {filename}...", True, 0)
        try:
            ok = await download_file_from_telegram(message_id, dest_path)
            if ok:
                self.toast.show_alert("Saved", f"Saved {filename}.", False, 3000)
        except Exception as e:
            self.toast.show_alert("Download failed", str(e), False, 5000)

    @qasync.asyncSlot()
    async def handle_open(self, message_id, filename):
        temp_dir = os.path.join(os.environ.get("TEMP", ""), "cloudgram_cache")
        os.makedirs(temp_dir, exist_ok=True)
        dest_path = os.path.join(temp_dir, filename)
        self.toast.show_alert("Opening", f"Fetching {filename}...", True, 0)
        try:
            ok = await download_file_from_telegram(message_id, dest_path)
            if ok:
                self.toast.show_alert("Ready", f"Opening {filename}.", False, 2000)
                os.startfile(dest_path)
        except Exception as e:
            self.toast.show_alert("Open failed", str(e), False, 5000)
