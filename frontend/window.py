# ui/main_window.py
import os
import uuid
import asyncio

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QUrl

from frontend.siri_wave.wave_widge import SiriWaveWidget
from frontend.assistant_worker import AssistantWorker
from frontend.approval_dialog import ApprovalDialog
from graph import (
    load_thread_messages,
    get_all_thread_ids,
    delete_thread_from_database   # ← import from graph.py
)
from memory_store import load_pdf_to_chroma
from voice import speak


class MainWindow(QMainWindow):

    # ─────────────────────────────────────────────────────────
    # CHAT DISPLAY
    # ─────────────────────────────────────────────────────────

    def start_ai_message(self):
        name_label = QLabel("🤖 Sierra :")
        name_label.setStyleSheet("""
            color:#A78BFA; font-size:12px;
            font-weight:bold; margin-left:10px;
        """)
        bubble = QLabel("")
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(500)
        bubble.setStyleSheet("""
            background:#374151; color:white;
            padding:12px; border-radius:15px;
        """)
        container = QVBoxLayout()
        container.addWidget(name_label)
        container.addWidget(bubble)
        row = QHBoxLayout()
        row.addLayout(container)
        row.addStretch()
        self.chat_layout.addLayout(row)
        self.current_ai_label = bubble

    def update_ai_message(self, chunk):
        if self.current_ai_label:
            self.current_ai_label.setText(
                self.current_ai_label.text() + chunk
            )
            QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
                self.scroll.verticalScrollBar().maximum()
            ))

    def add_message(self, sender, text):
        name_label = QLabel()
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(500)

        if sender == "user":
            name_label.setText("👤 You :")
            name_label.setStyleSheet("""
                color:#60A5FA; font-size:12px;
                font-weight:bold; margin-right:10px;
            """)
            bubble.setStyleSheet("""
                background:#2563EB; color:white;
                padding:12px; border-radius:15px;
            """)
            container = QVBoxLayout()
            container.addWidget(name_label)
            container.addWidget(bubble)
            row = QHBoxLayout()
            row.addStretch()
            row.addLayout(container)
        else:
            name_label.setText("🤖 Sierra :")
            name_label.setStyleSheet("""
                color:#A78BFA; font-size:12px;
                font-weight:bold; margin-left:10px;
            """)
            bubble.setStyleSheet("""
                background:#374151; color:white;
                padding:12px; border-radius:15px;
            """)
            container = QVBoxLayout()
            container.addWidget(name_label)
            container.addWidget(bubble)
            row = QHBoxLayout()
            row.addLayout(container)
            row.addStretch()

        self.chat_layout.addLayout(row)
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    # ─────────────────────────────────────────────────────────
    # ASSISTANT CONTROL
    # ─────────────────────────────────────────────────────────

    def assistant_stopped(self):
        self.start_btn.setText("🎤 START ASSISTANT")

    def toggle_assistant(self):
        if not self.worker.isRunning():
            self.worker.running = True
            self.worker.start()
            self.start_btn.setText("🛑 STOP ASSISTANT")
        else:
            self.worker.stop()
            self.start_btn.setText("🎤 START ASSISTANT")

    def show_approval_card(self, data):
        dialog = ApprovalDialog(data)
        dialog.exec()
        self.worker.approval_result = dialog.result_value

    # ─────────────────────────────────────────────────────────
    # THREAD SIDEBAR
    # ─────────────────────────────────────────────────────────

    def add_thread_to_sidebar(self, thread_id, title=None):
        """Add a thread row to the sidebar."""
        if thread_id in self.threads:
            return  # already added, skip

        if title is None:
            title = f"Chat {len(self.threads) + 1}"

        # Truncate long titles
        display_title = title[:28] + "..." if len(title) > 30 else title

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Thread button
        thread_btn = QPushButton(display_title)
        thread_btn.setStyleSheet("""
            QPushButton {
                background: #111827;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 12px;
                text-align: left;
                font-size: 13px;
            }
            QPushButton:hover { background: #1F2937; }
            QPushButton:pressed { background: #374151; }
        """)
        thread_btn.setCursor(Qt.PointingHandCursor)

        # Delete button — small red trash icon
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(32, 32)
        delete_btn.setToolTip("Delete this chat")
        delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #EF4444;
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #450A0A;
                color: #FCA5A5;
            }
        """)
        delete_btn.setCursor(Qt.PointingHandCursor)

        layout.addWidget(thread_btn, 1)
        layout.addWidget(delete_btn)

        # Insert before the stretch at bottom
        insert_pos = max(0, self.thread_layout.count() - 1)
        self.thread_layout.insertWidget(insert_pos, row)

        self.threads[thread_id] = {
            "title": title,
            "widget": row,
            "button": thread_btn,
            "delete": delete_btn,
        }

        thread_btn.clicked.connect(
            lambda _, tid=thread_id: self.open_thread(tid)
        )
        delete_btn.clicked.connect(
            lambda _, tid=thread_id: self.confirm_delete_thread(tid)
        )

    def load_all_threads(self):
        """Load all existing threads from the database into the sidebar."""
        thread_ids = get_all_thread_ids()  # now returns list of strings
        for thread_id in thread_ids:
            messages = load_thread_messages(thread_id)
            # Use first human message as title
            title = "New Chat"
            for msg in messages:
                if hasattr(msg, 'type') and msg.type == "human" and msg.content.strip():
                    title = msg.content.strip()[:30]
                    break
            self.add_thread_to_sidebar(thread_id, title)

    # ─────────────────────────────────────────────────────────
    # THREAD ACTIONS
    # ─────────────────────────────────────────────────────────

    def new_chat(self):
        """Create a new thread and clear the chat UI."""
        self.current_thread_id = str(uuid.uuid4())
        self.worker.set_thread(self.current_thread_id)
        self.clear_chat()
        self.add_thread_to_sidebar(self.current_thread_id, "New Chat")
        # Highlight new thread
        self._highlight_thread(self.current_thread_id)

    def open_thread(self, thread_id):
        """Load and display messages for a thread."""
        self.current_thread_id = thread_id
        self.worker.set_thread(thread_id)
        self.clear_chat()
        self._highlight_thread(thread_id)

        messages = load_thread_messages(thread_id)
        if not messages:
            return

        for msg in messages:
            if not msg.content or not msg.content.strip():
                continue
            if msg.type == "human":
                self.add_message("user", msg.content)
            elif msg.type == "ai":
                # Skip messages that are just memory dumps
                content = msg.content.strip()
                if content.startswith("MEMORY:"):
                    continue
                if content:
                    self.add_message("assistant", content)

    def confirm_delete_thread(self, thread_id):
        """Show confirmation dialog before deleting."""
        reply = QMessageBox.question(
            self,
            "Delete Chat",
            "Are you sure you want to delete this chat? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.delete_thread(thread_id)

    def delete_thread(self, thread_id):
        """Delete thread from UI and database."""
        if thread_id not in self.threads:
            return

        # Remove widget from sidebar
        widget = self.threads[thread_id]["widget"]
        widget.setParent(None)
        widget.deleteLater()
        del self.threads[thread_id]

        # Delete from database
        delete_thread_from_database(thread_id)

        # If we deleted the active thread, start a new one
        if self.current_thread_id == thread_id:
            self.clear_chat()
            if self.threads:
                # Open the first remaining thread
                first_id = next(iter(self.threads))
                self.open_thread(first_id)
            else:
                # No threads left, create a fresh one
                self.new_chat()

    def _highlight_thread(self, thread_id):
        """Highlight the active thread in the sidebar."""
        for tid, data in self.threads.items():
            if tid == thread_id:
                data["button"].setStyleSheet("""
                    QPushButton {
                        background: #1D4ED8;
                        color: white;
                        border: none;
                        border-radius: 10px;
                        padding: 10px 12px;
                        text-align: left;
                        font-size: 13px;
                    }
                    QPushButton:hover { background: #2563EB; }
                """)
            else:
                data["button"].setStyleSheet("""
                    QPushButton {
                        background: #111827;
                        color: white;
                        border: none;
                        border-radius: 10px;
                        padding: 10px 12px;
                        text-align: left;
                        font-size: 13px;
                    }
                    QPushButton:hover { background: #1F2937; }
                    QPushButton:pressed { background: #374151; }
                """)

    # ─────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def clear_chat(self):
        self.clear_layout(self.chat_layout)
        self.current_ai_label = None
    
    def upload_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF File",
            "",
            "PDF Files (*.pdf)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        if file_path:
            success = load_pdf_to_chroma(file_path)
            if success:
                filename = os.path.basename(file_path)
                asyncio.run(speak(f"{filename} loaded successfully"))
            else:
                asyncio.run(speak("Sorry, I couldn't load that PDF"))
            
    # ─────────────────────────────────────────────────────────
    # INIT / UI BUILD
    # ─────────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self.current_thread_id = str(uuid.uuid4())
        self.threads = {}
        self.current_ai_label = None

        self.worker = AssistantWorker()
        self.worker.set_thread(self.current_thread_id)
        self.worker.stopped.connect(self.assistant_stopped)
        self.worker.message_received.connect(self.add_message)
        self.worker.message_started.connect(self.start_ai_message)
        self.worker.message_chunk.connect(self.update_ai_message)
        self.worker.approval_request.connect(self.show_approval_card)

        self.setWindowTitle("Sierra AI Assistant")
        self.resize(1400, 800)
        self.setStyleSheet("QMainWindow { background-color: #070B1A; }")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ── Siri Wave ──
        self.wave = SiriWaveWidget()
        self.wave.setFixedHeight(150)
        main_layout.addWidget(self.wave)

        # ── Body ──
        body_layout = QHBoxLayout()
        body_layout.setSpacing(8)
        main_layout.addLayout(body_layout)

        # ══ LEFT PANEL ══════════════════════════════════════
        left_panel = QFrame()
        left_panel.setFixedWidth(280)
        left_panel.setStyleSheet("""
            QFrame { background-color: #0B1120; border-radius: 15px; }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        # New Chat button
        self.new_chat_btn = QPushButton("➕  New Chat")
        self.new_chat_btn.setFixedHeight(42)
        self.new_chat_btn.setCursor(Qt.PointingHandCursor)
        self.new_chat_btn.clicked.connect(self.new_chat)
        self.new_chat_btn.setStyleSheet("""
            QPushButton {
                background: #2563EB; color: white;
                border-radius: 12px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #1D4ED8; }
        """)
        left_layout.addWidget(self.new_chat_btn)

        # Thread scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: #0B1120; }
            QWidget { background: #0B1120; }
            QScrollBar:vertical { width: 4px; background: #0B1120; }
            QScrollBar::handle:vertical { background: #374151; border-radius: 2px; }
        """)

        self.thread_container = QWidget()
        self.thread_layout = QVBoxLayout(self.thread_container)
        self.thread_layout.setSpacing(4)
        self.thread_layout.setContentsMargins(0, 0, 0, 0)
        self.thread_layout.addStretch()  # pushes threads to top

        self.scroll_area.setWidget(self.thread_container)
        left_layout.addWidget(self.scroll_area, 1)

        # Start/Stop button

        row = QWidget()
        down_layout = QHBoxLayout(row)
        down_layout.setContentsMargins(4, 2, 4, 2)
        down_layout.setSpacing(4)

        # Thread button
        self.start_btn = QPushButton("🎤 Start Assistant")
        self.start_btn.setFixedHeight(50)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.toggle_assistant)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #00FF88; color: black;
                font-size: 16px; font-weight: bold;
                padding: 12px; border-radius: 15px;
            }
            QPushButton:hover { background: #00DD77; }
        """)

        # file button — small +
        self.upload_btn = QPushButton()
        self.upload_btn.setFixedSize(40, 40)
        self.upload_btn.setText("+")
        self.upload_btn.setStyleSheet("""
        QPushButton{
            border:none;
            font-size:22px;
            color:white;
            background:transparent;
        }

        QPushButton:hover{
            color:#4CAF50;
        }
        """)
        self.upload_btn.clicked.connect(self.upload_pdf)
        self.upload_btn.setCursor(Qt.PointingHandCursor)

        down_layout.addWidget(self.start_btn, 1)
        down_layout.addWidget(self.upload_btn)
        left_layout.addWidget(row)

        # ══ RIGHT PANEL ═════════════════════════════════════
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame { background-color: #0B1120; border-radius: 20px; }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)

        chat_title = QLabel("Conversation")
        chat_title.setStyleSheet("""
            color: white; font-size: 20px;
            font-weight: bold; padding: 4px 0;
        """)
        right_layout.addWidget(chat_title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("""
            QScrollArea { border: none; background: #0B1120; }
            QWidget { background: #0B1120; }
            QScrollBar:vertical { width: 4px; background: #0B1120; }
            QScrollBar::handle:vertical { background: #374151; border-radius: 2px; }
        """)

        chat_container = QWidget()
        self.chat_layout = QVBoxLayout(chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(8)
        self.scroll.setWidget(chat_container)
        right_layout.addWidget(self.scroll)

        # ── Add panels to body ──
        body_layout.addWidget(left_panel)
        body_layout.addWidget(right_panel, 1)

        # ── Load existing threads ──
        self.load_all_threads()

        # If no threads exist yet, create the first one
        if not self.threads:
            self.new_chat()
        else:
            # Open the most recent thread
            first_id = next(iter(self.threads))
            self.open_thread(first_id)