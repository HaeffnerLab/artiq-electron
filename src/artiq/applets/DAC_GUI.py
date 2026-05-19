#!/usr/bin/env python3

from PyQt5 import QtWidgets, QtCore
from artiq.applets.simple import SimpleApplet

class DatasetDisplayWidget(QtWidgets.QWidget):
    def __init__(self, args):
        super().__init__()
        
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        
        # Base dataset path/name from the ARTIQ Datasets tab
        self.dataset_prefix = "optimize.e"
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
        
        """
        TODO:
        * Make the layout nicer such that the displayed voltages are in grid-like format with names and
        values side by side, grouped by BL/BR/TL/TR. 
        * Add the Ex, Ey, Ez... placeholders on the side, they don't need values for now but should be there for future use.
        * Add a load_DAC button, currently don't need any functionality, but in the future it will submit an experimental
        sequence to load the values into the DAC hardware.
        """
        self.content_layout = QtWidgets.QFormLayout(container)
        self.content_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        
        self.value_labels = {}

        # Default dark layout styling
        self.setStyleSheet("background-color: #333333; color: #FFFFFF;")

        # Set up rows for all attributes
        for attr in self.attributes_list:
            name_label = QtWidgets.QLabel(f"{attr}:")
            name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
            
            val_label = QtWidgets.QLabel("Fetching from Master DB...")
            val_label.setStyleSheet("color: #aec7e8; font-size: 14px; font-family: monospace;")
            
            self.content_layout.addRow(name_label, val_label)
            self.value_labels[attr] = val_label

    def data_changed(self, data, mods):
        """
        Triggered automatically by the ARTIQ master immediately upon startup 
        with currently stored values, and again whenever a live change happens.
        """
        for attr in self.attributes_list:
            full_dataset_key = f"{self.dataset_prefix}.{attr}"
            if full_dataset_key in data:
                val = data[full_dataset_key][1]  # Extract currently stored value
                self.value_labels[attr].setText(str(val))


class DatasetViewerApplet(SimpleApplet):
    def __init__(self, main_widget_class):
        super().__init__(main_widget_class)
        
    def args_init(self):
        super().args_init()
        if not hasattr(self, 'datasets'):
            self.datasets = set()
            
        prefix = "optimize.e"
        attributes = ['bl1', 'bl2', 'bl3', 'bl4', 'bl5',
                      'br1', 'br2', 'br3', 'br4', 'br5', 
                      'tl1', 'tl2', 'tl3', 'tl4', 'tl5',
                      'tr1', 'tr2', 'tr3', 'tr4', 'tr5']
        
        # Subscribe to both the parent group name AND all possible sub-paths
        # to ensure the Master feeds us the startup snapshot regardless of DB structure.
        self.datasets.add(prefix)
        for attr in attributes:
            self.datasets.add(f"{prefix}.{attr}")


def main():
    applet = DatasetViewerApplet(DatasetDisplayWidget)
    applet.run()

if __name__ == "__main__":
    main()