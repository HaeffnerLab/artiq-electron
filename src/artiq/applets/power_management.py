import sys
import importlib.util
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QDoubleSpinBox, 
                             QPushButton, QGroupBox, QGridLayout, QScrollArea)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

# --- 1. Dynamic Import & Initialization ---
VISA_ADDRESS = "USB0::6833::3601::DP8B260200018::0::INSTR" 

try:
    spec = importlib.util.spec_from_file_location("device_lib", "/home/electron/artiq/experiment/devices/base.py")
    device_lib = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(device_lib)
    
    power_supply = device_lib.RigolDP832A(VISA_ADDRESS) 
except Exception as e:
    print(f"Warning: Could not connect to Rigol DP832A. Running UI in dummy mode. Error: {e}")
    power_supply = None


# --- 2. Modular Device Widget ---
class RigolDP832AWidget(QWidget):
    def __init__(self, device):
        super().__init__()
        self.device = device
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<b>Rigol DP832A Power Supply</b>")
        header.setStyleSheet("font-size: 14pt;")
        main_layout.addWidget(header)
        
        # Channel Selection
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["CH1", "CH2", "CH3"])
        
        ch_layout = QHBoxLayout()
        ch_layout.addWidget(QLabel("<b>Select Channel:</b>"))
        ch_layout.addWidget(self.channel_combo)
        main_layout.addLayout(ch_layout)

        # Settings Group
        settings_group = QGroupBox("Set Parameters")
        settings_layout = QGridLayout()
        
        self.set_v_spinbox = QDoubleSpinBox()
        self.set_v_spinbox.setRange(0, 30.0) 
        self.set_v_spinbox.setDecimals(3)
        self.set_v_spinbox.setSuffix(" V")
        
        self.set_i_spinbox = QDoubleSpinBox()
        self.set_i_spinbox.setRange(0, 3.2)
        self.set_i_spinbox.setDecimals(3)
        self.set_i_spinbox.setSuffix(" A")

        self.apply_btn = QPushButton("Apply Settings")
        self.apply_btn.clicked.connect(self.apply_settings)

        settings_layout.addWidget(QLabel("Voltage:"), 0, 0)
        settings_layout.addWidget(self.set_v_spinbox, 0, 1)
        settings_layout.addWidget(QLabel("Current:"), 1, 0)
        settings_layout.addWidget(self.set_i_spinbox, 1, 1)
        settings_layout.addWidget(self.apply_btn, 2, 0, 1, 2)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # Output Control
        self.output_btn = QPushButton("Turn Output ON")
        self.output_btn.setCheckable(True)
        self.output_btn.setStyleSheet("background-color: lightcoral; font-weight: bold; padding: 10px;")
        self.output_btn.clicked.connect(self.toggle_output)
        main_layout.addWidget(self.output_btn)

        # Measurements Group
        measure_group = QGroupBox("Measurements")
        measure_layout = QVBoxLayout()
        
        # Add the manual trigger button
        self.measure_btn = QPushButton("Measure Now")
        self.measure_btn.setStyleSheet("font-weight: bold; padding: 5px;")
        self.measure_btn.clicked.connect(self.measure_once)
        measure_layout.addWidget(self.measure_btn)
        
        font = QFont("Consolas", 24, QFont.Bold)
        
        self.meas_v_label = QLabel("--- V")
        self.meas_v_label.setFont(font)
        self.meas_v_label.setAlignment(Qt.AlignCenter)
        self.meas_v_label.setStyleSheet("color: #2E86C1;")
        
        self.meas_i_label = QLabel("--- A")
        self.meas_i_label.setFont(font)
        self.meas_i_label.setAlignment(Qt.AlignCenter)
        self.meas_i_label.setStyleSheet("color: #C0392B;")

        measure_layout.addWidget(QLabel("Measured Voltage:"))
        measure_layout.addWidget(self.meas_v_label)
        measure_layout.addWidget(QLabel("Measured Current:"))
        measure_layout.addWidget(self.meas_i_label)
        measure_group.setLayout(measure_layout)
        main_layout.addWidget(measure_group)

    # --- Hardware Interaction Methods ---
    def get_channel_int(self):
        ch_text = self.channel_combo.currentText()
        return int(ch_text.replace("CH", ""))

    def apply_settings(self):
        if not self.device: return
        ch = self.get_channel_int()
        v = self.set_v_spinbox.value()
        i = self.set_i_spinbox.value()
        
        try:
            self.device.set_voltage(ch, v)
            self.device.set_current(ch, i)
        except Exception as e:
            print(f"Error applying settings to CH{ch}: {e}")

    def toggle_output(self):
        ch = self.get_channel_int()
        is_on = self.output_btn.isChecked()
        
        if is_on:
            self.output_btn.setText("Turn Output OFF")
            self.output_btn.setStyleSheet("background-color: lightgreen; font-weight: bold; padding: 10px;")
            if self.device:
                try:
                    self.device.output_on(ch)
                    # Tell PyQt to run self.measure_once exactly 1000ms from now without freezing the UI
                    QTimer.singleShot(1000, self.measure_once)
                except Exception as e:
                    print(f"Error turning ON CH{ch}: {e}")
        else:
            self.output_btn.setText("Turn Output ON")
            self.output_btn.setStyleSheet("background-color: lightcoral; font-weight: bold; padding: 10px;")
            if self.device:
                try:
                    self.device.output_off(ch)
                except Exception as e:
                    print(f"Error turning OFF CH{ch}: {e}")

    def measure_once(self):
        """Called when 'Measure Now' is clicked, or 1s after output turns ON."""
        if not self.device: return
        ch = self.get_channel_int()
        
        try:
            meas_v = self.device.measure_voltage(ch)
            meas_i = self.device.measure_current(ch)
            
            self.meas_v_label.setText(f"{meas_v:.3f} V")
            self.meas_i_label.setText(f"{meas_i:.3f} A")
        except Exception as e:
            print(f"Measurement error: {e}")
            self.meas_v_label.setText("ERR")
            self.meas_i_label.setText("ERR")


# --- 3. Main Application Window ---
class ExperimentDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Experiment Control Dashboard")
        self.resize(450, 520)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)
        
        container = QWidget()
        scroll.setWidget(container)
        
        self.devices_layout = QVBoxLayout(container)
        
        self.rigol_widget = RigolDP832AWidget(power_supply)
        self.devices_layout.addWidget(self.rigol_widget)
        
        self.devices_layout.addStretch()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    
    dashboard = ExperimentDashboard()
    dashboard.show()
    
    exit_code = app.exec_()
    if power_supply:
        power_supply.close()
    sys.exit(exit_code)