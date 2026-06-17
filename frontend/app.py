import sys

from PySide6.QtWidgets import QApplication

from frontend.window import MainWindow

app = QApplication(sys.argv)

window = MainWindow()
print("window created")
window.show()

app.exec()