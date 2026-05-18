#!/usr/bin/env python3

import os
import h5py  # Used to read the stored default values from the local file
from PyQt5 import QtWidgets, QtCore
from artiq.applets.simple import SimpleApplet

class DatasetDisplayWidget(QtWidgets.QWidget):
    def __init__(self, args):
        super().__init__()
        
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        
        # Dataset identifier (serves as both the local file name and ARTIQ dataset name)
        self.file_path = "optimize.e"
        self.attributes_list = ['bl1', 'bl2', 'bl3', 'bl4', 'bl5',
                                'br1', 'br2', 'br3', 'br4', 'br5', 
                                'tl1', 'tl2', 'tl3', 'tl4', 'tl5',
                                'tr1', 'tr2', 'tr3', 'tr4', 'tr5'] 
        
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # --- Value Display Area ---
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)
        
        container = QtWidgets.QWidget()
        scroll.setWidget(container)
        
        self.content_layout = QtWidgets.QFormLayout(container)
        self.content_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        
        self.value_labels = {}

        # Apply default styling
        self.setStyleSheet("background-color: #333333; color: #FFFFFF;")

        # Initialize the layout rows for each attribute
        for attr in self.attributes_list:
            name_label = QtWidgets.QLabel(f"{attr}:")
            name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
            
            val_label = QtWidgets.QLabel("Loading defaults...")
            val_label.setStyleSheet("color: #aec7e8; font-size: 14px; font-family: monospace;")
            
            self.content_layout.addRow(name_label, val_label)
            self.value_labels[attr] = val_label

        # Load and display stored default values immediately on startup
        self.load_default_values()

    def load_default_values(self):
        """Reads the local HDF5 file to show stored values before live data arrives."""
        if not os.path.exists(self.file_path):
            for label in self.value_labels.values():
                label.setText("No stored data found")
            return

        try:
            with h5py.File(self.file_path, 'r') as f:
                for attr in self.attributes_list:
                    if attr in f:
                        val = f[attr][()]
                        self.value_labels[attr].setText(str(val))
                    elif 'datasets' in f and attr in f['datasets']:
                        val = f['datasets'][attr][()]
                        self.value_labels[attr].setText(str(val))
                    else:
                        self.value_labels[attr].setText("Not Stored")
        except Exception as e:
            for label in self.value_labels.values():
                label.setText(f"Error loading defaults: {str(e)}")

    def data_changed(self, data, mods):
        """Receives live updates from ARTIQ and updates the UI."""
        if self.file_path not in data:
            return

        try:
            # ARTIQ applet data arrives as a tuple: (mutation_id, value)
            payload = data[self.file_path][1]
            
            for attr in self.attributes_list:
                # Extract values dynamically based on how payload data is structured
                if isinstance(payload, dict) and attr in payload:
                    val = payload[attr]
                elif hasattr(payload, attr):
                    val = getattr(payload, attr)
                else:
                    continue
                
                self.value_labels[attr].setText(str(val))
                
        except (IndexError, TypeError, KeyError):
            pass


class DatasetViewerApplet(SimpleApplet):
    def __init__(self, main_widget_class):
        super().__init__(main_widget_class)
        
    def args_init(self):
        super().args_init()
        if not hasattr(self, 'datasets'):
            self.datasets = set()
        self.datasets.add("optimize.e")


def main():
    applet = DatasetViewerApplet(DatasetDisplayWidget)
    applet.run()

if __name__ == "__main__":
    main()