# directory_selector.py - A widget for selecting directories using the filesystem dialog.
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog
from PyQt6.QtGui import QFont
from PyQt6.QtCore import pyqtSignal

class DirectorySelector(QWidget):
    directorySelected = pyqtSignal(str)
    
    def __init__(self, parent=None, placeholder="Enter folder path..."):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        
        self.folder_field = QLineEdit()
        self.folder_field.setPlaceholderText(placeholder)
        self.folder_field.setFont(QFont("DejaVu Sans", 12))
        self.folder_field.textChanged.connect(self._on_text_changed)
        
        self.browse_button = QPushButton("Browse")
        self.browse_button.setFont(QFont("DejaVu Sans", 12))
        self.browse_button.clicked.connect(self._browse_directory)
        
        self.layout.addWidget(self.folder_field)
        self.layout.addWidget(self.browse_button)
    
    def _browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Folder")
        if directory:
            self.folder_field.setText(directory)
    
    def _on_text_changed(self, text):
        self.directorySelected.emit(text)
    
    def set_directory(self, directory):
        self.folder_field.setText(directory)
    
    def get_directory(self):
        return self.folder_field.text().strip()