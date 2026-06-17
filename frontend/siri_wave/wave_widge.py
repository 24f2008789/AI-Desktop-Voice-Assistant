import os

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl


class SiriWaveWidget(QWebEngineView):

    def __init__(self):
        super().__init__()

        html_path = os.path.join(
            os.path.dirname(__file__),
            "index.html"
        )

        self.load(
            QUrl.fromLocalFile(
                os.path.abspath(html_path)
            )
        )