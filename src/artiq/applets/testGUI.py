#!/usr/bin/env python3
import load_button
import sys
from artiq.experiment import *
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit
from artiq.experiment import *
import subprocess

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
      self.setStyleSheet("background-color: #333333; color: #FFFFFF;")
      self.dataset_prefix = "optimize.e"
      self.attributes_list = ['bl1', 'bl2', 'bl3', 'bl4', 'bl5',
                              'br1', 'br2', 'br3', 'br4', 'br5',
                              'tl1', 'tl2', 'tl3', 'tl4', 'tl5',
                              'tr1', 'tr2', 'tr3', 'tr4', 'tr5', 'Ex', 'Ey', 'Ez']
      self.value_labels = {}
      for i, attr in enumerate(self.attributes_list):
            name_label = QLabel(f"{attr}:")
            name_label.setStyleSheet("font-weight: bold; font-size: 14px")

            val_label = QLineEdit("Fetching from Master DB...")
            val_label.setStyleSheet("font-size: 14px; font-family: monospace;")

            widget = QWidget()
            combined = QHBoxLayout()
            combined.setSpacing(15)
            combined.addWidget(name_label)
            combined.addWidget(val_label)
            widget.setLayout(combined)

            layout.addWidget(widget, i%5, i//5)
            self.value_labels[attr] = val_label

      load_daq_button = QPushButton("Load DAQ")
      layout.addWidget(load_daq_button, 4,4)
      load_daq_button.clicked.connect(self.load_daq)
      self.horizontalGroupBox.setLayout(layout)


  def load_daq(self):
    input = str([x.text() for x in list(self.value_labels.values())])
    cmd = ["artiq_client",  "set-dataset", "voltages", f"\"{input}\""]
    process = subprocess.run(cmd)
    print(process.CompletedProcess)
    print("voltages loaded")

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    for attr in ex.attributes_list:
        ex.value_labels[attr].setText("0.0")
    ex.show()
    sys.exit(app.exec_())