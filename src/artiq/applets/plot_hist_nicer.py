#!/usr/bin/env python3
import numpy as np
import PyQt5  # make sure pyqtgraph imports Qt5
import pyqtgraph
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QCheckBox
)
from PyQt5.QtCore import Qt
from artiq.applets.simple import TitleApplet
from scipy.optimize import curve_fit


class XYPlot(pyqtgraph.PlotWidget):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.steps = 0
        self.accumulated_y = np.array([])  # Persistent array storing raw data (dBm)
        self.current_rid = None  # Tracks the current experiment sequence ID
        self.first_call = True  # flag for initial zoom
        self.dark_mode = False  # Dark mode flag
        
        # Default choices per specifications
        self.use_nw = True  
        self.log_y = True  
        
        self.update_color_scheme()
        self.showGrid(x=True, y=True)  # enable grid
        self.update_labels()
        self.update_log_mode()
        
        self.ylim = getattr(args, 'ylim')
        self.legend = self.addLegend()
        
        # Persistent item management to prevent ghosting
        self.hist_item = None
        self.fit_curves = {}

        # Tracking calculated state for accurate curve fitting
        self.current_bin_centers = None
        self.current_probabilities = None

    def update_labels(self):
        """Update axis labels based on selected unit state."""
        ylabel_name = getattr(self.args, 'ylabel', 'Y')
        unit_label = "nW" if self.use_nw else "dBm"
        self.setLabel('bottom', f'Power ({unit_label})')
        self.setLabel('left', 'Probability (Log Scale) / 0.01 nW' if self.log_y else 'Probability / 0.01 nW')

    def update_log_mode(self):
        """Applies log transformation handling directly on the ViewBox."""
        self.setLogMode(x=False, y=self.log_y)

    def update_color_scheme(self):
        """Set the color scheme based on self.dark_mode."""
        if self.dark_mode:
            self.color_scheme = {
                "data": "#aec7e8",     # light blue
                "linear": "#ffbb78",   # light orange
                "exp": "#98df8a",      # light green
                "lor": "#ff9896",      # light red
                "gauss": "#c5b0d5"     # light purple
            }
            self.setBackground("k")  # Black background
            self.getAxis('bottom').setTextPen(pyqtgraph.mkPen("w"))
            self.getAxis('left').setTextPen(pyqtgraph.mkPen("w"))
        else:
            self.color_scheme = {
                "data": "#1f77b4",     # default blue
                "linear": "#ff7f0e",   # default orange
                "exp": "#2ca02c",      # default green
                "lor": "#d62728",      # default red
                "gauss": "#9467bd"     # default purple
            }
            self.setBackground("w")  # White background
            self.getAxis('bottom').setTextPen(pyqtgraph.mkPen("k"))
            self.getAxis('left').setTextPen(pyqtgraph.mkPen("k"))

    def toggleFit(self, fit_type, update=False):
        # Explicitly remove old instances of this specific fit to prevent overlapping line leaks
        if fit_type in self.fit_curves:
            if fit_type == 'find dips':
                if 'curve' in self.fit_curves[fit_type]:
                    self.removeItem(self.fit_curves[fit_type]['curve'])
                for t in self.fit_curves[fit_type].get('labels', []):
                    self.removeItem(t)
            else:
                if 'curve' in self.fit_curves[fit_type]:
                    self.removeItem(self.fit_curves[fit_type]['curve'])
                if 'label' in self.fit_curves[fit_type]:
                    self.legend.removeItem(self.fit_curves[fit_type]['label'])
            
            if not update:
                del self.fit_curves[fit_type]
                return

        if self.current_bin_centers is None or self.current_probabilities is None:
            return

        # Mask out zero probabilities to prevent math errors (especially important in log scale)
        mask = self.current_probabilities > 0
        if not mask.any():
            return
        xdata = self.current_bin_centers[mask]
        ydata = self.current_probabilities[mask]

        # ----- Linear Fit -----
        if fit_type == 'linear':
            def func(x, A, B): return A * x + B
            p0 = [0, np.mean(ydata)]
            eq_str = 'A x + B'
            color = self.color_scheme["linear"]

        # ----- Exponential Decay Fit -----
        elif fit_type == 'exponential decay':
            def func(x, A, B, C): return A * np.exp(-x / B) + C
            x_span = max(xdata) - min(xdata)
            p0 = [max(ydata), x_span if x_span > 0 else 1.0, min(ydata)]
            eq_str = 'A exp(-x/B) + C'
            color = self.color_scheme["exp"]

        # ----- Lorentzian Fit -----
        elif fit_type == 'lorentzian':
            def func(x, A, x0, gamma, C): return A / (1 + ((x - x0) / gamma) ** 2) + C
            x_span = max(xdata) - min(xdata)
            p0 = [max(ydata), xdata[np.argmax(ydata)], x_span / 4 if x_span > 0 else 1.0, min(ydata)]
            eq_str = 'A/(1+((x-x0)/gamma)**2) + C'
            color = self.color_scheme["lor"]

        # ----- Gaussian Fit -----
        elif fit_type == 'gaussian':
            def func(x, A, mu, sigma, C): return A * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2)) + C
            x_span = max(xdata) - min(xdata)
            p0 = [max(ydata), xdata[np.argmax(ydata)], x_span / 4 if x_span > 0 else 1.0, min(ydata)]
            eq_str = 'A exp(-((x-mu)**2)/(2 sigma**2)) + C'
            color = self.color_scheme["gauss"]

        # ----- Double Exponential Fit -----
        elif fit_type == 'double exponential':
            def func(x, A, B, C, D): return A * np.exp(-x / B) + C * np.exp(-x / D)
            x_span = max(xdata) - min(xdata)
            init_b = x_span / 2 if x_span > 0 else 1.0
            p0 = [max(ydata), init_b, max(ydata) / 3, init_b * 2]
            eq_str = 'A exp(-x/B) + C exp(-x/D)'
            color = self.color_scheme["exp"]

        # ----- Double Lorentzian Fit -----
        elif fit_type == 'double lorentzian':
            def func(x, A1, x01, gamma1, A2, x02, gamma2, C):
                return (A1 / (1 + ((x - x01) / gamma1) ** 2) +
                        A2 / (1 + ((x - x02) / gamma2) ** 2) + C)
            x_span = max(xdata) - min(xdata)
            x01_0 = xdata[np.argmax(ydata)]
            init_gamma = x_span / 4 if x_span > 0 else 1.0
            p0 = [max(ydata) / 2, x01_0, init_gamma, max(ydata) / 2, x01_0 + x_span / 4, init_gamma, min(ydata)]
            eq_str = 'A1/(1+((x-x01)/gamma1)**2) + A2/(1+((x-x02)/gamma2)**2) + C'
            color = self.color_scheme["lor"]

        # ----- Find Dips -----
        elif fit_type == 'find dips':
            window = 5
            if window % 2 == 0: window += 1
            half = window // 2
            dip_indices = []
            for i in range(len(ydata)):
                start_win = max(0, i - half)
                end_win = min(len(ydata), i + half + 1)
                if ydata[i] == np.min(ydata[start_win:end_win]):
                    dip_indices.append(i)
            if not dip_indices:
                return
            curve = self.plot(xdata[dip_indices], ydata[dip_indices],
                              pen=None, symbol='x', symbolSize=12, symbolBrush='m')
            labels = []
            for i in dip_indices:
                text = f"({xdata[i]:.2f}, {ydata[i]:.3f})"
                t = pyqtgraph.TextItem(text, anchor=(0, 1), color='m')
                t.setPos(xdata[i], ydata[i])
                self.addItem(t)
                labels.append(t)
            self.fit_curves[fit_type] = {'curve': curve, 'label': 'Dips', 'labels': labels}
            return
        else:
            return

        try:
            popt, pcov = curve_fit(func, xdata, ydata, p0=p0, xtol=1e-10, ftol=1e-10, maxfev=10000)
        except Exception:
            return

        x_fit = np.linspace(np.min(xdata), np.max(xdata), 200)
        y_fit = func(x_fit, *popt)
        param_str = ', '.join([f'{p:.3e}' for p in popt])
        label_text = f'Fit {eq_str}\nparams: {param_str}'
        pen = pyqtgraph.mkPen(color, width=3)
        curve = self.plot(x_fit, y_fit, pen=pen, name=label_text)
        self.fit_curves[fit_type] = {'curve': curve, 'label': label_text}

    def clear_all_data_and_fits(self):
        """Resets structural distribution contexts entirely without breaking layout engines."""
        self.accumulated_y = np.array([])
        self.first_call = True
        self.current_bin_centers = None
        self.current_probabilities = None
        
        if self.hist_item is not None:
            self.removeItem(self.hist_item)
            self.hist_item = None

        for fit_type in list(self.fit_curves.keys()):
            if fit_type == 'find dips':
                for t in self.fit_curves[fit_type].get('labels', []):
                    try: self.removeItem(t)
                    except Exception: pass
            if 'curve' in self.fit_curves[fit_type]:
                try: self.removeItem(self.fit_curves[fit_type]['curve'])
                except Exception: pass
            if 'label' in self.fit_curves[fit_type] and fit_type != 'find dips':
                try: self.legend.removeItem(self.fit_curves[fit_type]['label'])
                except Exception: pass
        self.fit_curves.clear()

    def data_changed(self, data, mods, title0):
        # 1. Extract and monitor the Run ID (RID)
        incoming_rid = None
        try:
            if self.args.rid in data:
                incoming_rid = data[self.args.rid][1]
                if type(incoming_rid) is list: 
                    incoming_rid = incoming_rid[0]
        except KeyError:
            pass

        # Detect structural context shifts via explicit RID value changes
        if incoming_rid is not None and incoming_rid != self.current_rid:
            self.clear_all_data_and_fits()
            self.current_rid = incoming_rid

        # 2. Extract incoming array payload values safely without crashing on UI refreshes
        new_y = np.array([])
        if self.args.y in data:
            try:
                y = data[self.args.y][1]
                if len(np.shape(y)) > 1: 
                    if incoming_rid is not None and len(y) > int(incoming_rid) + 1: 
                        y = y[int(incoming_rid)]
                    else: 
                        y = y[-1]
                new_y = np.array(y).flatten()
            except KeyError:
                pass

        # 3. Detect sequence re-initialization (if data block resets completely to all zeroes)
        if new_y.size > 0 and np.all(new_y == 0):
            self.clear_all_data_and_fits()
            return

        # 4. Append data to existing accumulation profile ONLY if a real payload arrived
        if new_y.size > 0:
            if self.accumulated_y.size == 0:
                self.accumulated_y = new_y
            else:
                self.accumulated_y = np.concatenate([self.accumulated_y, new_y])

        # Safely continue to redraw utilizing cached elements
        if self.accumulated_y.size == 0:
            return

        title = f'RID: {self.current_rid}' if self.current_rid is not None else 'RID'

        # Process scaling conversions
        if self.use_nw:
            display_data = 10 ** ((self.accumulated_y + 60.0) / 10.0)
        else:
            display_data = self.accumulated_y

        # Generate Distribution Metrics
        counts, bin_edges = np.histogram(display_data, bins=50)
        total_counts = len(display_data)
        probabilities = counts / total_counts if total_counts > 0 else counts

        self.current_bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
        self.current_probabilities = probabilities

        fill_color = self.color_scheme["data"]
        brush_arg = pyqtgraph.mkBrush(fill_color + "60")

        # FIX: Provide explicit literal log coordinates when drawing in Log Y mode
        if self.log_y:
            fill_level_arg = -4.0  # Fills correctly down to the 1e-4 floor
            plot_probabilities = np.clip(probabilities, a_min=1e-4, a_max=None)
        else:
            fill_level_arg = 0.0
            plot_probabilities = probabilities

        # Remove the old histogram explicit item object right before drawing the new one
        if self.hist_item is not None:
            self.removeItem(self.hist_item)

        self.hist_item = self.plot(
            bin_edges, plot_probabilities, stepMode=True, 
            fillLevel=fill_level_arg, brush=brush_arg,
            pen=pyqtgraph.mkPen(fill_color, width=2)
        )

        self.setTitle(f"{title} (Accumulated N={total_counts})")
        
        if self.first_call:
            self.getViewBox().enableAutoRange()
            self.first_call = False

        # Continuously refresh active curves over the updated distribution
        for fit_type in list(self.fit_curves.keys()):
            self.toggleFit(fit_type, update=True)


class MainWidget(QWidget):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.resize(1200, 800)
        layout = QHBoxLayout(self)
        self.plotWidget = XYPlot(args)
        layout.addWidget(self.plotWidget, stretch=3)

        right_layout = QVBoxLayout()

        self.cb_dark = QCheckBox('Dark Mode')
        self.cb_nw = QCheckBox('Use nW')
        self.cb_logy = QCheckBox('Log Y')
        
        self.cb_nw.setChecked(True)
        self.cb_logy.setChecked(True)
        
        right_layout.addWidget(self.cb_dark)
        right_layout.addWidget(self.cb_nw)
        right_layout.addWidget(self.cb_logy)

        self.tabWidget = QTabWidget()
        right_layout.addWidget(self.tabWidget, stretch=1)

        fit_tab = QWidget()
        fit_layout = QVBoxLayout(fit_tab)
        self.cb_lin = QCheckBox('Linear')
        self.cb_exp = QCheckBox('Exponential decay')
        self.cb_lor = QCheckBox('Lorentzian')
        self.cb_gauss = QCheckBox('Gaussian')
        self.cb_dexp = QCheckBox('Double exponential')
        self.cb_dlor = QCheckBox('Double lorentzian')
        self.cb_dips = QCheckBox('Find dips')

        fit_layout.addWidget(self.cb_lin)
        fit_layout.addWidget(self.cb_exp)
        fit_layout.addWidget(self.cb_dexp)
        fit_layout.addWidget(self.cb_lor)
        fit_layout.addWidget(self.cb_gauss)
        fit_layout.addWidget(self.cb_dlor)
        fit_layout.addWidget(self.cb_dips)
        fit_layout.addStretch()
        self.tabWidget.addTab(fit_tab, 'Fitting functions')

        layout.addLayout(right_layout, stretch=1)

        self.cb_dark.stateChanged.connect(self.toggleDarkMode)
        self.cb_nw.stateChanged.connect(self.toggleUnitConversion)
        self.cb_logy.stateChanged.connect(self.toggleLogY)

        self.cb_lin.stateChanged.connect(lambda state: self.onFitToggled('linear', state))
        self.cb_exp.stateChanged.connect(lambda state: self.onFitToggled('exponential decay', state))
        self.cb_dexp.stateChanged.connect(lambda state: self.onFitToggled('double exponential', state))
        self.cb_lor.stateChanged.connect(lambda state: self.onFitToggled('lorentzian', state))
        self.cb_gauss.stateChanged.connect(lambda state: self.onFitToggled('gaussian', state))
        self.cb_dlor.stateChanged.connect(lambda state: self.onFitToggled('double lorentzian', state))
        self.cb_dips.stateChanged.connect(lambda state: self.onFitToggled('find dips', state))

    def onFitToggled(self, fit_type, state):
        self.plotWidget.toggleFit(fit_type)

    def toggleUnitConversion(self, state):
        self.plotWidget.use_nw = (state == Qt.Checked)
        self.plotWidget.update_labels()
        self.plotWidget.data_changed({}, mods=None, title0="")

    def toggleLogY(self, state):
        self.plotWidget.log_y = (state == Qt.Checked)
        self.plotWidget.update_log_mode()
        self.plotWidget.update_labels()
        self.plotWidget.data_changed({}, mods=None, title0="")

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
            for cb in self.findChildren(QCheckBox):
                palette = cb.palette()
                palette.setColor(cb.foregroundRole(), Qt.white)
                cb.setPalette(palette)
        else:
            self.setStyleSheet("")
            self.tabWidget.setStyleSheet("")
            for cb in self.findChildren(QCheckBox):
                cb.setPalette(self.style().standardPalette())
            
        self.plotWidget.data_changed({}, mods=None, title0="")

    def data_changed(self, data, mods, title):
        self.plotWidget.data_changed(data, mods, title)


def main():
    applet = TitleApplet(MainWidget)
    applet.add_dataset('y', 'Y values')
    applet.add_dataset('rid', 'RID values', required=False)
    applet.argparser.add_argument('--window', type=int, default=None)
    try:
        applet.argparser.add_argument('--ylim', type=float, default=0.0)
        applet.argparser.add_argument('--xlabel', type=str, default='X')
        applet.argparser.add_argument('--ylabel', type=str, default='Y')
    except Exception:
        pass
    applet.run()


if __name__ == '__main__':
    main()