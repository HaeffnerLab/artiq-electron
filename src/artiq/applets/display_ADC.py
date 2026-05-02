#!/usr/bin/env python3

import time
from collections import deque
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

from artiq.applets.simple import SimpleApplet

class MultiChannelPlotWidget(QtWidgets.QWidget):
    def __init__(self, args):
        super().__init__()
        
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.dark_mode = True  # Default to dark mode
        
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # --- Top Bar for Controls ---
        top_layout = QtWidgets.QHBoxLayout()
        self.theme_btn = QtWidgets.QPushButton("Toggle Light/Dark Mode")
        self.theme_btn.clicked.connect(self.toggle_mode)
        top_layout.addWidget(self.theme_btn)
        top_layout.addStretch()  # Pushes button to the left
        main_layout.addLayout(top_layout)
        
        # --- Plots Area ---
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)
        
        container = QtWidgets.QWidget()
        scroll.setWidget(container)
        
        self.plots_layout = QtWidgets.QVBoxLayout(container)
        
        self.plots = {}
        self.curves = {}
        self.data_history = {}

        for i in range(8):
            val_dataset = f"current_channel_{i}_value"
            
            time_axis = pg.DateAxisItem(orientation='bottom')
            
            plot = pg.PlotWidget(axisItems={'bottom': time_axis})
            plot.setTitle(f"ADC Channel {i}") # Default title
            plot.setLabel('left', 'Voltage (V)') 
            plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setMinimumHeight(180)
            plot.setMouseEnabled(x=True, y=True)
            
            # Create the curve (color will be set by apply_theme)
            curve = plot.plot()
            
            self.plots_layout.addWidget(plot)
            plot.hide()
            
            # Store references using the value dataset name as the key
            self.plots[val_dataset] = plot
            self.curves[val_dataset] = curve
            self.data_history[val_dataset] = deque()

        # Apply the initial color scheme
        self.apply_theme()

    def toggle_mode(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.color_scheme = {
                "data": "#aec7e8",     # light blue
                "linear": "#ffbb78",   # light orange
                "exp": "#98df8a",      # light green
                "lor": "#ff9896",      # light red
                "gauss": "#c5b0d5",    # light purple
                "interp": "#aec7e8"    # same as data
            }
            bg_color = "k"
            fg_color = "w"
        else:
            self.color_scheme = {
                "data": "#1f77b4",     # default blue
                "linear": "#ff7f0e",   # default orange
                "exp": "#2ca02c",      # default green
                "lor": "#d62728",      # default red
                "gauss": "#9467bd",    # default purple
                "interp": "#1f77b4"    # same as data
            }
            bg_color = "w"
            fg_color = "k"

        self.setStyleSheet(f"background-color: {'#333' if self.dark_mode else '#EEE'};")

        for val_dataset, plot in self.plots.items():
            plot.setBackground(bg_color)
            
            pen = pg.mkPen(fg_color)
            plot.getAxis('bottom').setTextPen(pen)
            plot.getAxis('bottom').setPen(pen)
            plot.getAxis('left').setTextPen(pen)
            plot.getAxis('left').setPen(pen)
            
            # Update title color to match theme
            plot.setTitle(plot.plotItem.titleLabel.text, color=fg_color)
            
            self.curves[val_dataset].setPen(pg.mkPen(color=self.color_scheme["data"], width=2))

    def data_changed(self, data, mods):
        now = time.time()
        
        for i in range(8):
            val_dataset = f"current_channel_{i}_value"
            name_dataset = f"ADC_channel_{i}_name"
            
            plot_widget = self.plots[val_dataset]
            
            # 1. Handle the Title (Name Dataset)
            try:
                # Extract string name
                channel_name = str(data[name_dataset][1])
                # Ensure theme color is preserved when updating title
                title_color = "w" if self.dark_mode else "k"
                plot_widget.setTitle(channel_name, color=title_color)
            except (KeyError, ValueError, TypeError, IndexError):
                title_color = "w" if self.dark_mode else "k"
                plot_widget.setTitle(f"ADC Channel {i}", color=title_color)

            # 2. Handle the Trace (Value Dataset)
            try:
                val = float(data[val_dataset][1])
                
                history = self.data_history[val_dataset]
                history.append((now, val))
                
                while history and history[0][0] < (now - 60):
                    history.popleft()
                
                x_data = [pt[0] for pt in history]
                y_data = [pt[1] for pt in history]
                
                self.curves[val_dataset].setData(x_data, y_data)
                plot_widget.show()
                
            except (KeyError, ValueError, TypeError, IndexError):
                plot_widget.hide()
                self.data_history[val_dataset].clear()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_F:
            for plot in self.plots.values():
                if plot.isVisible():
                    plot.enableAutoRange(axis=pg.ViewBox.XYAxes)
        else:
            super().keyPressEvent(event)


class MultiChannelApplet(SimpleApplet):
    def __init__(self, main_widget_class):
        super().__init__(main_widget_class)
        
    def args_init(self):
        super().args_init()
        if not hasattr(self, 'datasets'):
            self.datasets = set()
            
        for i in range(8):
            # Subscribe to both the value and the name datasets
            self.datasets.add(f"current_channel_{i}_value")
            self.datasets.add(f"ADC_channel_{i}_name")


def main():
    pg.setConfigOptions(antialias=True)
    applet = MultiChannelApplet(MultiChannelPlotWidget)
    applet.run()

if __name__ == "__main__":
    main()