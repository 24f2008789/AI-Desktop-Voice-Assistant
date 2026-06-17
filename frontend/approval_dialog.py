from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit
)

from PySide6.QtCore import Qt


class ApprovalDialog(QDialog):

    def __init__(self, data):
        super().__init__()

        self.result_value = None

        self.setWindowTitle("Sierra Approval")
        self.resize(500, 350)

        self.setStyleSheet("""
        QDialog{
            background:#0F172A;
        }
        """)

        layout = QVBoxLayout(self)

        # ==========================
        # TITLE
        # ==========================

        title = QLabel("🤖 Sierra Needs Your Approval")

        title.setAlignment(Qt.AlignCenter)

        title.setStyleSheet("""
            color:#FACC15;
            font-size:22px;
            font-weight:bold;
            padding:10px;
        """)

        layout.addWidget(title)

        # ==========================
        # INFO TEXT
        # ==========================

        info = QLabel(
            "Sierra wants to perform an action."
        )

        info.setAlignment(Qt.AlignCenter)

        info.setStyleSheet("""
            color:white;
            font-size:15px;
        """)

        layout.addWidget(info)

        # ==========================
        # CONTACT
        # ==========================

        contact_label = QLabel(
            f"👤 Recipient : {data['contact']}"
        )

        contact_label.setStyleSheet("""
            color:#38BDF8;
            font-size:15px;
            font-weight:bold;
            padding-top:15px;
        """)

        layout.addWidget(contact_label)

        # ==========================
        # MESSAGE TITLE
        # ==========================

        msg_title = QLabel("💬 Message")

        msg_title.setStyleSheet("""
            color:white;
            font-size:15px;
            font-weight:bold;
            padding-top:10px;
        """)

        layout.addWidget(msg_title)

        # ==========================
        # MESSAGE BOX
        # ==========================

        message_box = QTextEdit()

        message_box.setReadOnly(True)

        message_box.setText(data["message"])

        message_box.setStyleSheet("""
            QTextEdit{
                background:#1E293B;
                color:white;
                border:none;
                border-radius:12px;
                padding:10px;
                font-size:14px;
            }
        """)

        layout.addWidget(message_box)

        # ==========================
        # BUTTONS
        # ==========================

        btn_layout = QHBoxLayout()

        approve_btn = QPushButton("✓ Approve")

        approve_btn.setStyleSheet("""
            QPushButton{
                background:#22C55E;
                color:white;
                font-size:15px;
                font-weight:bold;
                padding:12px;
                border-radius:10px;
            }

            QPushButton:hover{
                background:#16A34A;
            }
        """)

        reject_btn = QPushButton("✗ Cancel")

        reject_btn.setStyleSheet("""
            QPushButton{
                background:#EF4444;
                color:white;
                font-size:15px;
                font-weight:bold;
                padding:12px;
                border-radius:10px;
            }

            QPushButton:hover{
                background:#DC2626;
            }
        """)

        approve_btn.clicked.connect(self.approve)
        reject_btn.clicked.connect(self.reject_action)

        btn_layout.addWidget(approve_btn)
        btn_layout.addWidget(reject_btn)

        layout.addLayout(btn_layout)

    def approve(self):
        self.result_value = "yes"
        self.accept()

    def reject_action(self):
        self.result_value = "no"
        self.reject()