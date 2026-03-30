from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
import qasync
import asyncio

class LoginScreen(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.phone_code_hash = None
        self.phone_number = None
        self.login_event = asyncio.Event()
        
        self.setWindowTitle("Login to Telegram")
        self.setFixedSize(300, 250)
        self.setStyleSheet("background-color: white; font-family: 'Segoe UI', Arial;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.label = QLabel("Enter Phone Number:")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("+14185759959")
        self.input_field.setStyleSheet("padding: 5px; font-size: 14px; border: 1px solid #ccc; border-radius: 4px;")
        
        self.action_btn = QPushButton("Send Code")
        self.action_btn.setStyleSheet("background-color: #1a73e8; color: white; border-radius: 5px; padding: 8px; font-weight: bold;")
        self.action_btn.clicked.connect(self.handle_action)
        
        layout.addWidget(self.label)
        layout.addWidget(self.input_field)
        layout.addSpacing(15)
        layout.addWidget(self.action_btn)
        layout.addStretch()
        
    @qasync.asyncSlot()
    async def handle_action(self):
        if not self.phone_code_hash:
            # We are sending the phone number
            self.phone_number = self.input_field.text().strip()
            if not self.phone_number:
                QMessageBox.warning(self, "Error", "Please enter a valid phone number.")
                return
            
            try:
                self.action_btn.setEnabled(False)
                res = await self.client.send_code_request(self.phone_number)
                self.phone_code_hash = res.phone_code_hash
                
                # Update UI for code input
                self.label.setText("Enter Telegram Verification Code:")
                self.input_field.clear()
                self.input_field.setPlaceholderText("00000")
                self.action_btn.setText("Login")
                self.action_btn.setEnabled(True)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                self.action_btn.setEnabled(True)
        else:
            # We are sending the code
            code = self.input_field.text().strip()
            if not code:
                return
            
            try:
                self.action_btn.setEnabled(False)
                await self.client.sign_in(self.phone_number, code, phone_code_hash=self.phone_code_hash)
                self.login_event.set()
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                self.action_btn.setEnabled(True)

    def closeEvent(self, event):
        self.login_event.set() # prevent main loop hanging if closed
        super().closeEvent(event)
        
    async def wait_for_login(self):
        await self.login_event.wait()

