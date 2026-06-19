import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFileDialog, QVBoxLayout

class Window(QWidget):
    def __init__(self):
        super().__init__()

        button = QPushButton("Browse")

        button.clicked.connect(self.open_file)

        layout = QVBoxLayout()
        layout.addWidget(button)

        self.setLayout(layout)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "All Files (*);;PDF Files (*.pdf)"
        )

        print(file_path)

app = QApplication(sys.argv)

window = Window()
window.show()

sys.exit(app.exec())