#!/usr/bin/env python3
import sys
from PyQt5.QtWidgets import (
    QApplication,
    QWidget, QLabel, QLineEdit,
    QVBoxLayout, QHBoxLayout, QPushButton, QFormLayout
)
from PyQt5.QtCore import Qt
from artiq.applets.simple import TitleApplet
import pyvisa as visa
from time import sleep
import sys

    


def ramp_mcp_voltage(TODO, V1=2400, V2=2200, V3=200, sleeptime=0.5, print_log=False): 
    rm = visa.ResourceManager()
    instruments = rm.list_resources()
    # instruments
    usb = list(filter(lambda x: ('USB' in x and 'ASRL' not in x), instruments))
    if len(usb) != 1:
        print('Bad instrument list', instruments)
        sys.exit(-1)
    odp = rm.open_resource(usb[0])
    odp.write("INST:NSEL 1")
    odp.write("VOLT:PROT 10.1")
    odp.write("CURR:PROT 0.001")
    odp.write("OUTP ON")

    odp.write("INST:NSEL 2")
    odp.write("VOLT:PROT 10.1")
    odp.write("CURR:PROT 0.001")
    odp.write("OUTP ON")

    odp.write("INST:NSEL 3")
    odp.write("VOLT:PROT 5")
    odp.write("CURR:PROT 0.001")
    odp.write("OUTP ON")

    Vstep01 = 5*50/5000
    Vstep02 = 5*50/2500 * 1.8
    Vstep03 = 5*50/2500
    V1g0 = 10*V1/5000
    V2g0 = 10*V2/2500
    V3g0 = 10*V3/1250

    ON = "Turn on"
    OFF = "Turn off"

    if TODO == ON:
        odp.write("INST:NSEL 1")
        vinit1 = float(odp.query("MEAS:VOLT?"))
        sleep(0.1)
        odp.write("INST:NSEL 2")
        vinit2 = float(odp.query("MEAS:VOLT?"))
        sleep(0.1)
        odp.write("INST:NSEL 3")
        vinit3 = float(odp.query("MEAS:VOLT?"))
        while 1:
            odp.write("INST:NSEL 1")
            vcurr1 = float(odp.query("MEAS:VOLT?"))
            sleep(0.2)
            odp.write("INST:NSEL 2")
            vcurr2 = float(odp.query("MEAS:VOLT?"))
            sleep(0.2)
            odp.write("INST:NSEL 3")
            vcurr3 = float(odp.query("MEAS:VOLT?"))
            sleep(0.2)
            if vcurr1 > V1g0+0.1:
                if vcurr2 > V2g0+0.1:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2-Vstep02))
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2-Vstep02))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2-Vstep02))
                        sleep(sleeptime)
                elif vcurr2 < V2g0-0.1:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2+Vstep02))
                        sleep(sleeptime)
                else:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        sleep(sleeptime)
            elif vcurr1 < V1g0-0.1:
                if vcurr2 > V2g0+0.1:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2-Vstep02))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2-Vstep02))
                        sleep(sleeptime)
                elif vcurr2 < V2g0-0.1:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        sleep(sleeptime)
                else:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1+Vstep01))
                        sleep(sleeptime)       
            else:
                if vcurr2 > V2g0+0.1:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2-Vstep02))
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2-Vstep02))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 2")
                        odp.write("VOLT "+str(vcurr2-Vstep02))
                        sleep(sleeptime)
                elif vcurr2 < V2g0-0.1:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 < (vcurr1*5000/10-50):
                            odp.write("VOLT "+str(vcurr2+Vstep02))
                        sleep(sleeptime)
                else:
                    if vcurr3 > V3g0+0.1:
                        odp.write("INST:NSEL 3")
                        odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    elif vcurr3 < V3g0-0.1:
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250 < vcurr2*2500:
                            odp.write("VOLT "+str(vcurr3+Vstep03))
                        sleep(sleeptime)
                    else:
                        break
            if print_log: 
                print(vcurr1, vcurr2, vcurr3)
        odp.write("INST:NSEL 1")
        odp.write("VOLT "+str(V1g0))
        odp.write("INST:NSEL 2")
        odp.write("VOLT "+str(V2g0))
        odp.write("INST:NSEL 3")
        odp.write("VOLT "+str(V3g0))
        print("Finish")
        if print_log: 
            print(vcurr1, vcurr2, vcurr3)

    elif TODO == OFF:
        sleeptime = 0.5
        odp.write("INST:NSEL 1")
        vinit1 = float(odp.query("MEAS:VOLT?"))
        sleep(0.1)
        odp.write("INST:NSEL 2")
        vinit2 = float(odp.query("MEAS:VOLT?"))
        sleep(0.1)
        odp.write("INST:NSEL 3")
        vinit3 = float(odp.query("MEAS:VOLT?"))
        while 1:
            odp.write("INST:NSEL 1")
            vcurr1 = float(odp.query("MEAS:VOLT?"))
            sleep(0.1)
            odp.write("INST:NSEL 2")
            vcurr2 = float(odp.query("MEAS:VOLT?"))
            odp.write("INST:NSEL 3")
            vcurr3 = float(odp.query("MEAS:VOLT?"))
            sleep(0.1)
            if vcurr1 > 0.11:
                if vcurr2 > 0.11:
                    if vcurr3 > 0.11:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 > (vcurr1*5000/10-200):
                            odp.write("VOLT "+str(vcurr2-Vstep02))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250/10 > (vcurr2*2500/10-200):
                            odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 > (vcurr1*5000/10-200):
                            odp.write("VOLT "+str(vcurr2-Vstep02))
                        sleep(sleeptime)                    
                else:
                    if vcurr3 > 0.11:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250/10 > (vcurr2*2500/10-200):
                            odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 1")
                        odp.write("VOLT "+str(vcurr1-Vstep01))
                        sleep(sleeptime)                    
                    
            else:
                if vcurr2 > 0.11:
                    if vcurr3 > 0.11:
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 > (vcurr1*5000/10-200):
                            odp.write("VOLT "+str(vcurr2-Vstep02))
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250/10 > (vcurr2*2500/10-200):
                            odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    else:
                        odp.write("INST:NSEL 2")
                        if vcurr2*2500/10 > (vcurr1*5000/10-200):
                            odp.write("VOLT "+str(vcurr2-Vstep02))
                        sleep(sleeptime)                    
                else:
                    if vcurr3 > 0.11:
                        odp.write("INST:NSEL 3")
                        if vcurr3*1250/10 > (vcurr2*2500/10-200):
                            odp.write("VOLT "+str(vcurr3-Vstep03))
                        sleep(sleeptime)
                    else:
                        break
            if print_log:        
                print(vcurr1, vcurr2, vcurr3)
        odp.write("INST:NSEL 1")
        odp.write("VOLT 0.01")
        odp.write("INST:NSEL 2")
        odp.write("VOLT 0.01")                    
        odp.write("INST:NSEL 3")
        odp.write("VOLT 0.01")                    
        
        
    else:
        print("Check your spelling.")


class VoltageControlApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("MCP Voltage Control")

        # Create form layout for labels and line edits
        form_layout = QFormLayout()

        self.inputs = {}
        labels = ["V1", "V2", "V3", "V1 offset", "V2 offset", "V3 offset", "sleeptime"]
        defaults = ["2400", "2200", "200", "-9", "3", "0", "2"]

        for label, default in zip(labels, defaults):
            edit = QLineEdit()
            edit.setText(default)
            self.inputs[label] = edit
            form_layout.addRow(QLabel(label), edit)

        # Buttons
        btn_on = QPushButton("ON")
        btn_off = QPushButton("OFF")

        btn_on.clicked.connect(lambda: self.run_voltage_ramp("Turn on"))
        btn_off.clicked.connect(lambda: self.run_voltage_ramp("Turn off"))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_on)
        btn_layout.addWidget(btn_off)

        # Overall layout
        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def run_voltage_ramp(self, action):
        # Read and compute parameters
        V1 = float(self.inputs["V1"].text())
        V2 = float(self.inputs["V2"].text())
        V3 = float(self.inputs["V3"].text())
        V1_off = float(self.inputs["V1 offset"].text())
        V2_off = float(self.inputs["V2 offset"].text())
        V3_off = float(self.inputs["V3 offset"].text())
        sleeptime = float(self.inputs["sleeptime"].text())

        final_V1 = V1 + V1_off
        final_V2 = V2 + V2_off
        final_V3 = V3 + V3_off

        # Directly call the ramp function (this will block the GUI)
        ramp_mcp_voltage(
            action,
            V1=final_V1,
            V2=final_V2,
            V3=final_V3,
            sleeptime=sleeptime
        )
    
    def data_changed(self, data, mods, title):
        self.plotWidget.data_changed(data, mods, title)


def main():
    app = QApplication(sys.argv)
    window = VoltageControlApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
