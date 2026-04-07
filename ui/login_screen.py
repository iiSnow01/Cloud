from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGraphicsDropShadowEffect, QWidget, QFrame
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer, QSequentialAnimationGroup, QParallelAnimationGroup
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient, QBrush, QPen, QPainterPath, QRadialGradient
import qasync
import asyncio
import math


LOGIN_PALETTE = {
    "base": "#05101a",
    "mid": "#081623",
    "end": "#120f26",
    "mint": "#7BF2C3",
    "cyan": "#00C2FF",
    "coral": "#FF8A5B",
    "text": "#ecf7ff",
    "muted": "#97adc2",
    "card": "rgba(7, 16, 28, 0.86)",
    "border": "rgba(123, 242, 195, 0.18)",
    "danger": "#ffb4a2",
    "success": "#98f7d5",
}


class AnimatedBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset = 0.0
        self._orbs = [
            {"x": 0.14, "y": 0.18, "radius": 110, "speed": 1.0, "color": LOGIN_PALETTE["mint"], "alpha": 0.14},
            {"x": 0.82, "y": 0.28, "radius": 150, "speed": 0.8, "color": LOGIN_PALETTE["coral"], "alpha": 0.11},
            {"x": 0.28, "y": 0.82, "radius": 120, "speed": 1.2, "color": LOGIN_PALETTE["cyan"], "alpha": 0.09},
        ]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(30)

    def _animate(self):
        self._offset += 0.01
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width, height = self.width(), self.height()
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0.0, QColor(LOGIN_PALETTE["base"]))
        gradient.setColorAt(0.55, QColor(LOGIN_PALETTE["mid"]))
        gradient.setColorAt(1.0, QColor(LOGIN_PALETTE["end"]))
        painter.fillRect(self.rect(), gradient)

        grid_pen = QPen(QColor(255, 255, 255, 10))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        for x in range(0, width, 28):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, 28):
            painter.drawLine(0, y, width, y)

        for orb in self._orbs:
            cx = orb["x"] * width + math.sin(self._offset * orb["speed"]) * 24
            cy = orb["y"] * height + math.cos(self._offset * orb["speed"] * 0.8) * 18
            radial = QRadialGradient(cx, cy, orb["radius"])
            inner = QColor(orb["color"])
            inner.setAlphaF(orb["alpha"])
            outer = QColor(orb["color"])
            outer.setAlpha(0)
            radial.setColorAt(0.0, inner)
            radial.setColorAt(1.0, outer)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(radial))
            painter.drawEllipse(QPoint(int(cx), int(cy)), orb["radius"], orb["radius"])


class PrimaryButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)
        self.setFont(QFont("Segoe UI Semibold", 11))
        self.setStyleSheet(
            f"""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {LOGIN_PALETTE['mint']}, stop:1 {LOGIN_PALETTE['cyan']});
                color: white;
                border: none;
                border-radius: 15px;
                padding: 0 18px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #96f7d4, stop:1 #33d4ff);
            }
            QPushButton:pressed {
                background: #00a6d8;
            }
            QPushButton:disabled {
                background: #425160;
                color: #cbd5e1;
            }
            """
        )


class ModernLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setFont(QFont("Segoe UI", 12))
        self.setStyleSheet(
            f"""
            QLineEdit {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(148, 163, 184, 0.35);
                border-radius: 15px;
                padding: 0 16px;
                color: {LOGIN_PALETTE['text']};
                selection-background-color: {LOGIN_PALETTE['cyan']};
            }
            QLineEdit:focus {
                background: rgba(255, 255, 255, 0.09);
                border: 1px solid {LOGIN_PALETTE['mint']};
            }
            QLineEdit::placeholder {
                color: rgba(226, 232, 240, 0.45);
            }
            """
        )


class StepIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_step = 1
        self.setFixedHeight(34)

    def set_step(self, step):
        self._current_step = step
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        center_y = self.height() // 2
        positions = [width // 2 - 42, width // 2 + 42]
        radius = 9

        line_pen = QPen(QColor(148, 163, 184, 70), 3)
        painter.setPen(line_pen)
        painter.drawLine(positions[0] + radius + 5, center_y, positions[1] - radius - 5, center_y)

        if self._current_step >= 2:
            active_pen = QPen(QColor(LOGIN_PALETTE["mint"]), 3)
            painter.setPen(active_pen)
            painter.drawLine(positions[0] + radius + 5, center_y, positions[1] - radius - 5, center_y)

        for index, x in enumerate(positions, start=1):
            active = index <= self._current_step
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(LOGIN_PALETTE["mint"]) if active else QColor(148, 163, 184, 90))
            painter.drawEllipse(QPoint(x, center_y), radius, radius)
            painter.setPen(QColor(LOGIN_PALETTE["base"]) if active else QColor("#e2e8f0"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(x - 4, center_y + 4, str(index))


class TelegramIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(68, 68)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height())
        gradient = QLinearGradient(0, 0, size, size)
        gradient.setColorAt(0.0, QColor(LOGIN_PALETTE["mint"]))
        gradient.setColorAt(1.0, QColor(LOGIN_PALETTE["coral"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(0, 0, size, size)

        painter.setBrush(QColor(LOGIN_PALETTE["text"]))
        cx = size / 2
        cy = size / 2
        scale = size / 68.0

        path = QPainterPath()
        path.moveTo(cx - 18 * scale, cy + 3 * scale)
        path.lineTo(cx + 19 * scale, cy - 11 * scale)
        path.lineTo(cx - 4 * scale, cy + 18 * scale)
        path.lineTo(cx - 1 * scale, cy + 6 * scale)
        path.closeSubpath()
        painter.drawPath(path)

        fold = QPainterPath()
        fold.moveTo(cx - 1 * scale, cy + 6 * scale)
        fold.lineTo(cx + 19 * scale, cy - 11 * scale)
        fold.lineTo(cx + 5 * scale, cy + 7 * scale)
        fold.closeSubpath()
        painter.setBrush(QColor(255, 255, 255, 190))
        painter.drawPath(fold)


class LoginScreen(QDialog):
    def __init__(self, client, parent=None, initial_phone=None):
        super().__init__(parent)
        self.client = client
        self.phone_code_hash = None
        self.phone_number = None
        self._initial_phone = initial_phone
        self.login_event = asyncio.Event()

        self.setWindowTitle("Cloudgram Login")
        self.setFixedSize(460, 560)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos = None
        self._setup_ui()
        if self._initial_phone:
            self.input_field.setText(self._initial_phone)
            self.input_field.selectAll()
        self._animate_entrance()
        QTimer.singleShot(150, self.input_field.setFocus)

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.bg = AnimatedBackground(self)
        self.bg.setFixedSize(460, 560)

        self.card = QFrame(self.bg)
        self.card.setGeometry(18, 18, 424, 524)
        self.card.setStyleSheet(
            f"""
            QFrame {
                background: {LOGIN_PALETTE['card']};
                border-radius: 28px;
                border: 1px solid {LOGIN_PALETTE['border']};
            }
            """
        )

        card_shadow = QGraphicsDropShadowEffect(self.card)
        card_shadow.setBlurRadius(46)
        card_shadow.setColor(QColor(0, 0, 0, 130))
        card_shadow.setOffset(0, 14)
        self.card.setGraphicsEffect(card_shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 24, 28, 28)
        card_layout.setSpacing(0)

        top_row = QHBoxLayout()
        self.badge_label = QLabel("Telegram secure login")
        self.badge_label.setStyleSheet(
            f"background: rgba(123, 242, 195, 0.16); color: {LOGIN_PALETTE['mint']}; border-radius: 12px; padding: 7px 12px; font-size: 11px; font-weight: 700;"
        )
        top_row.addWidget(self.badge_label)
        top_row.addStretch()

        self.close_btn = QPushButton("x")
        self.close_btn.setFixedSize(34, 34)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #cbd5e1;
                border: none;
                border-radius: 17px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: rgba(248, 113, 113, 0.16);
                color: #fecaca;
            }
            """
        )
        self.close_btn.clicked.connect(self.close)
        top_row.addWidget(self.close_btn)
        card_layout.addLayout(top_row)
        card_layout.addSpacing(28)

        hero_row = QHBoxLayout()
        hero_row.setSpacing(14)
        self.icon = TelegramIcon()
        hero_row.addWidget(self.icon, alignment=Qt.AlignmentFlag.AlignTop)

        hero_copy = QVBoxLayout()
        self.title_label = QLabel("Welcome back")
        self.title_label.setFont(QFont("Segoe UI Semibold", 24))
        self.title_label.setStyleSheet(f"color: {LOGIN_PALETTE['text']}; border: none;")
        self.subtitle_label = QLabel("Sign in with the phone number linked to your Telegram account.")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setFont(QFont("Segoe UI", 10))
        self.subtitle_label.setStyleSheet(f"color: {LOGIN_PALETTE['muted']}; border: none; line-height: 1.4;")
        hero_copy.addWidget(self.title_label)
        hero_copy.addWidget(self.subtitle_label)
        hero_row.addLayout(hero_copy)
        card_layout.addLayout(hero_row)
        card_layout.addSpacing(28)

        self.helper_card = QFrame()
        self.helper_card.setStyleSheet(
            f"QFrame {{ background: rgba(13, 21, 33, 0.82); border: 1px solid {LOGIN_PALETTE['border']}; border-radius: 18px; }}"
        )
        helper_layout = QHBoxLayout(self.helper_card)
        helper_layout.setContentsMargins(14, 12, 14, 12)
        helper_layout.setSpacing(10)

        helper_dot = QLabel("1")
        helper_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        helper_dot.setFixedSize(28, 28)
        helper_dot.setStyleSheet(
            f"background: {LOGIN_PALETTE['coral']}; color: #2c140e; border-radius: 14px; font-size: 11px; font-weight: 800;"
        )
        self.helper_title = QLabel("Enter your number")
        self.helper_title.setStyleSheet(f"color: {LOGIN_PALETTE['text']}; font-size: 12px; font-weight: 700; border: none;")
        self.helper_text = QLabel("We will send a one-time verification code to complete sign-in.")
        self.helper_text.setWordWrap(True)
        self.helper_text.setStyleSheet(f"color: {LOGIN_PALETTE['muted']}; font-size: 10px; border: none;")
        helper_copy = QVBoxLayout()
        helper_copy.setSpacing(2)
        helper_copy.addWidget(self.helper_title)
        helper_copy.addWidget(self.helper_text)
        helper_layout.addWidget(helper_dot, alignment=Qt.AlignmentFlag.AlignTop)
        helper_layout.addLayout(helper_copy)
        card_layout.addWidget(self.helper_card)
        card_layout.addSpacing(22)

        step_row = QHBoxLayout()
        step_row.addStretch()
        self.step_indicator = StepIndicator()
        self.step_indicator.setFixedWidth(150)
        step_row.addWidget(self.step_indicator)
        step_row.addStretch()
        card_layout.addLayout(step_row)
        card_layout.addSpacing(22)

        self.input_label = QLabel("PHONE NUMBER")
        self.input_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.input_label.setStyleSheet(f"color: {LOGIN_PALETTE['mint']}; border: none; letter-spacing: 1.8px;")
        card_layout.addWidget(self.input_label)
        card_layout.addSpacing(8)

        self.input_field = ModernLineEdit()
        self.input_field.setPlaceholderText("+1 418 575 9959")
        card_layout.addWidget(self.input_field)
        card_layout.addSpacing(10)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setFont(QFont("Segoe UI", 9))
        self.info_label.setStyleSheet(f"color: {LOGIN_PALETTE['danger']}; border: none; min-height: 22px;")
        card_layout.addWidget(self.info_label)
        card_layout.addSpacing(12)

        self.action_btn = PrimaryButton("Send code")
        self.action_btn.clicked.connect(self.handle_action)
        self.input_field.returnPressed.connect(self.action_btn.click)
        card_layout.addWidget(self.action_btn)
        card_layout.addSpacing(18)

        footer = QLabel("Your session stays on this device.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: rgba(151, 173, 194, 0.82); border: none; font-size: 10px;")
        card_layout.addWidget(footer)
        card_layout.addStretch()

        root_layout.addWidget(self.bg)

    def _animate_entrance(self):
        self.setWindowOpacity(0.0)

        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(380)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._card_anim = QPropertyAnimation(self.card, b"pos")
        self._card_anim.setDuration(520)
        self._card_anim.setStartValue(QPoint(18, 40))
        self._card_anim.setEndValue(QPoint(18, 18))
        self._card_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        group = QParallelAnimationGroup(self)
        group.addAnimation(self._opacity_anim)
        group.addAnimation(self._card_anim)
        group.start()

    def _transition_to_code_input(self):
        self._fade_out = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out.setDuration(160)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.82)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InQuad)

        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(220)
        self._fade_in.setStartValue(0.82)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutQuad)

        def update_content():
            self.badge_label.setText("Verification step")
            self.title_label.setText("Verify code")
            self.subtitle_label.setText(f"We sent a login code to {self.phone_number}. Enter it below to continue.")
            self.helper_title.setText("Enter your code")
            self.helper_text.setText("This code expires quickly. Double-check spacing and country code if delivery is delayed.")
            self.input_label.setText("VERIFICATION CODE")
            self.input_field.clear()
            self.input_field.setPlaceholderText("12345")
            self.action_btn.setText("Verify login")
            self.action_btn.setEnabled(True)
            self.step_indicator.set_step(2)
            self.info_label.setText("")
            self.input_field.setFocus()

        self._fade_out.finished.connect(update_content)

        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(self._fade_out)
        sequence.addAnimation(self._fade_in)
        sequence.start()

    def _show_error(self, message):
        self.info_label.setStyleSheet(f"color: {LOGIN_PALETTE['danger']}; border: none; min-height: 22px;")
        self.info_label.setText(f"Error: {message}")

    def _show_success(self, message):
        self.info_label.setStyleSheet(f"color: {LOGIN_PALETTE['success']}; border: none; min-height: 22px;")
        self.info_label.setText(f"Success: {message}")

    @qasync.asyncSlot()
    async def handle_action(self):
        if not self.phone_code_hash:
            self.phone_number = self.input_field.text().strip()
            if not self.phone_number:
                self._show_error("Please enter a valid phone number.")
                return

            try:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Sending...")
                self.info_label.setText("")

                response = await self.client.send_code_request(self.phone_number)
                self.phone_code_hash = response.phone_code_hash

                self._show_success("Code sent successfully.")
                QTimer.singleShot(520, self._transition_to_code_input)
            except Exception as error:
                self._show_error(str(error))
                self.action_btn.setText("Send code")
                self.action_btn.setEnabled(True)
        else:
            code = self.input_field.text().strip()
            if not code:
                self._show_error("Please enter the verification code.")
                return

            try:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Verifying...")
                self.info_label.setText("")

                await self.client.sign_in(
                    self.phone_number,
                    code,
                    phone_code_hash=self.phone_code_hash,
                )

                self._show_success("Login successful.")
                self.login_event.set()
                QTimer.singleShot(720, self.accept)
            except Exception as error:
                self._show_error(str(error))
                self.action_btn.setText("Verify login")
                self.action_btn.setEnabled(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def closeEvent(self, event):
        self.login_event.set()
        if hasattr(self, "bg") and self.bg.timer.isActive():
            self.bg.timer.stop()
        super().closeEvent(event)

    async def wait_for_login(self):
        await self.login_event.wait()
