#!/usr/bin/env python3
import sys
from artiq.experiment import *
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QFileDialog
from artiq.experiment import *
import subprocess
import pandas as pd
import os
import numpy as np
from PyQt5.QtGui import QPixmap

class App(QDialog):
  def __init__(self):
          super().__init__()
          self.file = open('src/artiq/applets/cfile.txt').read()
          
          self.f = open('src/artiq/applets/cali_file.txt').read()
          self.title = 'PyQt5 layout - pythonspot.com'
          self.left = 10
          self.top = 10
          self.width = 320
          self.height = 100
          self.setWindowTitle(self.title)
          self.setGeometry(self.left, self.top, self.width, self.height)
          self.makeGrid()

          


          windowLayout = QVBoxLayout()
          windowLayout.addWidget(self.horizontalGroupBox)
          self.setLayout(windowLayout)

          self.show()

  def makeGrid(self):
      self.horizontalGroupBox = QGroupBox("")
      layout = QGridLayout()
      
      self.setStyleSheet("background-color: #000000; color: #FFFFFF;")
      #self.setStyleSheet("background-color: #333333; color: #FFFFFF;")
      self.dataset_prefix = "optimize.e"
      self.attributes_list = ['bl1', 'bl2', 'bl3', 'bl4', 'bl5',
                              'br1', 'br2', 'br3', 'br4', 'br5',
                              'tl1', 'tl2', 'tl3', 'tl4', 'tl5',
                              'tr1', 'tr2', 'tr3', 'tr4', 'tr5', 'Ex', 'Ey', 'Ez', 'U1', 'U2', 'U3', 'U4', 'U5']
      self.value_labels = {}
      for i, attr in enumerate(self.attributes_list[:20]):
            name_label = QLabel(f"{attr}:")
            name_label.setStyleSheet("font-weight: bold; font-size: 14px;")

            val_label = QLineEdit("Fetching from Master DB...")
            val_label.setStyleSheet("font-size: 14px; font-family: monospace; ")
            val_label.setFixedSize(75, 20)
            widget = QWidget()
            combined = QHBoxLayout()
            combined.setSpacing(15)
            combined.addWidget(name_label)
            combined.addWidget(val_label)
            widget.setStyleSheet("background-color: #0A3161;")
            widget.setLayout(combined)

            layout.addWidget(widget, i%5, i//5)
            self.value_labels[attr] = val_label
      for i, attr in enumerate(self.attributes_list[20:]):
            name_label = QLabel(f"{attr}:")
            name_label.setStyleSheet("font-weight: bold; font-size: 14px")

            val_label = QLineEdit("Fetching from Master DB...")
            val_label.setStyleSheet("font-size: 14px; font-family: monospace;")
            val_label.setFixedSize(75, 20)
            widget = QWidget()
            combined = QHBoxLayout()
            combined.setSpacing(15)
            combined.addWidget(name_label)
            combined.addWidget(val_label)
            widget.setLayout(combined)
            widget.setStyleSheet("background-color: #0A3161;")

            layout.addWidget(widget, i%5, (i//5)+5)
            self.value_labels[attr] = val_label
      load_dac_button = QPushButton("Load DAC")
      layout.addWidget(load_dac_button, 4,4)
      load_dac_button.clicked.connect(self.load_dac)
      c_file_name = QLabel(str(self.file))
      layout.addWidget(c_file_name, 1, 4)
      load_c_file = QPushButton("Choose C File")
      load_c_file.clicked.connect(self.choose_your_c_file_now_if_you_want)
      layout.addWidget(load_c_file, 0,4)


      load_cal_file = QPushButton("Choose Calibration File")
      load_cal_file.clicked.connect(self.cali_file)
      layout.addWidget(load_cal_file, 2,4)
      cal_file_name = QLabel(self.f)
      layout.addWidget(cal_file_name, 3, 4)
      self.horizontalGroupBox.setLayout(layout)
      self.name_list = [c_file_name, cal_file_name]
  def choose_your_c_file_now_if_you_want(self):
      self.file = QFileDialog.getOpenFileName()[0]
      open('/home/electron/artiq/src/artiq/applets/cfile.txt', 'w').write(self.file)
      self.name_list[0].setText(self.file)
      
  def cali_file(self):
        self.f = QFileDialog.getOpenFileName()[0]
        open('/home/electron/artiq/src/artiq/applets/cali_file.txt', 'w').write(self.file)
        self.name_list[1].setText(self.f)
  def load_dac(self):
    tmp = np.loadtxt(self.f)
    self.dac_calibration_fit = tmp
    self.pin_matching = {
            "bl1":2,
            "bl2":4,
            "bl3":6,
            "bl4":8,
            "bl5":18,
            "br1":24,
            "br2":22,
            "br3":20,
            "br4":10,
            "br5":16,
            "tl1":12,
            "tl2":23,
            "tl3":9,
            "tl4":19,
            "tl5":17,
            "tr1":3,
            "tr2":5,
            "tr3":11,
            "tr4":21,
            "tr5":7,
            }
    multipole_v = [float(x.text()) for x in list(self.value_labels.values())[20:]]
    if any(multipole_v):
        self.update_multipoles()
    else:
        for i,x in enumerate(self.value_labels.keys()):
            prefix = 'new_ARTIQ_dataset_for_the_dashboard.electrode.'
            prefix2 = 'hidden_ARTIQ_dataset_after_calibrated_for_amplifier.'
            if x[0] == "E" or x[0] == "U":
                prefix = 'new_ARTIQ_dataset_for_the_dashboard.multipoles.'

            cmd = ["artiq_client",  "set-dataset", prefix+x, self.value_labels[x].text(), '-p']
            subprocess.run(cmd)
            if (i < 20):
                m = self.dac_calibration_fit[1][self.pin_matching[x]]
                b = self.dac_calibration_fit[0][self.pin_matching[x]]
                print(str((float(self.value_labels[x].text())-b)/m))
                cmd = ["artiq_client",  "set-dataset", prefix2+x+'.v', str(self.value_labels[x].text()), '-p']
                subprocess.run(cmd)
                cmd = ["artiq_client",  "set-dataset", prefix2+x+'.m', str(m), '-p']
                subprocess.run(cmd)
                cmd = ["artiq_client",  "set-dataset", prefix2+x+'.b', str(b), '-p']
                subprocess.run(cmd)
    self.script_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = ["artiq_client", "submit", "/home/electron/artiq/experiment/artiq-master/repository/experiment_sequences/instruments/load_voltages.py"]
    subprocess.run(cmd, cwd=self.script_dir)
    print("voltages loaded")

  def update_multipoles(self):
        self.pin_matching = {
            "bl1":19,
            "bl2":18,
            "bl3":6,
            "bl4":1,
            "bl5":4,
            "br1":7,
            "br2":17,
            "br3":2,
            "br4":10,
            "br5":15,
            "tl1":24,
            "tl2":25,
            "tl3":13,
            "tl4":22,
            "tl5":23,
            "tr1":20,
            "tr2":8,
            "tr3":11,
            "tr4":21,
            "tr5":12,
            }
        
        self.controlled_multipoles = ["Ex","Ey","Ez","U1","U2","U3","U4","U5"]

        
        df = pd.read_csv(self.file,index_col = 0)
        voltages = pd.Series(np.zeros(len(self.pin_matching.keys())),index = df.index.values)
        # print("Multipoles:",dac_ms)
        for m in self.controlled_multipoles:
            voltages += df[m] * float(self.value_labels[m].text())
        dac_vs = voltages.to_dict()
    
        for x in dac_vs.keys():
            prefix = 'new_ARTIQ_dataset_for_the_dashboard.electrode.'
            prefix2 = 'hidden_ARTIQ_dataset_after_calibrated_for_amplifier.'
            if x[0] == "E" or x[0] == "U":
                prefix = 'new_ARTIQ_dataset_for_the_dashboard.multipoles.'
            cmd = ["artiq_client",  "set-dataset", prefix+x, str(dac_vs[x]), '-p']
            self.value_labels[x].setText(str(dac_vs[x]))
            self.value_labels[x].setCursorPosition(0)
            subprocess.run(cmd)
            m = self.dac_calibration_fit[1][self.pin_matching[x]]
            b = self.dac_calibration_fit[0][self.pin_matching[x]]
            cmd = ["artiq_client",  "set-dataset", prefix2+x+'.v', str(dac_vs[x]), '-p']
            subprocess.run(cmd)
            cmd = ["artiq_client",  "set-dataset", prefix2+x+'.m', str(m), '-p']
            subprocess.run(cmd)
            cmd = ["artiq_client",  "set-dataset", prefix2+x+'.b', str(b), '-p']
        for x in self.controlled_multipoles:
            prefix = 'new_ARTIQ_dataset_for_the_dashboard.multipoles.'
            cmd = ["artiq_client",  "set-dataset", prefix+x, self.value_labels[x].text(), '-p']
            subprocess.run(cmd)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    for attr in ex.attributes_list:
        ex.value_labels[attr].setText("0.0")
    ex.show()
    sys.exit(app.exec_())


def load_dac_prg(file, cali, voltages):
    pin_matching = {
            "bl1":2,
            "bl2":4,
            "bl3":6,
            "bl4":8,
            "bl5":18,
            "br1":24,
            "br2":22,
            "br3":20,
            "br4":10,
            "br5":16,
            "tl1":12,
            "tl2":23,
            "tl3":9,
            "tl4":19,
            "tl5":17,
            "tr1":3,
            "tr2":5,
            "tr3":11,
            "tr4":21,
            "tr5":7,
            }
    attributes_list = ['bl1', 'bl2', 'bl3', 'bl4', 'bl5',
                              'br1', 'br2', 'br3', 'br4', 'br5',
                              'tl1', 'tl2', 'tl3', 'tl4', 'tl5',
                              'tr1', 'tr2', 'tr3', 'tr4', 'tr5', 'Ex', 'Ey', 'Ez', 'U1', 'U2', 'U3', 'U4', 'U5']
    dac_calibration_fit = np.loadtxt(cali)
    multipole_v = [float(x) for x in voltages[20:]]
    if any(multipole_v):
        update_multipoles_prg(file, dac_calibration_fit, voltages)
    else:
        for i,x in enumerate(voltages):
            prefix = 'new_ARTIQ_dataset_for_the_dashboard.electrode.'
            prefix2 = 'hidden_ARTIQ_dataset_after_calibrated_for_amplifier.'

            cmd = ["artiq_client",  "set-dataset", prefix+attributes_list[i], str(x), '-p']
            subprocess.run(cmd)
            if (i < 20):
                m = dac_calibration_fit[1][pin_matching[attributes_list[i]]]
                b = dac_calibration_fit[0][pin_matching[attributes_list[i]]]
                cmd = ["artiq_client",  "set-dataset", prefix2+str(attributes_list[i])+'.v', str(x), '-p']
                subprocess.run(cmd)
                cmd = ["artiq_client",  "set-dataset", prefix2+str(attributes_list[i])+'.m', str(m), '-p']
                subprocess.run(cmd)
                cmd = ["artiq_client",  "set-dataset", prefix2+str(attributes_list[i])+'.b', str(b), '-p']
                subprocess.run(cmd)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = ["artiq_client", "submit", "/home/electron/artiq/experiment/artiq-master/repository/experiment_sequences/instruments/load_voltages.py"]
    subprocess.run(cmd, cwd=script_dir)
    print("voltages loaded")


def update_multipoles_prg(file, dac_cali, v):
        pin_matching = {
            "bl1":19,
            "bl2":18,
            "bl3":6,
            "bl4":1,
            "bl5":4,
            "br1":7,
            "br2":17,
            "br3":2,
            "br4":10,
            "br5":15,
            "tl1":24,
            "tl2":25,
            "tl3":13,
            "tl4":22,
            "tl5":23,
            "tr1":20,
            "tr2":8,
            "tr3":11,
            "tr4":21,
            "tr5":12,
            }
    
        controlled_multipoles = ["Ex","Ey","Ez","U1","U2","U3","U4","U5"]
        df = pd.read_csv(file,index_col = 0)
        voltages = pd.Series(np.zeros(len(pin_matching.keys())),index = df.index.values)
        # print("Multipoles:",dac_ms)
        for i,m in enumerate(v[20:]):
            voltages += df[controlled_multipoles[i]] * float(m)
        dac_vs = voltages.to_dict()
        for x in dac_vs.keys():
            prefix = 'new_ARTIQ_dataset_for_the_dashboard.electrode.'
            prefix2 = 'hidden_ARTIQ_dataset_after_calibrated_for_amplifier.'
            if x[0] == "E" or x[0] == "U":
                prefix = 'new_ARTIQ_dataset_for_the_dashboard.multipoles.'
            cmd = ["artiq_client",  "set-dataset", prefix+x, str(dac_vs[x]), '-p']
            subprocess.run(cmd)
            m = dac_cali[1][pin_matching[x]]
            b = dac_cali[0][pin_matching[x]]
            cmd = ["artiq_client",  "set-dataset", prefix2+x+'.v', str(dac_vs[x]), '-p']
            subprocess.run(cmd)
            cmd = ["artiq_client",  "set-dataset", prefix2+x+'.m', str(m), '-p']
            subprocess.run(cmd)
            cmd = ["artiq_client",  "set-dataset", prefix2+x+'.b', str(b), '-p']