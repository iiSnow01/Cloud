from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QListWidget, QListWidgetItem, QProgressBar, QGridLayout, QScrollArea, QFileDialog, QMessageBox, QMenu, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QTimer, QRect, QPoint, QEasingCurve, QParallelAnimationGroup
import qasync
import asyncio
import os
import time
import shutil
import tempfile
from datetime import datetime
from core.uploader import upload_file_to_telegram
from core.downloader import download_file_from_telegram
from db.local_db import get_all_files

# Google integrations (graceful no-op if packages not yet installed)
try:
    from cloud_auth.google_auth import is_google_connected, connect_google_async, disconnect_google
    from core.google_photos import list_media_items, download_media as gp_download_media, download_thumbnail as gp_download_thumbnail
    from core.gmail_sync import list_messages_with_attachments, download_attachment as gmail_download_attachment
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    def is_google_connected(): return False

class ToastNotification(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 80)
        self.setStyleSheet("""
            ToastNotification {
                background-color: #2b2b2b;
                border-radius: 12px;
                border: 1px solid #444;
            }
            QLabel { color: #f2f2f2; font-family: 'Segoe UI', Arial; border: none; }
            QProgressBar {
                background-color: #404040; border-radius: 4px; max-height: 5px; border: none;
            }
            QProgressBar::chunk { background-color: #0078D7; border-radius: 4px; }
        """)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        
        self.title_label = QLabel("Notification")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.desc_label = QLabel("")
        self.desc_label.setStyleSheet("font-size: 11px; color: #cccccc;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.desc_label)
        layout.addWidget(self.progress_bar)
        
        self.hide()
        
        # Animations Setup
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(600)
        self.pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        
        self.op_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.op_anim.setDuration(400)
        
        self.anim_group = QParallelAnimationGroup()
        self.anim_group.addAnimation(self.pos_anim)
        self.anim_group.addAnimation(self.op_anim)
        
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.fade_out)
        self.hide_timer.setSingleShot(True)

    def show_alert(self, title, desc, show_progress=False, auto_hide_ms=3000):
        self.title_label.setText(title)
        self.desc_label.setText(desc)
        self.progress_bar.setVisible(show_progress)
        self.progress_bar.setValue(0)
        self.raise_()
        self.show()
        
        if self.parent():
            parent_rect = self.parent().rect()
            start_x = parent_rect.width() - self.width() - 20
            start_y = parent_rect.height() + 10
            end_y = parent_rect.height() - self.height() - 20
        else:
            start_x, start_y, end_y = 0, 0, 0
            
        self.pos_anim.setStartValue(QPoint(start_x, start_y))
        self.pos_anim.setEndValue(QPoint(start_x, end_y))
        
        self.op_anim.setStartValue(0.0)
        self.op_anim.setEndValue(1.0)
        
        try: self.anim_group.finished.disconnect()
        except: pass
        self.anim_group.start()
        
        if auto_hide_ms > 0:
            self.hide_timer.start(auto_hide_ms)
        else:
            self.hide_timer.stop()

    def fade_out(self):
        start_x = self.x()
        start_y = self.y()
        end_y = self.parent().rect().height() + 10 if self.parent() else start_y + 100
        
        self.pos_anim.setStartValue(QPoint(start_x, start_y))
        self.pos_anim.setEndValue(QPoint(start_x, end_y))
        
        self.pos_anim.setEasingCurve(QEasingCurve.Type.InBack)
        
        self.op_anim.setStartValue(1.0)
        self.op_anim.setEndValue(0.0)
        
        try: self.anim_group.finished.disconnect() 
        except: pass
        self.anim_group.finished.connect(self.hide)
        self.anim_group.start()
        
    def update_progress(self, desc, percent):
        self.desc_label.setText(desc)
        self.progress_bar.setValue(int(percent))

class FileCard(QFrame):
    def __init__(self, msg_id, filename, size, icon_color, type_label, on_open, on_download, parent=None):
        super().__init__(parent)
        self.msg_id = msg_id
        self.filename = filename
        self.on_open = on_open
        self.on_download = on_download
        
        self.setFixedSize(160, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            FileCard { background-color: white; border: 1px solid #e5e5e5; border-radius: 8px; }
            FileCard:hover { border: 1px solid #d0d0d0; background-color: #fcfcfc; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(36, 40)
        self.icon_label.setScaledContents(True)
        self.icon_label.setStyleSheet(f"background-color: {icon_color}; border-radius: 8px;")
        layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        name_label = QLabel(filename)
        name_label.setStyleSheet("font-family: 'Segoe UI', Arial; font-weight: 500; font-size: 13px; color: #333; border: none;")
        name_label.setWordWrap(True)
        name_label.setFixedHeight(35)
        size_label = QLabel(size)
        size_label.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 11px; color: #888; border: none;")
        layout.addWidget(name_label)
        layout.addWidget(size_label)

    def update_icon(self, pixmap_path):
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(pixmap_path).scaled(
            self.icon_label.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        self.icon_label.setPixmap(pixmap)
        self.icon_label.setStyleSheet("border-radius: 8px; border: none; background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_open(self.msg_id, self.filename)
            
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        open_action = menu.addAction("Open Live")
        dl_action = menu.addAction("Download")
        open_action.triggered.connect(lambda: self.on_open(self.msg_id, self.filename))
        dl_action.triggered.connect(lambda: self.on_download(self.msg_id, self.filename))
        menu.exec(event.globalPos())

class RecentItem(QFrame):
    def __init__(self, msg_id, filename, date_str, size_str, icon_color, on_open, on_download, parent=None):
        super().__init__(parent)
        self.msg_id = msg_id
        self.filename = filename
        self.on_open = on_open
        self.on_download = on_download

        self.setFixedHeight(65)
        self.setStyleSheet("""
            RecentItem { background-color: white; border: 1px solid #e5e5e5; border-radius: 8px; margin-bottom: 5px; }
            RecentItem:hover { background-color: #fbfbfb; border: 1px solid #d0d0d0; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(36, 36)
        self.icon_label.setScaledContents(True)
        self.icon_label.setStyleSheet(f"background-color: {icon_color}; border-radius: 6px;")
        layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignLeft)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(15, 0, 0, 0)
        text_layout.setSpacing(2)
        name_label = QLabel(filename)
        name_label.setStyleSheet("font-family: 'Segoe UI', Arial; font-weight: 600; font-size: 13px; color: #222; border: none;")
        date_label = QLabel(date_str)
        date_label.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 11px; color: #777; border: none;")
        text_layout.addWidget(name_label)
        text_layout.addWidget(date_label)
        layout.addLayout(text_layout)
        layout.addStretch()
        size_label = QLabel(size_str)
        size_label.setFixedWidth(60)
        size_label.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 12px; color: #555; border: none;")
        layout.addWidget(size_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.menu_btn = QPushButton("•••")
        self.menu_btn.setFixedSize(30, 30)
        self.menu_btn.setStyleSheet("border: none; font-size: 14px; color: #777; background: transparent;")
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.clicked.connect(self.show_menu)
        layout.addWidget(self.menu_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def show_menu(self):
        menu = QMenu(self)
        open_action = menu.addAction("Open Live")
        dl_action = menu.addAction("Download")
        open_action.triggered.connect(lambda: self.on_open(self.msg_id, self.filename))
        dl_action.triggered.connect(lambda: self.on_download(self.msg_id, self.filename))
        menu.exec(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft()))

    def update_icon(self, pixmap_path):
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(pixmap_path).scaled(
            self.icon_label.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        self.icon_label.setPixmap(pixmap)
        self.icon_label.setStyleSheet("border-radius: 6px; border: none; background: transparent;")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cloudgram")
        self.resize(1000, 700)
        self.setStyleSheet("background-color: white; font-family: 'Segoe UI', Arial;")
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("QFrame { background-color: #f4f3f0; border-right: 1px solid #e0e0e0; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 25, 20, 20)
        
        logo_layout = QHBoxLayout()
        logo_icon = QLabel()
        logo_icon.setFixedSize(32, 32)
        logo_icon.setStyleSheet("background-color: #1a73e8; border-radius: 8px;") 
        logo_text = QLabel("Cloudgram")
        logo_text.setStyleSheet("font-family: 'Segoe UI', Arial; font-size: 18px; font-weight: bold; color: #111; border: none;")
        logo_layout.addWidget(logo_icon)
        logo_layout.addSpacing(5)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        sidebar_layout.addLayout(logo_layout)
        sidebar_layout.addSpacing(40)
        
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { height: 42px; border-radius: 8px; padding-left: 10px; color: #444; font-size: 14px; font-weight: 500; }
            QListWidget::item:selected { background-color: white; color: #111; font-weight: bold; border: 1px solid #e0e0e0; }
            QListWidget::item:hover:!selected { background-color: #ebebeb; }
            QListWidget::item:focus { border: none; }
        """)
        for txt, sel in [("   All files", True), ("   Folders", False), ("   Gallery", False), ("   Uploads", False), ("   Google Photos", False), ("   Gmail", False), ("   Trash", False)]:
            it = QListWidgetItem(txt)
            if sel: it.setSelected(True)
            self.nav_list.addItem(it)
        
        self.current_category = "All files"
        self._gp_cache = {}  # mediaItemId -> Google Photos item dict
        self.nav_list.itemSelectionChanged.connect(self.on_category_changed)

        sidebar_layout.addWidget(self.nav_list)
        sidebar_layout.addSpacing(12)

        # Google Account connect / disconnect button
        self.google_btn = QPushButton()
        self.google_btn.setFixedHeight(36)
        self.google_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_google_btn()
        self.google_btn.clicked.connect(self._toggle_google)
        sidebar_layout.addWidget(self.google_btn)
        sidebar_layout.addStretch()
        
        storage_frame = QFrame()
        storage_frame.setStyleSheet("QFrame { background-color: white; border: 1px solid #e5e5e5; border-radius: 10px; }")
        storage_layout = QVBoxLayout(storage_frame)
        storage_layout.setContentsMargins(15, 15, 15, 15)
        s_title = QLabel("Storage used")
        s_title.setStyleSheet("font-size: 12px; color: #444; border: none; font-weight: 500;")
        progress = QProgressBar()
        progress.setFixedHeight(6)
        progress.setTextVisible(False)
        progress.setValue(20)
        progress.setStyleSheet("QProgressBar { background-color: #e6e6e6; border-radius: 3px; border: none; } QProgressBar::chunk { background-color: #1a73e8; border-radius: 3px; }")
        s_desc = QLabel("1.8 GB of unlimited")
        s_desc.setStyleSheet("font-size: 11px; color: #777; border: none;")
        storage_layout.addWidget(s_title)
        storage_layout.addWidget(progress)
        storage_layout.addWidget(s_desc)
        sidebar_layout.addWidget(storage_frame)
        main_layout.addWidget(sidebar)
        
        # Main Area
        main_content = QFrame()
        main_content.setStyleSheet("background-color: white; border: none;")
        content_layout = QVBoxLayout(main_content)
        content_layout.setContentsMargins(40, 30, 40, 20)
        top_bar = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search files...")
        self.search_box.setFixedHeight(40)
        self.search_box.setStyleSheet("QLineEdit { background-color: #f6f6f6; border: 1px solid #eaeaea; border-radius: 8px; padding-left: 15px; font-size: 13px; color: #333; } QLineEdit:focus { border: 1px solid #1a73e8; background-color: white; }")
        self.search_box.textChanged.connect(self.load_files)
        grid_btn = QPushButton(u"\u25A6") 
        list_btn = QPushButton(u"\u2630") 
        for btn in (grid_btn, list_btn):
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("QPushButton { background-color: white; border: 1px solid #e5e5e5; border-radius: 8px; font-size: 20px; color: #555; }")
        self.upload_btn = QPushButton("Upload ▼")
        self.upload_btn.setFixedHeight(40)
        self.upload_btn.setFixedWidth(120)
        self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upload_btn.setStyleSheet("""
            QPushButton { background-color: #1a73e8; color: white; font-weight: bold; border-radius: 8px; border: none; font-size: 14px; }
            QPushButton:hover { background-color: #1557b0; }
        """)
        
        self.upload_menu = QMenu(self)
        self.upload_menu.addAction("Upload File(s)", self.action_upload_file)
        self.upload_menu.addAction("Upload Folder (as Zip)", self.action_upload_folder)
        
        self.upload_btn.setMenu(self.upload_menu)
        
        top_bar.addWidget(self.search_box)
        top_bar.addSpacing(20)
        top_bar.addWidget(grid_btn)
        top_bar.addWidget(list_btn)
        top_bar.addWidget(self.upload_btn)
        content_layout.addLayout(top_bar)
        content_layout.addSpacing(20)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        pinned_lbl = QLabel("PINNED")
        pinned_lbl.setStyleSheet("color: #777; font-size: 12px; font-weight: bold; letter-spacing: 1px; border: none;")
        scroll_layout.addWidget(pinned_lbl)
        self.pinned_grid = QGridLayout()
        self.pinned_grid.setAlignment(Qt.AlignmentFlag.AlignLeft)
        scroll_layout.addLayout(self.pinned_grid)
        scroll_layout.addSpacing(40)
        
        recent_lbl = QLabel("RECENT")
        recent_lbl.setStyleSheet("color: #777; font-size: 12px; font-weight: bold; letter-spacing: 1px; border: none;")
        scroll_layout.addWidget(recent_lbl)
        
        self.recent_list = QVBoxLayout()
        scroll_layout.addLayout(self.recent_list)
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        content_layout.addWidget(scroll_area)
        main_layout.addWidget(main_content)
        
        self.toast = ToastNotification(self)
        
        # self.load_files() # Loaded manually in main.py to prevent startup hang

    def on_category_changed(self):
        items = self.nav_list.selectedItems()
        if items:
            self.current_category = items[0].text().strip()
            if self.current_category == "Google Photos":
                asyncio.create_task(self._load_google_photos())
            elif self.current_category == "Gmail":
                asyncio.create_task(self._load_gmail())
            else:
                self.load_files()

    def load_files(self):
        query = self.search_box.text().lower()
        rows = get_all_files()
        
        filtered_rows = []
        for r in rows:
            db_id, msg_id, name, size, type_, date_str, pinned = r
            if self.current_category == "Folders" and type_ != "folder":
                continue
            if self.current_category == "Gallery" and type_ not in ("image", "video"):
                continue
            if self.current_category == "Uploads" and type_ not in ("document"):
                continue
            if self.current_category == "Trash": # Trash not implemented yet
                continue
            filtered_rows.append(r)
            
        rows = filtered_rows
            
        # Clear existing
        while self.pinned_grid.count():
            item = self.pinned_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        while self.recent_list.count():
            item = self.recent_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        row, col = 0, 0
        for r in rows:
            # r: (id, message_id, file_name, file_size, file_type, uploaded_at, is_pinned)
            db_id, msg_id, name, size, type_, date_str, pinned = r
            if query and query not in name.lower():
                continue
            
            # Formatting size
            if size > 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size / 1024:.0f} KB"
                
            color = "#d6ebff"
            if type_ == 'image': color = "#fdeadd"
            elif type_ == 'video': color = "#fed6e3"
            elif type_ == 'document': color = "#e0f2d8"
            elif type_ == 'folder': color = "#e7dffd"
            
            if pinned:
                card = FileCard(msg_id, name, size_str, color, type_.capitalize(), self.handle_open, self.handle_download)
                self.pinned_grid.addWidget(card, row, col)
                col += 1
                if col > 3:
                    col = 0
                    row += 1
                
                if type_ in ('image', 'video'):
                    import asyncio
                    asyncio.create_task(self.load_thumbnail(msg_id, card))
            else:
                try: # try parsing sqlite date to something nice
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    fmt_date = date_obj.strftime("%b %d, %H:%M")
                except:
                    fmt_date = date_str
                    
                item = RecentItem(msg_id, name, fmt_date, size_str, color, self.handle_open, self.handle_download)
                self.recent_list.addWidget(item)
                
                if type_ in ('image', 'video'):
                    import asyncio
                    asyncio.create_task(self.load_thumbnail(msg_id, item))

    async def load_thumbnail(self, message_id, widget):
        thumb_dir = os.path.join(os.environ.get('TEMP', ''), 'cloudgram_thumbs')
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"thumb_{message_id}.jpg")
        
        if not os.path.exists(thumb_path):
            try:
                await download_file_from_telegram(message_id, thumb_path, is_thumbnail=True)
            except Exception as e:
                pass
                
        if os.path.exists(thumb_path):
            widget.update_icon(thumb_path)

    @qasync.asyncSlot()
    async def action_upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if file_path:
            await self.do_upload(file_path)

    @qasync.asyncSlot()
    async def action_upload_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Upload")
        if folder_path:
            await self.do_upload_folder(folder_path)

    async def do_upload_folder(self, folder_path):
        folder_name = os.path.basename(folder_path) or "Archive"
        self.upload_btn.setEnabled(False)
        self.toast.show_alert("Zipping", f"Compressing {folder_name}...", True, 0)
        
        temp_zip = os.path.join(tempfile.gettempdir(), f"{folder_name}") # without .zip extension because make_archive adds it
        out_zip = shutil.make_archive(temp_zip, 'zip', folder_path)
        
        await self.do_upload(out_zip, override_name=f"{folder_name}.zip", override_type="folder")

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
                speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed > 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
                pct = (current / total) * 100 if total else 0
                self.toast.update_progress(f"{pct:.1f}% ({speed_str}) - {filename}", int(pct))
                last_time = now
                last_bytes = current

        try:
            await upload_file_to_telegram(file_path, progress_callback=progress_cb, override_type=override_type)
            self.toast.show_alert("Success", f"{filename} uploaded!", False, 3000)
            self.load_files()
        except Exception as e:
            self.toast.show_alert("Upload Failed", str(e), False, 4000)
        finally:
            self.upload_btn.setEnabled(True)

    @qasync.asyncSlot()
    async def handle_download(self, message_id, filename):
        dest_path, _ = QFileDialog.getSaveFileName(self, "Save File", filename)
        if dest_path:
            self.toast.show_alert("Downloading", f"Starting {filename}...", True, 0)
            last_time = time.time()
            last_bytes = 0
            
            def progress_cb(current, total):
                nonlocal last_time, last_bytes
                now = time.time()
                elapsed = now - last_time
                if elapsed > 0.5 or current == total:
                    speed = (current - last_bytes) / elapsed if elapsed > 0 else 0
                    speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed > 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
                    pct = (current / total) * 100 if total else 0
                    self.toast.update_progress(f"{pct:.1f}% ({speed_str}) - {filename}", int(pct))
                    last_time = now
                    last_bytes = current

            try:
                success = await download_file_from_telegram(message_id, dest_path, progress_callback=progress_cb)
                if success:
                    self.toast.show_alert("Success", f"File saved: {filename}", False, 3000)
            except Exception as e:
                self.toast.show_alert("Download Failed", str(e), False, 4000)

    @qasync.asyncSlot()
    async def handle_open(self, message_id, filename):
        temp_dir = os.path.join(os.environ.get('TEMP', ''), 'cloudgram_cache')
        os.makedirs(temp_dir, exist_ok=True)
        dest_path = os.path.join(temp_dir, filename)
        
        self.toast.show_alert("Live Preview", f"Fetching {filename}...", True, 0)
        
        last_time = time.time()
        last_bytes = 0
        def progress_cb(current, total):
            nonlocal last_time, last_bytes
            now = time.time()
            elapsed = now - last_time
            if elapsed > 0.5 or current == total:
                speed = (current - last_bytes) / elapsed if elapsed > 0 else 0
                speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed > 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
                pct = (current / total) * 100 if total else 0
                self.toast.update_progress(f"{pct:.1f}% ({speed_str})", int(pct))
                last_time = now
                last_bytes = current

        try:
            success = await download_file_from_telegram(message_id, dest_path, progress_callback=progress_cb)
            if success:
                self.toast.show_alert("Success", f"Opening {filename}!", False, 2000)
                os.startfile(dest_path)
            else:
                self.toast.fade_out()
        except Exception as e:
            self.toast.show_alert("Error", str(e), False, 4000)

    # ═══════════════════════════════════════════════════════════════════════
    # Google Account helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _refresh_google_btn(self):
        if is_google_connected():
            self.google_btn.setText("✓  Google Connected")
            self.google_btn.setStyleSheet("""
                QPushButton { background:#e8f5e9; color:#2e7d32; border:1px solid #4caf50;
                              border-radius:8px; font-size:12px; font-weight:600; }
                QPushButton:hover { background:#c8e6c9; }
            """)
        else:
            self.google_btn.setText("🔗  Connect Google")
            self.google_btn.setStyleSheet("""
                QPushButton { background:#fff3e0; color:#e65100; border:1px solid #ff9800;
                              border-radius:8px; font-size:12px; font-weight:600; }
                QPushButton:hover { background:#ffe0b2; }
            """)

    def _toggle_google(self):
        if is_google_connected():
            disconnect_google()
            self._refresh_google_btn()
            self.toast.show_alert("Disconnected", "Google account unlinked.", False, 3000)
        else:
            asyncio.create_task(self._connect_google_task())

    async def _connect_google_task(self):
        self.google_btn.setEnabled(False)
        self.toast.show_alert("Connecting", "Opening browser for Google sign-in…", False, 0)
        try:
            await connect_google_async()
            self._refresh_google_btn()
            self.toast.show_alert("Success", "Google account connected!", False, 3000)
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Missing credentials.json", str(e))
        except Exception as e:
            self.toast.show_alert("Google Error", str(e), False, 5000)
        finally:
            self.google_btn.setEnabled(True)

    # ═══════════════════════════════════════════════════════════════════════
    # Content area helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _clear_content(self):
        while self.pinned_grid.count():
            item = self.pinned_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        while self.recent_list.count():
            item = self.recent_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_status(self, text: str):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#aaa; font-size:14px; padding:40px; border:none;")
        self.recent_list.addWidget(lbl)

    # ═══════════════════════════════════════════════════════════════════════
    # Google Photos
    # ═══════════════════════════════════════════════════════════════════════

    async def _load_google_photos(self):
        self._clear_content()
        if not GOOGLE_AVAILABLE:
            self._show_status("Google packages not installed.\nRun: pip install -r requirements.txt")
            return
        if not is_google_connected():
            self._show_status("Connect your Google account first.\nClick '🔗 Connect Google' in the sidebar.")
            return

        self._show_status("Fetching photos from Google Photos…")
        try:
            data = await list_media_items(page_size=50)
        except Exception as e:
            self._clear_content()
            self.toast.show_alert("Google Photos Error", str(e), False, 5000)
            return

        self._clear_content()
        media_items = data.get("mediaItems", [])
        if not media_items:
            self._show_status("No media found in Google Photos.")
            return

        self._gp_cache = {}
        row, col = 0, 0
        for it in media_items:
            self._gp_cache[it["id"]] = it
            meta = it.get("mediaMetadata", {})
            is_video = "video" in meta
            w, h = meta.get("width", 0), meta.get("height", 0)
            size_str = f"{w}\u00d7{h}" if w and h else ""
            color = "#fed6e3" if is_video else "#fdeadd"
            card = FileCard(
                it["id"], it.get("filename", "photo"),
                size_str, color,
                "Video" if is_video else "Photo",
                self.handle_gp_open, self.handle_gp_download,
            )
            self.pinned_grid.addWidget(card, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
            asyncio.create_task(self._load_gp_thumb(it.get("baseUrl", ""), it["id"], card))

    async def _load_gp_thumb(self, base_url: str, media_id: str, widget):
        if not base_url:
            return
        thumb_dir = os.path.join(os.environ.get("TEMP", ""), "cloudgram_gp_thumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"gp_{media_id}.jpg")
        if not os.path.exists(thumb_path):
            try:
                await gp_download_thumbnail(base_url, thumb_path, size=200)
            except Exception:
                return
        if os.path.exists(thumb_path):
            widget.update_icon(thumb_path)

    @qasync.asyncSlot()
    async def handle_gp_open(self, media_id: str, filename: str):
        it = self._gp_cache.get(media_id, {})
        base_url = it.get("baseUrl", "")
        is_video = "video" in it.get("mediaMetadata", {})
        if not base_url:
            self.toast.show_alert("Error", "Media URL unavailable.", False, 3000)
            return
        temp_dir = os.path.join(os.environ.get("TEMP", ""), "cloudgram_cache")
        os.makedirs(temp_dir, exist_ok=True)
        dest = os.path.join(temp_dir, filename)
        self.toast.show_alert("Downloading", f"Opening {filename}…", True, 0)
        try:
            await gp_download_media(base_url, dest, is_video=is_video)
            self.toast.show_alert("Done", f"Opening {filename}", False, 2000)
            os.startfile(dest)
        except Exception as e:
            self.toast.show_alert("Error", str(e), False, 4000)

    @qasync.asyncSlot()
    async def handle_gp_download(self, media_id: str, filename: str):
        it = self._gp_cache.get(media_id, {})
        base_url = it.get("baseUrl", "")
        is_video = "video" in it.get("mediaMetadata", {})
        if not base_url:
            self.toast.show_alert("Error", "Media URL unavailable.", False, 3000)
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Save Photo/Video", filename)
        if not dest:
            return
        self.toast.show_alert("Downloading", filename, True, 0)
        try:
            await gp_download_media(base_url, dest, is_video=is_video)
            self.toast.show_alert("Saved", f"File saved: {filename}", False, 3000)
        except Exception as e:
            self.toast.show_alert("Error", str(e), False, 4000)

    # ═══════════════════════════════════════════════════════════════════════
    # Gmail
    # ═══════════════════════════════════════════════════════════════════════

    async def _load_gmail(self):
        self._clear_content()
        if not GOOGLE_AVAILABLE:
            self._show_status("Google packages not installed.\nRun: pip install -r requirements.txt")
            return
        if not is_google_connected():
            self._show_status("Connect your Google account first.\nClick '🔗 Connect Google' in the sidebar.")
            return

        self._show_status("Fetching emails with attachments from Gmail…")
        try:
            messages = await list_messages_with_attachments(max_results=30)
        except Exception as e:
            self._clear_content()
            self.toast.show_alert("Gmail Error", str(e), False, 5000)
            return

        self._clear_content()
        if not messages:
            self._show_status("No emails with attachments found.")
            return

        for msg in messages:
            item = GmailMessageItem(
                msg,
                on_download=self._gmail_download,
                on_open=self._gmail_open,
            )
            self.recent_list.addWidget(item)

    def _gmail_download(self, att: dict):
        asyncio.create_task(self._gmail_download_task(att))

    def _gmail_open(self, att: dict):
        asyncio.create_task(self._gmail_open_task(att))

    async def _gmail_download_task(self, att: dict):
        dest, _ = QFileDialog.getSaveFileName(self, "Save Attachment", att["filename"])
        if not dest:
            return
        self.toast.show_alert("Downloading", att["filename"], True, 0)
        try:
            await gmail_download_attachment(att["message_id"], att["attachment_id"], dest)
            self.toast.show_alert("Saved", f"Saved: {att['filename']}", False, 3000)
        except Exception as e:
            self.toast.show_alert("Error", str(e), False, 4000)

    async def _gmail_open_task(self, att: dict):
        temp_dir = os.path.join(os.environ.get("TEMP", ""), "cloudgram_cache")
        os.makedirs(temp_dir, exist_ok=True)
        dest = os.path.join(temp_dir, att["filename"])
        self.toast.show_alert("Opening", att["filename"], True, 0)
        try:
            await gmail_download_attachment(att["message_id"], att["attachment_id"], dest)
            self.toast.show_alert("Done", f"Opening {att['filename']}", False, 2000)
            os.startfile(dest)
        except Exception as e:
            self.toast.show_alert("Error", str(e), False, 4000)


# ═══════════════════════════════════════════════════════════════════════════
# Gmail message widget
# ═══════════════════════════════════════════════════════════════════════════

class GmailMessageItem(QFrame):
    """Shows one Gmail message with its attachments inside the recent-list."""

    def __init__(self, msg_data: dict, on_download, on_open, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            GmailMessageItem { background:white; border:1px solid #e5e5e5;
                               border-radius:8px; margin-bottom:8px; }
            GmailMessageItem:hover { background:#fbfbfb; border:1px solid #d0d0d0; }
            QLabel { border:none; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(5)

        # ── Header row ──────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        sender = QLabel(msg_data.get("from", "Unknown")[:45])
        sender.setStyleSheet("font-weight:600; font-size:13px; color:#222;")
        date_lbl = QLabel(msg_data.get("date", "")[:16])
        date_lbl.setStyleSheet("font-size:11px; color:#888;")
        hdr.addWidget(sender)
        hdr.addStretch()
        hdr.addWidget(date_lbl)
        layout.addLayout(hdr)

        # ── Subject ─────────────────────────────────────────────────────────
        subj = QLabel(msg_data.get("subject", "(no subject)"))
        subj.setWordWrap(True)
        subj.setStyleSheet("font-size:12px; color:#444;")
        layout.addWidget(subj)

        # ── Attachments ─────────────────────────────────────────────────────
        for att in msg_data.get("attachments", []):
            row = QHBoxLayout()

            icon = QLabel("\U0001f4ce")
            icon.setStyleSheet("font-size:13px;")

            name_lbl = QLabel(att["filename"])
            name_lbl.setStyleSheet("font-size:11px; color:#1a73e8;")

            sz = att.get("size", 0)
            sz_str = f"{sz/1024:.0f} KB" if sz > 0 else ""
            sz_lbl = QLabel(sz_str)
            sz_lbl.setStyleSheet("font-size:11px; color:#888;")

            open_btn = QPushButton("Open")
            open_btn.setFixedSize(54, 24)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.setStyleSheet("""
                QPushButton { background:#f0f7ff; border:1px solid #1a73e8;
                              border-radius:4px; font-size:11px; color:#1a73e8; }
                QPushButton:hover { background:#1a73e8; color:white; }
            """)
            open_btn.clicked.connect(lambda _, a=att: on_open(a))

            save_btn = QPushButton("Save")
            save_btn.setFixedSize(54, 24)
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet("""
                QPushButton { background:#f5f5f5; border:1px solid #ccc;
                              border-radius:4px; font-size:11px; color:#444; }
                QPushButton:hover { background:#e0e0e0; }
            """)
            save_btn.clicked.connect(lambda _, a=att: on_download(a))

            row.addWidget(icon)
            row.addWidget(name_lbl)
            row.addWidget(sz_lbl)
            row.addStretch()
            row.addWidget(open_btn)
            row.addWidget(save_btn)
            layout.addLayout(row)
