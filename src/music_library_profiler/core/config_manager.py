# config_manager.py - Manages loading and saving user configuration settings.
import json
import sys
import os
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file="config.json"):
        # Store config in user's home directory, not in package directory
        if getattr(sys, 'frozen', False):
            # Running as bundled executable
            self.config_dir = Path.home() / ".music_library_profiler"
        else:
            # Running as script
            self.config_dir = Path(__file__).parent.parent / "config"
        
        self.config_file = self.config_dir / config_file
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file or create default if not exists"""
        default_config = {
            "last_directory": "",
            "window_geometry": [100, 100, 600, 400],
            "current_playlist": None
        }
        
        try:
            if not self.config_dir.exists():
                self.config_dir.mkdir(parents=True, exist_ok=True)
            
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return {**default_config, **loaded_config}
            else:
                return default_config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    
    def _save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        return self._save_config()