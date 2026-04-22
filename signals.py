from PyQt6.QtCore import QObject, pyqtSignal


class TranscriptionSignals(QObject):
    partial_result = pyqtSignal(str)
    final_result = pyqtSignal(str)
