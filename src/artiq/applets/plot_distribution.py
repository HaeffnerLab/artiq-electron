#!/usr/bin/env python3
import sys
import os
import re
import numpy as np
import h5py
import PyQt5  # ensures pyqtgraph loads Qt5
import pyqtgraph
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QCheckBox, QPushButton,
    QFileDialog, QApplication, QComboBox, QLabel, QDialog, QGridLayout, QMessageBox,
    QGroupBox, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt
from artiq.applets.simple import TitleApplet

# ------------------------- PowerHistogramPlot -------------------------
class PowerHistogramPlot(pyqtgraph.PlotWidget):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.dark_mode = False  # default light mode
        self.update_color_scheme()
        self.showGrid(x=True, y=True)
        
        xlabel = getattr(args, 'xlabel', 'Power Value')
        ylabel = getattr(args, 'ylabel', 'Density')
        self.setLabel('bottom', xlabel)
        self.setLabel('left', ylabel)
        
        # Internal tracking variables for limits mapping
        self.global_x_min = 0.0
        self.global_x_max = 10.0
        self.hist_item = None

    def update_color_scheme(self):
        if self.dark_mode:
            self.setBackground("k")
            self.getAxis('bottom').setTextPen(pyqtgraph.mkPen("w"))
            self.getAxis('left').setTextPen(pyqtgraph.mkPen("w"))
        else:
            self.setBackground("w")
            self.getAxis('bottom').setTextPen(pyqtgraph.mkPen("k"))
            self.getAxis('left').setTextPen(pyqtgraph.mkPen("k"))

    def set_global_limits(self, x_min, x_max):
        if x_min < x_max:
            padding = (x_max - x_min) * 0.05
            self.global_x_min = x_min - padding
            self.global_x_max = x_max + padding

    def plot_histogram(self, data, title, log_y=True, fix_xlim=False):
        self.clear()
        if len(data) == 0:
            return
        # data = 10**(data/10)*1e6
        # print(data)
        # Calculate density histogram properties
        y_density, x_edges = np.histogram(data, bins=max(50, int(max(data)-min(data))*100), density=True)
        
        # Handle zero-values safely and determine the correct log-space fill baseline
        if log_y:
            y_density = np.where(y_density <= 0, 1e-6, y_density)
            self.setLogMode(x=False, y=True)
            # FIX: Explicitly pass -6.0 (log10 of 1e-6) because pyqtgraph 
            # does not automatically log-transform the fillLevel argument!
            fill_level = -6.0  
        else:
            self.setLogMode(x=False, y=False)
            fill_level = 0.0

        # Plot setup utilizing standard Pyqtgraph steps mapping rule (len(x) == len(y) + 1)
        fill_color = (220, 20, 60, 150) if self.dark_mode else (31, 119, 180, 180)
        self.hist_item = self.plot(
            x_edges, 
            y_density, 
            stepMode=True, 
            fillLevel=fill_level, 
            fillOutline=True, 
            brush=fill_color, 
            pen='k'
        )
        
        self.setTitle(title)
        
        if fix_xlim:
            self.setXRange(self.global_x_min, self.global_x_max, padding=0)
        else:
            self.setXRange(np.min(x_edges), np.max(x_edges), padding=0.1)


# ------------------------ MainWidget ------------------------
class MainWidget(QWidget):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.current_file_path = None
        self.experiment_map = {}
        self.dataset_pattern = re.compile(r'data\.(\d+)MHz\.(\d+)dB\.(\d+)')
        
        self.resize(1200, 800)
        main_layout = QHBoxLayout(self)
        left_panel = QVBoxLayout()
        
        self.browseBtn = QPushButton("Browse HDF5 File", self)
        self.browseBtn.clicked.connect(self.browseFile)
        left_panel.addWidget(self.browseBtn)
        
        self.plotWidget = PowerHistogramPlot(args)
        left_panel.addWidget(self.plotWidget, stretch=1)
        main_layout.addLayout(left_panel, stretch=3)

        # Right Panel Tab Setup
        self.tabWidget = QTabWidget()
        
        # Tab 1: Dataset Configurations and parameters setup
        param_tab = QWidget()
        param_layout = QVBoxLayout(param_tab)
        
        config_box = QGroupBox("Dataset Selectors")
        config_form = QFormLayout()
        
        self.freq_combo = QComboBox()
        self.att_combo = QComboBox()
        config_form.addRow("Frequency (MHz):", self.freq_combo)
        config_form.addRow("Attenuation (dB):", self.att_combo)
        config_box.setLayout(config_form)
        param_layout.addWidget(config_box)
        
        # Navigation Controls structured in a Grid Layout
        nav_box = QGroupBox("Step Controls")
        nav_layout = QGridLayout()
        
        self.btn_freq_prev = QPushButton("Prev Freq")
        self.btn_freq_next = QPushButton("Next Freq")
        self.btn_att_prev = QPushButton("Prev Att")
        self.btn_att_next = QPushButton("Next Att")
        
        # Row 0: Frequency Steppers
        nav_layout.addWidget(QLabel("Freq:"), 0, 0)
        nav_layout.addWidget(self.btn_freq_prev, 0, 1)
        nav_layout.addWidget(self.btn_freq_next, 0, 2)
        
        # Row 1: Attenuation Steppers
        nav_layout.addWidget(QLabel("Att:"), 1, 0)
        nav_layout.addWidget(self.btn_att_prev, 1, 1)
        nav_layout.addWidget(self.btn_att_next, 1, 2)
        
        nav_box.setLayout(nav_layout)
        param_layout.addWidget(nav_box)
        
        # View modification behaviors
        view_box = QGroupBox("Display Layout Options")
        view_layout = QVBoxLayout()
        self.cb_log_y = QCheckBox("Log Scale (Y-axis)")
        self.cb_log_y.setChecked(True)
        self.cb_fix_xlim = QCheckBox("Fix X-Axis Limits")
        view_layout.addWidget(self.cb_log_y)
        view_layout.addWidget(self.cb_fix_xlim)
        view_box.setLayout(view_layout)
        param_layout.addWidget(view_box)
        
        param_layout.addStretch()
        self.tabWidget.addTab(param_tab, 'Configuration Panels')
        main_layout.addWidget(self.tabWidget, stretch=1)

        # Global layout overrides
        controls_layout = QHBoxLayout()
        self.cb_dark = QCheckBox("Dark Mode")
        controls_layout.addWidget(self.cb_dark)
        left_panel.addLayout(controls_layout)

        # Connect functional changes
        self.freq_combo.currentIndexChanged.connect(self.update_attenuation_options)
        self.att_combo.currentIndexChanged.connect(self.load_and_process_data)
        self.cb_log_y.stateChanged.connect(self.load_and_process_data)
        self.cb_fix_xlim.stateChanged.connect(self.load_and_process_data)
        self.cb_dark.stateChanged.connect(self.toggleDarkMode)
        
        # Setup Button Click Events
        self.btn_freq_prev.clicked.connect(self.on_freq_prev_clicked)
        self.btn_freq_next.clicked.connect(self.on_freq_next_clicked)
        self.btn_att_prev.clicked.connect(self.on_att_prev_clicked)
        self.btn_att_next.clicked.connect(self.on_att_next_clicked)

    def data_changed(self, data, mods, title):
        """ Satisfies ARTIQ's applet pipeline requirements. """
        pass

    def toggleDarkMode(self, state):
        dark = (state == Qt.Checked)
        self.plotWidget.dark_mode = dark
        self.plotWidget.update_color_scheme()
        if dark:
            self.setStyleSheet(
                "background-color: black; color: white; "
                "QTabWidget::pane { background: black; } "
                "QTabBar::tab { background: black; color: white; }"
            )
            self.tabWidget.setStyleSheet(
                "background-color: black; color: white; "
                "QTabWidget::pane { background: black; } "
                "QTabBar::tab { background: black; color: white; }"
            )
        else:
            self.setStyleSheet("")
            self.tabWidget.setStyleSheet("")
        self.load_and_process_data()

    def browseFile(self):
        file_dialog = QFileDialog(self, "Open HDF5 File", "", "HDF5 Files (*.h5 *.hdf5)")
        file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        if file_dialog.exec_() != QFileDialog.Accepted:
            return
            
        self.current_file_path = file_dialog.selectedFiles()[0]
        self.experiment_map.clear()
        
        global_min, global_max = float('inf'), float('-inf')

        try:
            with h5py.File(self.current_file_path, 'r') as f:
                target_root = f['datasets'] if 'datasets' in f else f
                
                for key in target_root.keys():
                    match = self.dataset_pattern.match(key)
                    if match:
                        freq = int(match.group(1))
                        att = int(match.group(2))
                        
                        config_key = (freq, att)
                        if config_key not in self.experiment_map:
                            self.experiment_map[config_key] = []
                        self.experiment_map[config_key].append(key)
                        
                        arr = 10**(target_root[key][()]/10)*1e6
                        if arr.size > 0:
                            global_min = min(global_min, np.min(arr))
                            global_max = max(global_max, np.max(arr))
                            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error scanning file structure: {e}")
            return

        if not self.experiment_map:
            QMessageBox.warning(self, "No Matches", "No keys matched the dataset format rules.")
            return

        self.plotWidget.set_global_limits(global_min, global_max)

        self.freq_combo.blockSignals(True)
        self.freq_combo.clear()
        unique_freqs = sorted(list(set(k[0] for k in self.experiment_map.keys())))
        self.freq_combo.addItems([str(f) for f in unique_freqs])
        self.freq_combo.blockSignals(False)

        self.update_attenuation_options()

    def update_attenuation_options(self):
        if not self.freq_combo.currentText():
            return
        current_freq = int(self.freq_combo.currentText())
        associated_atts = sorted(list(set(k[1] for k in self.experiment_map.keys() if k[0] == current_freq)))
        
        self.att_combo.blockSignals(True)
        self.att_combo.clear()
        self.att_combo.addItems([str(a) for a in associated_atts])
        self.att_combo.blockSignals(False)
        
        self.load_and_process_data()

    def load_and_process_data(self):
        if not self.freq_combo.currentText() or not self.att_combo.currentText():
            return
            
        freq = int(self.freq_combo.currentText())
        att = int(self.att_combo.currentText())
        
        target_keys = self.experiment_map.get((freq, att), [])
        if not target_keys:
            return

        chunks = []
        try:
            with h5py.File(self.current_file_path, 'r') as f:
                target_root = f['datasets'] if 'datasets' in f else f
                for key in target_keys:
                    chunks.append(10**(target_root[key][()]/10)*1e6)
        except Exception as e:
            QMessageBox.warning(self, "Read Error", f"Failed to open datasets: {e}")
            return

        if chunks:
            concatenated_data = np.concatenate(chunks)
            title = f"Distribution Configuration: {freq} MHz | {att} dB (Samples Count: {len(concatenated_data)})"
            
            self.plotWidget.plot_histogram(
                data=concatenated_data,
                title=title,
                log_y=self.cb_log_y.isChecked(),
                fix_xlim=self.cb_fix_xlim.isChecked()
            )

    # Frequency Navigation Methods
    def on_freq_prev_clicked(self):
        idx = self.freq_combo.currentIndex()
        if idx > 0:
            self.freq_combo.setCurrentIndex(idx - 1)
        else:
            self.freq_combo.setCurrentIndex(self.freq_combo.count() - 1)

    def on_freq_next_clicked(self):
        idx = self.freq_combo.currentIndex()
        if idx < self.freq_combo.count() - 1:
            self.freq_combo.setCurrentIndex(idx + 1)
        else:
            self.freq_combo.setCurrentIndex(0)

    # Attenuation Navigation Methods
    def on_att_prev_clicked(self):
        idx = self.att_combo.currentIndex()
        if idx > 0:
            self.att_combo.setCurrentIndex(idx - 1)
        else:
            self.att_combo.setCurrentIndex(self.att_combo.count() - 1)

    def on_att_next_clicked(self):
        idx = self.att_combo.currentIndex()
        if idx < self.att_combo.count() - 1:
            self.att_combo.setCurrentIndex(idx + 1)
        else:
            self.att_combo.setCurrentIndex(0)


# --------------------------- Main Execution Entry ---------------------------
def main():
    applet = TitleApplet(MainWidget)
    try:
        applet.argparser.add_argument('--xlabel', type=str, default='Power (nW)')
        applet.argparser.add_argument('--ylabel', type=str, default='Probability Density / 0.01 nW')
    except Exception:
        pass
    applet.run()

if __name__ == '__main__':
    main()