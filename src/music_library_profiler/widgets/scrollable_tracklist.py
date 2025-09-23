import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout)
from PyQt6.QtCore import Qt, QSize
import logging

'''
My ideal solution for this is to have a dynamically loaded scroller, meaning
    data will be loaded only when the user can see an element. I hypothesize 
    that will work better for massive databases, but this is outside of my
    scope/ability right now, I just don't know PyQt6 well enough to do it.
'''

#TODO: Fix issues with arabic (farsi?) characters right adjusting everything (use HBox)

class ItemWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.layout = QHBoxLayout(self)
        self.label = QLabel("Item", self)
        self.layout.addWidget(self.label)
    
    def set_data(self, text):
        self.label.setText(text)

class DynamicScrollWidget(QWidget):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.data_provider = DataProvider(database)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(1)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Create refresh button
        self.refresh_button = QLabel("🔄 Refresh")
        self.refresh_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.refresh_button.mousePressEvent = self.on_refresh_clicked
        layout.addWidget(self.refresh_button)
        
        # Create visible item widgets
        self.item_widgets = []
        # for i in range(self.total_visible_items + 2 * self.buffer_items):
        for i in range(self.data_provider.get_length()):
            item = ItemWidget()
            self.item_widgets.append(item)
            layout.addWidget(item)

        self.update_items()
    
    def update_items(self):
        data = self.data_provider.get_all()
        for i, widget in enumerate(self.item_widgets):
            widget.set_data(f"{i + 1}. {data[i]['title']}")


    # def update_items(self):
    #     """Update visible items based on current scroll position"""
    #     total_items = self.data_provider.get_length()

    #     data_start = max(0, min(self.current_start - self.buffer_items, total_items - self.total_visible_items))
    #     data_end = min(data_start + self.total_visible_items + self.buffer_items, total_items)

    #     data_range = self.data_provider.get_range(data_start, data_end - data_start)
    #     print(f"Data start: {data_start}, Data end: {data_end}")
    #     print(data_range)

    #     for i, widget in enumerate(self.item_widgets):
    #         data_index = data_start + i
    #         print(f"Updating widget {i} for data index {data_index}")
    #         print(f"Data at index: {data_range[data_index - data_start] if data_index - data_start < len(data_range) else 'N/A'}")
    #         if data_index < len(data_range):
    #             data = data_range[data_index - data_start]
    #             widget.setVisible(True)
    #             widget.set_data(f"{data_index + 1}. {data['title']}")
    #         else:
    #             widget.setVisible(False)
    
    # def scroll_to(self, position_percent):
    #     """Scroll to a specific percentage of the total content"""
    #     total_items = self.data_provider.get_length()
    #     new_start = int((total_items - self.total_visible_items) * position_percent / 100)
    #     self.current_start = max(0, min(new_start, total_items - self.total_visible_items))
    #     print(f"Scrolling to start index: {self.current_start}, with total items: {total_items}")
    
    #     self.update_items()
    
    def on_refresh_clicked(self, event):
        """Handle refresh button click"""
        logging.info("Refresh button clicked")
        self.data_provider.refresh_total_count()
        self.current_start = 0
        self.update_items()

class DataProvider:
    """Data provider gathers data for the scrollable list from the sqlite database."""
    def __init__(self, database):
        self.database = database
        self.refresh_total_count()
    
    def refresh_total_count(self):
        logging.info("Refreshing total track count from database")
        self.length = self.database.count_number_of_tracks()
    
    def get_length(self):
        return self.length
    
    def get_item(self, index):
        if 0 <= index < self.length:
            return self.database.get_track_by_id(index)
        return None

    def get_range(self, start, count):
        if start < 0 or count <= 0 or start >= self.length:
            return []
        if start + count > self.length:
            count = self.length - start
        return self.database.get_range_of_tracks(start, count)
    
    def get_all(self):
        return self.database.fetch_all_tracks()
        
        

    