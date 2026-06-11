#!/usr/bin/env python3
import load_button
import sys
from artiq.experiment import *
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QFileDialog
from artiq.experiment import *
import subprocess
import pandas as pd
import numpy as np
from PyQt5.QtGui import QPixmap

class App(QDialog):
  def __init__(self):
          super().__init__()
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
      
      self.setStyleSheet("background-color: #B31942; color: #FFFFFF;")
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
            val_label.setFixedSize(50, 20)
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
            val_label.setFixedSize(50, 20)
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
      
      load_c_file = QPushButton("Choose C File")
      load_c_file.clicked.connect(self.choose_your_c_file_now_if_you_want)
      layout.addWidget(load_c_file, 3,4)

      self.horizontalGroupBox.setLayout(layout)
  def choose_your_c_file_now_if_you_want(self):
      self.file = QFileDialog.getOpenFileName()[0]

  def load_dac(self):
    if any(list(self.value_labels.values())[20:]):
        self.update_multipoles()
    else:
        for x in self.value_labels.keys():
            prefix = 'new_ARTIQ_dataset_for_the_dashboard.electrode.'
            if x[0] == "E" or x[0] == "U":
                prefix = 'new_ARTIQ_dataset_for_the_dashboard.multipoles.'
            cmd = ["artiq_client",  "set-dataset", prefix+x, self.value_labels[x].text()]
            subprocess.run(cmd)
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
            if x[0] == "E" or x[0] == "U":
                prefix = 'new_ARTIQ_dataset_for_the_dashboard.multipoles.'
            cmd = ["artiq_client",  "set-dataset", prefix+x, str(dac_vs[x])]
            self.value_labels[x].setText(str(dac_vs[x]))
            self.value_labels[x].setCursorPosition(0)
            subprocess.run(cmd)
        for x in self.controlled_multipoles:
            prefix = 'new_ARTIQ_dataset_for_the_dashboard.multipoles.'
            cmd = ["artiq_client",  "set-dataset", prefix+x, self.value_labels[x].text()]
            subprocess.run(cmd)
        print("voltages loaded")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    for attr in ex.attributes_list:
        ex.value_labels[attr].setText("0.0")
    ex.show()
    sys.exit(app.exec_())