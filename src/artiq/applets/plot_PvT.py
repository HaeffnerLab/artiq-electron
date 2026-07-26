#!/usr/bin/env python3
import sys
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
from scipy.optimize import curve_fit

# ------------------------- XYPlot (plotting & fitting) -------------------------
class XYPlot(pyqtgraph.PlotWidget):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.steps = 0
        self.datasets = []
        self.first_call = True  
        self.dark_mode = False  
        self.interpolate = False  
        self.update_color_scheme()
        self.showGrid(x=True, y=True)
        xlabel = getattr(args, 'xlabel', 'X')
        ylabel = getattr(args, 'ylabel', 'Y')
        self.setLabel('bottom', xlabel)
        self.setLabel('left', ylabel)
        self.legend = self.addLegend()
        self.color_cycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
                            '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
                            '#bcbd22', '#17becf']
        self.next_color_index = 0

    def update_color_scheme(self):
        if self.dark_mode:
            self.setBackground("k")
            self.getAxis('bottom').setTextPen(pyqtgraph.mkPen("w"))
            self.getAxis('left').setTextPen(pyqtgraph.mkPen("w"))
        else:
            self.setBackground("w")
            self.getAxis('bottom').setTextPen(pyqtgraph.mkPen("k"))
            self.getAxis('left').setTextPen(pyqtgraph.mkPen("k"))

    def get_next_color(self):
        color = self.color_cycle[self.next_color_index]
        self.next_color_index = (self.next_color_index + 1) % len(self.color_cycle)
        return color

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F:
            all_x = np.hstack([d['x'] for d in self.datasets]) if self.datasets else None
            all_y = np.hstack([d['y'] for d in self.datasets]) if self.datasets else None
            if all_x is not None and all_y is not None and len(all_x) > 0:
                mask = all_y > 0
                if mask.any():
                    x_min, x_max = np.min(all_x[mask]), np.max(all_x[mask])
                    y_min, y_max = np.min(all_y[mask]), np.max(all_y[mask])
                else:
                    x_min, x_max = np.min(all_x), np.max(all_x)
                    y_min, y_max = np.min(all_y), np.max(all_y)
                self.getViewBox().setRange(xRange=(x_min, x_max), yRange=(y_min, y_max), padding=0.1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def append_data(self, data, title):
        try:
            y = data['y'][1]
        except KeyError:
            return
        x = data.get('x', (False, None))[1]
        if x is None:
            x = np.arange(len(y))
        x, y = np.array(x), np.array(y)
        color = self.get_next_color()
        interp_pen = pyqtgraph.mkPen(color, style=Qt.SolidLine, width=2.5)
        scatter = self.plot(x, y, pen=interp_pen, symbol='o', symbolSize=6,
                            symbolBrush=color)
        dataset = {'x': x, 'y': y, 'title': title, 'color': color, 'scatter': scatter, 'fits': {}}
        if self.interpolate:
            interp_pen = pyqtgraph.mkPen(color, style=Qt.SolidLine, width=2)
            dataset["interp"] = self.plot(x, y, pen=interp_pen)
        self.datasets.append(dataset)
        self.legend.addItem(scatter, title)

    def clear_data(self):
        self.clear()
        self.datasets = []
        self.next_color_index = 0
        self.legend = self.addLegend()

    def removeFit(self, fit_type):
        for dataset in self.datasets:
            if fit_type in dataset['fits']:
                item = dataset['fits'][fit_type]
                if fit_type == 'find dips':
                    self.removeItem(item['curve'])
                    for t in item['labels']:
                        self.removeItem(t)
                else:
                    self.removeItem(item['curve'])
                    if 'label' in item:
                        self.legend.removeItem(item['label'])
                del dataset['fits'][fit_type]

    def removeInterp(self):
        for dataset in self.datasets:
            if "interp" in dataset:
                self.removeItem(dataset["interp"])
                del dataset["interp"]

    def toggleFit(self, fit_type, update=False):
        if not update:
            self.removeFit(fit_type)
            return

        for dataset in self.datasets:
            if fit_type in dataset['fits']:
                self.removeFit(fit_type)
                if not update:
                    continue

            xdata, ydata = dataset['x'], dataset['y']
            mask = ydata != 0
            if not mask.any():
                continue
            xdata_fit, ydata_fit = xdata[mask], ydata[mask]

            options = None
            parent = self.parent()
            if parent is not None and hasattr(parent, 'fitOptionsWidget'):
                options = parent.fitOptionsWidget.getOptions()

            if options and 'x_range' in options:
                x_range_start, x_range_end = options['x_range']
                mask_xrange = np.where((xdata_fit >= x_range_start) & (xdata_fit <= x_range_end))
                if len(mask_xrange[0]) < 1:
                    continue
                xdata_fit, ydata_fit = xdata_fit[mask_xrange], ydata_fit[mask_xrange]

            if fit_type == 'linear':
                def func(x, A, B): return A * x + B
                p0 = [1, 0]
                eq_str = 'A x + B'
            elif fit_type == 'exponential decay':
                def func(x, A, B, C): return A * np.exp(-x/B) + C
                p0 = [max(ydata_fit) - min(ydata_fit), 1e4, min(ydata_fit)]
                eq_str = 'A exp(-x/B/1000) + C'
            elif fit_type == 'double exponential':
                def func(x, A, q, C, D): return A * np.exp(-x/(q*D)) + C * np.exp(-x/D)
                amp = max(ydata_fit) - min(ydata_fit)
                p0 = [amp, 10/30, amp/3, 30]
                eq_str = 'A exp(-x/B/1000) + C exp(-x/D/1000)'
            elif fit_type == 'lorentzian':
                def func(x, A, x0, gamma, C): return A / (1 + ((x - x0) / gamma)**2) + C
                p0 = [-(max(ydata_fit) - min(ydata_fit)), xdata_fit[np.argmax(ydata_fit)], (max(xdata_fit) - min(xdata_fit)) / 2, max(ydata_fit)]
                eq_str = 'A/(1+((x-x0)/gamma)**2) + C'
            elif fit_type == 'gaussian':
                def func(x, A, mu, sigma, C): return A * np.exp(-((x - mu)**2) / (2 * sigma**2)) + C
                p0 = [-(max(ydata_fit) - min(ydata_fit)), xdata_fit[np.argmax(ydata_fit)], (max(xdata_fit) - min(xdata_fit)) / 4, min(ydata_fit)]
                eq_str = 'A exp(-((x-mu)**2)/(2 sigma**2)) + C'
            elif fit_type == 'double lorentzian':
                def func(x, A1, x01, gamma1, A2, x02, gamma2, C):
                    return (A1 / (1 + ((x - x01)/gamma1)**2) + A2 / (1 + ((x - x02)/gamma2)**2) + C)
                amp = max(ydata_fit) - min(ydata_fit)
                x_range = np.max(xdata_fit) - np.min(xdata_fit)
                x01_0 = xdata_fit[np.argmax(ydata_fit)]
                p0 = [amp/2, x01_0, x_range/4, amp/2, x01_0 + x_range/4, x_range/4, min(ydata_fit)]
                eq_str = 'A1/(1+((x-x01)/gamma1)**2) + A2/(1+((x-x02)/gamma2)**2) + C'
                if options and 'initial_guesses' in options and 'double lorentzian' in options['initial_guesses']:
                    p0 = options['initial_guesses']['double lorentzian']
            elif fit_type == 'find dips':
                window = options.get('dips_window', 10) if options else 10
                if window % 2 == 0: window += 1
                half = window // 2
                dip_indices = []
                for i in range(len(ydata_fit)):
                    start_win, end_win = max(0, i - half), min(len(ydata_fit), i + half + 1)
                    if ydata_fit[i] == np.min(ydata_fit[start_win:end_win]):
                        dip_indices.append(i)
                if len(dip_indices) < 1: continue
                scatter = self.plot(xdata_fit[dip_indices], ydata_fit[dip_indices], pen=None, symbol='x', symbolSize=12, symbolBrush='m')
                labels = []
                for i in dip_indices:
                    t = pyqtgraph.TextItem(f"({xdata_fit[i]:.2f}, {ydata_fit[i]:.2f})", anchor=(0,1), color='m')
                    t.setPos(xdata_fit[i], ydata_fit[i])
                    self.addItem(t)
                    labels.append(t)
                dataset['fits']['find dips'] = {'curve': scatter, 'labels': labels, 'label': 'Dips'}
                continue
            else:
                continue

            if options:
                initial = options.get('initial_guesses', {}).get(fit_type, None)
                if initial is not None and len(initial) > 0: p0 = initial
                start, end = options['range']
                if end == 0: end = len(xdata_fit)
            else:
                start, end = 0, len(xdata_fit)

            try:
                xscale = 1e-3 if np.max(xdata_fit) > 1e3 else 1
                if fit_type == 'double exponential':
                    popt, pcov = curve_fit(func, (xdata_fit*xscale)[start:end], ydata_fit[start:end], p0=p0,
                                           bounds=([-np.inf, 0, 1e-6, -np.inf], [np.inf, 1, np.inf, np.inf]), xtol=1e-10, ftol=1e-10, maxfev=10000)
                    popt[1] *= popt[3]
                    pcov[1][1] *= popt[3]
                else:
                    popt, pcov = curve_fit(func, (xdata_fit*xscale)[start:end], ydata_fit[start:end], p0=p0, xtol=1e-10, ftol=1e-10, maxfev=10000)
            except Exception:
                continue

            x_fit = np.linspace(np.min((xdata_fit*xscale)), np.max((xdata_fit*xscale)), 200)
            y_fit = func(x_fit, *popt)
            mse = sum((func((xdata_fit*xscale)[start:end], *popt) - ydata_fit[start:end])**2) / len((xdata_fit*xscale)[start:end])
            param_str = ', '.join([f'{popt[i]:.2e} +- {np.sqrt(pcov[i][i]):.2e}' for i in range(len(pcov))])
            label_text = f'Fit {eq_str}; Params: {param_str}; MSE: {mse:.2e}'
            curve_item = self.plot(x_fit/xscale, y_fit, pen=pyqtgraph.mkPen(dataset['color'], width=2), name=label_text)
            dataset['fits'][fit_type] = {'curve': curve_item, 'label': label_text}

    def data_changed(self, data, mods, title):
        y_key = getattr(self.args, 'y', 'y')
        try:
            y = data[y_key][1]
        except KeyError:
            return
        x = data.get(getattr(self.args, 'x', 'x'), (False, None))[1]
        if x is None:
            x = np.arange(len(y))
        error = data.get(getattr(self.args, 'error', 'error'), (False, None))[1]
        fit = data.get(getattr(self.args, 'fit', 'fit'), (False, None))[1]
        if not len(y) or len(y) != len(x):
            return
        x, y = np.array(x), np.array(y)
        color = self.get_next_color()
        interp_pen = pyqtgraph.mkPen(color, style=Qt.SolidLine, width=2.5)
        scatter = self.plot(x, y, pen=interp_pen, symbol='o', symbolSize=6,
                            symbolBrush=color)
        if error is not None and hasattr(error, '__len__') and len(error) == len(y):
            self.addItem(pyqtgraph.ErrorBarItem(x=x, y=y, height=np.array(error)))
        if fit is not None and len(fit) == len(y):
            xi = np.argsort(x)
            self.plot(x[xi], np.array(fit)[xi])
        self.datasets.append({'x': x, 'y': y, 'title': title, 'color': color, 'scatter': scatter, 'fits': {}})
        self.setTitle(title)
        all_x = np.hstack([d['x'] for d in self.datasets])
        all_y = np.hstack([d['y'] for d in self.datasets])
        self.getViewBox().setRange(xRange=(np.min(all_x), np.max(all_x)), yRange=(np.min(all_y), np.max(all_y)), padding=0.1)

# ------------------ Fit Options Widget ------------------
class FitOptionsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        guess_group = QGroupBox("Initial Guess Parameters")
        guess_layout = QFormLayout()
        self.lin_guess = QLineEdit()
        self.exp_guess = QLineEdit()
        self.dexp_guess = QLineEdit()
        self.lorentz_guess = QLineEdit()
        self.gauss_guess = QLineEdit()
        self.dlor_guess = QLineEdit()
        guess_layout.addRow("Linear (A,B):", self.lin_guess)
        guess_layout.addRow("Exponential decay (A,B,C):", self.exp_guess)
        guess_layout.addRow("Double exponential (A,B,C,D):", self.dexp_guess)
        guess_layout.addRow("Lorentzian (A,x0,gamma,C):", self.lorentz_guess)
        guess_layout.addRow("Gaussian (A,mu,sigma,C):", self.gauss_guess)
        guess_layout.addRow("Double Lorentzian:", self.dlor_guess)
        guess_group.setLayout(guess_layout)
        layout.addWidget(guess_group)

        range_group = QGroupBox("Fitting Range (Indices)")
        range_layout = QHBoxLayout()
        self.start_index, self.end_index = QSpinBox(), QSpinBox()
        self.start_index.setPrefix("Start: ")
        self.end_index.setMinimum(-999)
        self.end_index.setPrefix("End: ")
        range_layout.addWidget(self.start_index)
        range_layout.addWidget(self.end_index)
        range_group.setLayout(range_layout)
        layout.addWidget(range_group)

        xrange_group = QGroupBox("Fitting Range (x ranges)")
        xrange_layout = QHBoxLayout()
        self.x_range_start, self.x_range_end = QDoubleSpinBox(), QDoubleSpinBox()
        for box in [self.x_range_start, self.x_range_end]:
            box.setDecimals(2)
            box.setRange(-1e12, 1e12)
        self.x_range_start.setValue(-1e9); self.x_range_start.setPrefix("x Start: ")
        self.x_range_end.setValue(1e9); self.x_range_end.setPrefix("x End: ")
        xrange_layout.addWidget(self.x_range_start)
        xrange_layout.addWidget(self.x_range_end)
        xrange_group.setLayout(xrange_layout)
        layout.addWidget(xrange_group)

        dips_group = QGroupBox("Find Dips Options")
        dips_layout = QHBoxLayout()
        self.dips_window = QSpinBox()
        self.dips_window.setMinimum(3); self.dips_window.setValue(10); self.dips_window.setPrefix("Window: ")
        dips_layout.addWidget(self.dips_window)
        dips_group.setLayout(dips_layout)
        layout.addWidget(dips_group)

        self.apply_button = QPushButton("Apply Fit Options")
        layout.addWidget(self.apply_button)
        layout.addStretch()

    def getOptions(self):
        options = {}
        initial_guesses = {}
        def parse_guess(text):
            try: return [float(p.strip()) for p in text.split(',') if p.strip() != ""]
            except Exception: return None
        for key, field in [('linear', self.lin_guess), ('exponential decay', self.exp_guess), 
                           ('double exponential', self.dexp_guess), ('lorentzian', self.lorentz_guess), 
                           ('gaussian', self.gauss_guess), ('double lorentzian', self.dlor_guess)]:
            val = parse_guess(field.text())
            if val: initial_guesses[key] = val
        options['initial_guesses'] = initial_guesses
        options['range'] = (self.start_index.value(), self.end_index.value())
        options['x_range'] = (self.x_range_start.value(), self.x_range_end.value())
        options['dips_window'] = self.dips_window.value()
        return options

# ----------------- Variable Selection Dialog -----------------
class VariableSelectionDialog(QDialog):
    def __init__(self, dataset_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Variables")
        self.selected_x, self.selected_y = None, None
        layout = QGridLayout(self)
        layout.addWidget(QLabel("x variable"), 0, 0)
        layout.addWidget(QLabel("y variable"), 0, 1)
        self.x_combo, self.y_combo = QComboBox(self), QComboBox(self)
        for name, array in dataset_dict.items():
            length = 0 if len(np.shape(array)) < 1 else np.shape(array)[0]
            display_text = f"{name} <{length}>"
            self.x_combo.addItem(display_text, userData=name)
            self.y_combo.addItem(display_text, userData=name)
        layout.addWidget(self.x_combo, 1, 0)
        layout.addWidget(self.y_combo, 1, 1)
        ok_btn = QPushButton("OK", self)
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn, 2, 0, 1, 2)

    def accept(self):
        self.selected_x = self.x_combo.currentData()
        self.selected_y = self.y_combo.currentData()
        super().accept()

# ------------------------ MainWidget ------------------------
class MainWidget(QWidget):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.pvt_data = {}  
        self.t_data = None  
        self.pvt_ymin = None  
        self.pvt_ymax = None  
        self.resize(1200, 800)
        main_layout = QHBoxLayout(self)
        left_panel = QVBoxLayout(self)
        self.browseBtn = QPushButton("Browse HDF5 File", self)
        self.browseBtn.clicked.connect(self.browseFile)
        left_panel.addWidget(self.browseBtn)
        self.plotWidget = XYPlot(args)
        left_panel.addWidget(self.plotWidget, stretch=1)
        main_layout.addLayout(left_panel, stretch=3)

        self.tabWidget = QTabWidget()
        
        # Tab 1: Fitting Functions
        fit_tab = QWidget()
        fit_layout = QVBoxLayout(fit_tab)
        self.cb_interp = QCheckBox('Interpolate')
        self.cb_lin = QCheckBox('Linear')
        self.cb_exp = QCheckBox('Exponential decay')
        self.cb_dexp = QCheckBox('Double exponential')
        self.cb_lor = QCheckBox('Lorentzian')
        self.cb_gauss = QCheckBox('Gaussian')
        self.cb_dlor = QCheckBox('Double lorentzian')
        self.cb_dips = QCheckBox('Find dips')
        for cb in [self.cb_interp, self.cb_lin, self.cb_exp, self.cb_dexp, self.cb_lor, self.cb_gauss, self.cb_dlor, self.cb_dips]:
            fit_layout.addWidget(cb)
        self.cb_interp.stateChanged.connect(lambda state: self.plotWidget.removeInterp() if not state else None)
        self.cb_interp.stateChanged.connect(self.toggleInterpolate)
        fit_layout.addStretch()
        self.tabWidget.addTab(fit_tab, 'Fitting functions')
        
        # Tab 2: Fit Options
        self.fitOptionsWidget = FitOptionsWidget(self)
        self.tabWidget.addTab(self.fitOptionsWidget, 'Fit Options')
        
        # Tab 3: PvT Viewer Controls (PvT view active and default)
        pvt_tab = QWidget()
        pvt_layout = QVBoxLayout(pvt_tab)
        
        dropdown_group = QGroupBox("Filter Configurations")
        dropdown_layout = QFormLayout()
        
        self.combo_freq = QComboBox()
        self.combo_att = QComboBox()
        self.combo_N = QComboBox()
        
        # Setup Freq row with Prev/Next buttons
        layout_freq = QHBoxLayout()
        self.btn_freq_prev = QPushButton("Prev")
        self.btn_freq_prev.setFixedWidth(50)
        self.btn_freq_next = QPushButton("Next")
        self.btn_freq_next.setFixedWidth(50)
        layout_freq.addWidget(self.btn_freq_prev)
        layout_freq.addWidget(self.combo_freq, stretch=1)
        layout_freq.addWidget(self.btn_freq_next)
        
        # Setup Attenuation row with Prev/Next buttons
        layout_att = QHBoxLayout()
        self.btn_att_prev = QPushButton("Prev")
        self.btn_att_prev.setFixedWidth(50)
        self.btn_att_next = QPushButton("Next")
        self.btn_att_next.setFixedWidth(50)
        layout_att.addWidget(self.btn_att_prev)
        layout_att.addWidget(self.combo_att, stretch=1)
        layout_att.addWidget(self.btn_att_next)
        
        # Setup N parameter row with Prev/Next buttons
        layout_N = QHBoxLayout()
        self.btn_N_prev = QPushButton("Prev")
        self.btn_N_prev.setFixedWidth(50)
        self.btn_N_next = QPushButton("Next")
        self.btn_N_next.setFixedWidth(50)
        layout_N.addWidget(self.btn_N_prev)
        layout_N.addWidget(self.combo_N, stretch=1)
        layout_N.addWidget(self.btn_N_next)

        dropdown_layout.addRow("Driving Freq (MHz):", layout_freq)
        dropdown_layout.addRow("Attenuation (dB):", layout_att)
        dropdown_layout.addRow("N parameter:", layout_N)
        dropdown_group.setLayout(dropdown_layout)
        pvt_layout.addWidget(dropdown_group)
        
        xlim_group = QGroupBox("Manual Limits")
        xlim_layout = QHBoxLayout()
        self.cb_custom_xlim = QCheckBox("Fix X")
        self.xlim_min = QDoubleSpinBox()
        self.xlim_max = QDoubleSpinBox()
        for box in [self.xlim_min, self.xlim_max]:
            box.setRange(-1e9, 1e9)
            box.setDecimals(1)
        self.xlim_max.setValue(100.0)
        
        self.cb_fix_ylim = QCheckBox("Fix Y")
        
        xlim_layout.addWidget(self.cb_custom_xlim)
        xlim_layout.addWidget(QLabel("Min X:"))
        xlim_layout.addWidget(self.xlim_min)
        xlim_layout.addWidget(QLabel("Max X:"))
        xlim_layout.addWidget(self.xlim_max)
        xlim_layout.addWidget(self.cb_fix_ylim)
        xlim_group.setLayout(xlim_layout)
        pvt_layout.addWidget(xlim_group)
        
        pvt_layout.addStretch()
        self.tabWidget.addTab(pvt_tab, 'PvT Viewer')
        main_layout.addWidget(self.tabWidget, stretch=1)

        # Bottom UI utilities
        controls_layout = QHBoxLayout()
        self.cb_dark = QCheckBox("Dark Mode")
        self.cb_dark.stateChanged.connect(self.toggleDarkMode)
        controls_layout.addWidget(self.cb_dark)
        self.clearBtn = QPushButton("Clear")
        self.clearBtn.clicked.connect(self.clearPlot)
        controls_layout.addWidget(self.clearBtn)
        left_panel.addLayout(controls_layout)

        # Wire up actions
        self.cb_lin.stateChanged.connect(lambda state: self.onFitToggled('linear', state))
        self.cb_exp.stateChanged.connect(lambda state: self.onFitToggled('exponential decay', state))
        self.cb_dexp.stateChanged.connect(lambda state: self.onFitToggled('double exponential', state))
        self.cb_lor.stateChanged.connect(lambda state: self.onFitToggled('lorentzian', state))
        self.cb_gauss.stateChanged.connect(lambda state: self.onFitToggled('gaussian', state))
        self.cb_dlor.stateChanged.connect(lambda state: self.onFitToggled('double lorentzian', state))
        self.cb_dips.stateChanged.connect(lambda state: self.onFitToggled('find dips', state))
        self.fitOptionsWidget.apply_button.clicked.connect(self.updateFitCurves)
        
        # Link dropdown navigation button actions
        self.btn_freq_prev.clicked.connect(lambda: self.step_combobox(self.combo_freq, -1))
        self.btn_freq_next.clicked.connect(lambda: self.step_combobox(self.combo_freq, 1))
        self.btn_att_prev.clicked.connect(lambda: self.step_combobox(self.combo_att, -1))
        self.btn_att_next.clicked.connect(lambda: self.step_combobox(self.combo_att, 1))
        self.btn_N_prev.clicked.connect(lambda: self.step_combobox(self.combo_N, -1))
        self.btn_N_next.clicked.connect(lambda: self.step_combobox(self.combo_N, 1))
        
        # Link dropdown/limit hooks directly to active updates
        self.combo_freq.currentIndexChanged.connect(self.updatePvTPlot)
        self.combo_att.currentIndexChanged.connect(self.updatePvTPlot)
        self.combo_N.currentIndexChanged.connect(self.updatePvTPlot)
        self.cb_custom_xlim.stateChanged.connect(self.updatePvTPlot)
        self.cb_fix_ylim.stateChanged.connect(self.updatePvTPlot)
        self.xlim_min.valueChanged.connect(self.updatePvTPlot)
        self.xlim_max.valueChanged.connect(self.updatePvTPlot)
        
        # Set PvT viewer active on startup layout
        self.tabWidget.setCurrentIndex(2)

    def step_combobox(self, combo, delta):
        """Helper to safely step forward or backward through QComboBox indices."""
        count = combo.count()
        if count <= 1:
            return
        new_index = (combo.currentIndex() + delta) % count
        combo.setCurrentIndex(new_index)

    def toggleDarkMode(self, state):
        dark = (state == Qt.Checked)
        self.plotWidget.dark_mode = dark
        self.plotWidget.update_color_scheme()
        if dark:
            style = "background-color: black; color: white; QTabWidget::pane { background: black; } QTabBar::tab { background: black; color: white; }"
            self.setStyleSheet(style); self.tabWidget.setStyleSheet(style)
        else:
            self.setStyleSheet(""); self.tabWidget.setStyleSheet("")
        for dataset in self.plotWidget.datasets:
            dataset['scatter'].setSymbolBrush(dataset['color'])

    def toggleInterpolate(self, state):
        self.plotWidget.interpolate = (state == Qt.Checked)
        if state:
            for d in self.plotWidget.datasets:
                if "interp" not in d:
                    d["interp"] = self.plotWidget.plot(d['x'], d['y'], pen=pyqtgraph.mkPen(d['color'], style=Qt.DashLine, width=2))
        else:
            self.plotWidget.removeInterp()

    def onFitToggled(self, fit_type, state):
        if state: self.plotWidget.toggleFit(fit_type, update=True)
        else: self.plotWidget.removeFit(fit_type)

    def updateFitCurves(self):
        fits = ['linear', 'exponential decay', 'double exponential', 'lorentzian', 'gaussian', 'double lorentzian']
        boxes = [self.cb_lin, self.cb_exp, self.cb_dexp, self.cb_lor, self.cb_gauss, self.cb_dlor]
        for f, cb in zip(fits, boxes):
            if cb.isChecked(): self.plotWidget.toggleFit(f, update=True)
        if self.cb_dips.isChecked(): self.plotWidget.toggleFit('find dips', update=True)
        else: self.plotWidget.removeFit('find dips')

    def clearFitOptions(self): 
        for cb in [self.cb_interp, self.cb_lin, self.cb_exp, self.cb_dexp, self.cb_lor, self.cb_gauss, self.cb_dlor, self.cb_dips]:
            cb.setChecked(False)

    def clearPlot(self):
        self.plotWidget.clear_data()
        self.clearFitOptions()

    def show_message(self, title, message):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title); msg_box.setText(message); msg_box.exec_()

    def browseFile(self):
        self.clearFitOptions()
        
        # Modified line: Changed default directory string parameter
        default_dir = "/home/electron/artiq/experiment/artiq-master/results"
        file_dialog = QFileDialog(self, "Open HDF5 File", default_dir, "HDF5 Files (*.h5 *.hdf5)")
        file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        if file_dialog.exec_() != QFileDialog.Accepted:
            return
        file_path = file_dialog.selectedFiles()[0]
        
        self.pvt_data.clear()
        self.t_data = None
        self.pvt_ymin = None
        self.pvt_ymax = None
        
        pattern = re.compile(r'[dd]?ata\.(\d+(?:\.\d+)?)MHz\.(\d+(?:\.\d+)?)dB\.(\d+)')
        
        try:
            with h5py.File(file_path, 'r') as file:
                if 't_data' in file:
                    self.t_data = np.array(file['t_data'][()])
                elif 'datasets' in file and 't_data' in file['datasets']:
                    self.t_data = np.array(file['datasets']['t_data'][()])
                
                dataset_names = list(file['datasets'].keys()) if 'datasets' in file else []
                data_dict = {name: np.array(file['datasets'][name][()]) for name in dataset_names}
                
                for name in dataset_names:
                    match = pattern.match(name)
                    if match:
                        freq, att, N = match.groups()
                        self.pvt_data[(freq, att, N)] = np.array(file['datasets'][name][()])
                
                for attr_source in [file, file.get('datasets')]:
                    if attr_source is not None:
                        for attr_name in attr_source.attrs.keys():
                            match = pattern.match(attr_name)
                            if match:
                                freq, att, N = match.groups()
                                self.pvt_data[(freq, att, N)] = np.array(attr_source.attrs[attr_name])
                                
        except Exception as e:
            self.show_message("Error", f"Error reading file: {e}")
            return

        if self.pvt_data:
            unique_freqs = sorted(list(set(k[0] for k in self.pvt_data.keys())), key=float)
            unique_atts = sorted(list(set(k[1] for k in self.pvt_data.keys())), key=float)
            unique_Ns = sorted(list(set(k[2] for k in self.pvt_data.keys())), key=int)
            
            all_y_values = [y.ravel() for y in self.pvt_data.values() if y.size > 0]
            if all_y_values:
                combined_y = np.concatenate(all_y_values)
                self.pvt_ymin = float(np.min(combined_y))
                self.pvt_ymax = float(np.max(combined_y))

            for combo, options in [(self.combo_freq, unique_freqs), (self.combo_att, unique_atts), (self.combo_N, unique_Ns)]:
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(options)
                combo.blockSignals(False)
                
            self.tabWidget.setCurrentIndex(2)  
            self.updatePvTPlot()
            return

        if not dataset_names:
            self.show_message("No Datasets", "No matching records found in this file.")
            return
            
        var_dialog = VariableSelectionDialog(data_dict, self)
        if var_dialog.exec_() == QDialog.Accepted:
            x_key, y_key = var_dialog.selected_x, var_dialog.selected_y
            new_data = {'y': (True, data_dict[y_key])}
            if x_key: new_data['x'] = (True, data_dict[x_key])
            self.plotWidget.data_changed(new_data, mods=None, title=f"{x_key} vs {y_key}")

    def updatePvTPlot(self):
        if not self.pvt_data:
            return
            
        freq = self.combo_freq.currentText()
        att = self.combo_att.currentText()
        N = self.combo_N.currentText()
        key = (freq, att, N)
        
        if key in self.pvt_data:
            y_data = self.pvt_data[key]
            if y_data.ndim > 1:
                y_data = y_data.ravel()
                
            if self.t_data is not None and len(self.t_data) == len(y_data):
                x_data = self.t_data
            else:
                x_data = np.arange(len(y_data))
            
            self.plotWidget.clear_data()
            title = f"PvT: {freq}MHz | {att}dB | N={N}"
            
            new_data = {'y': (True, y_data), 'x': (True, x_data)}
            self.plotWidget.data_changed(new_data, mods=None, title=title)
            
            range_kwargs = {}
            if self.cb_custom_xlim.isChecked():
                range_kwargs['xRange'] = (self.xlim_min.value(), self.xlim_max.value())
                
            if self.cb_fix_ylim.isChecked() and self.pvt_ymin is not None and self.pvt_ymax is not None:
                range_kwargs['yRange'] = (self.pvt_ymin, self.pvt_ymax)
            
            if range_kwargs:
                range_kwargs['padding'] = 0.0
                self.plotWidget.getViewBox().setRange(**range_kwargs)
            
            self.updateFitCurves()
        else:
            self.plotWidget.clear_data()
            self.plotWidget.setTitle(f"Configuration combination {key} unavailable.")

    def data_changed(self, data, mods, title):
        self.plotWidget.data_changed(data, mods, title)

# --------------------------- Main Applet Initialization -----------------------------------
def main():
    applet = TitleApplet(MainWidget)
    applet.add_dataset('error', 'Error bars for each X value', required=False)
    applet.add_dataset('fit', 'Fit values for each X value', required=False)
    try:
        applet.argparser.add_argument('--range', type=int, default=None)
        applet.argparser.add_argument('--xlabel', type=str, default='Time (s)')
        applet.argparser.add_argument('--ylabel', type=str, default='Power (dBm)')
        applet.argparser.add_argument('--title', type=str, default='PvT Scope')
    except Exception:
        pass
    applet.run()

if __name__ == '__main__':
    main()