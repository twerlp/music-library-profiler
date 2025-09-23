# resource_manager.py - Utility to manage resource paths for both development and PyInstaller environments.
import sys
import os
from pathlib import Path

def project_path(relative_path):
    """Get absolute path for a project file/folder for both dev and PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Development - go up from utils to src
        base_path = Path(__file__).parent.parent.parent
    
    return base_path / relative_path

# def resource_path(relative_path):
#     """Get absolute path to resource for both dev and PyInstaller"""
#     if hasattr(sys, '_MEIPASS'):
#         # PyInstaller bundle
#         base_path = Path(sys._MEIPASS)
#     else:
#         # Development - go up from utils to src, then to assets
#         base_path = Path(__file__).parent.parent.parent / "assets"
    
#     return base_path / relative_path

