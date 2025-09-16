#!/bin/bash
echo "Building Music Library Profiler..."

# Create build directory
mkdir -p dist

# Run PyInstaller
pyinstaller --onefile \
            --windowed \
            --name MusicLibraryProfiler \
            --icon assets/icon.ico \
            --add-data "assets:assets" \
            --add-data "widgets:widgets" \
            --add-data "utils:utils" \
            main.py

echo "Build complete! Check the dist/ directory."