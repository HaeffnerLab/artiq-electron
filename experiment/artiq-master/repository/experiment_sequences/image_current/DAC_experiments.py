from artiq.experiment import delay, us, BooleanValue, NumberValue, kernel, rpc, EnvExperiment
import pandas as pd
import numpy as np
from Config import Configuration


class DAC(Configuration):
    def build(self, load_config=True):
        self.setattr_device('core')
        self.setattr_device('zotino0')
        if load_config:
            Configuration.build(self)
        self.load_config = load_config
        self.build_DAC()
        
    def prepare(self):
        if self.load_config:
            Configuration.prepare(self)
        self.c_file_csv = self.DAC.cfile 
        self.offset_file_txt = self.DAC.calibration_file
    
    def build_DAC(self):
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

        # list of excess electrodes which is not included in the cfile, in this case it's the threshold voltage
        self.excess_e = []#["trigger_level"]
        
        # gnd pins
        self.gnd = [9,16,3,5,14] # gnd pins -> zotino channel
        # if or not use amplifier
        self.use_amplifier = True
        # max absolute voltage of the zotino channel
        self.max_voltage = 9.5
        self.controlled_multipoles = ["Ex","Ey","Ez","U1","U2","U3","U4","U5"]
        self.setattr_argument("multipole_control",BooleanValue(default = True), group='DC.multipoles')
        for e in self.pin_matching:
            self.setattr_argument(e, NumberValue(default = 0., ndecimals = 3, step = .001, unit = 'V'), group = "DC.electrodes", tooltip = "[V] | electrode voltage")

        for m in self.controlled_multipoles:
            self.setattr_argument(m, NumberValue(default = 0., ndecimals = 3, step = .001), group = "DC.multipoles", tooltip = "V/mm") 

    def run(self):
        # self.core.reset()
        self.load_DAC()

    def load_DAC(self):
        self.loadDACoffset()
        dac_pins, dac_pins_voltages = self.get_dac_vs()
        self.kernel_load_dac(dac_pins, dac_pins_voltages)

    def loadDACoffset(self):
        f = self.offset_file_txt 
        tmp = np.loadtxt(f)
        self.dac_calibration_fit = tmp 
        self.dac_manual_offset = np.zeros(32)
    
    @ kernel
    def kernel_load_dac(self,dac_pins, dac_pins_voltages):
        self.core.reset()
        self.core.break_realtime()
        self.zotino0.init()
        for i in range(len(dac_pins)):
            delay(500*us)
            m = self.dac_calibration_fit[1][dac_pins[i]]
            b = self.dac_calibration_fit[0][dac_pins[i]]
            self.zotino0.write_dac(dac_pins[i],(dac_pins_voltages[i]+b)/m - self.dac_manual_offset[dac_pins[i]])
        for pin in self.gnd:
            delay(500*us)
            self.zotino0.write_dac(pin,0.0)
            m = self.dac_calibration_fit[1][pin]
            b = self.dac_calibration_fit[0][pin]
            self.zotino0.write_offset(pin,-b/m)
        self.zotino0.load()
        # print("Loaded dac voltages")

    def get_dac_vs(self):
        dac_vs = {}
        dac_pins = []
        dac_pins_voltages = []

        if self.multipole_control:
            dac_vs = self.update_multipoles()
            # dac_vs["DC0"] += self.DC0_bias # with DC0 bias voltage
            # print(dac_vs)
        else:
            for e in self.pin_matching:
                dac_vs[e] = getattr(self,e)
        
        for e in dac_vs:
            dac_pins.append(self.pin_matching[e])
            dac_pins_voltages.append(dac_vs[e])
        
        self.set_DC_dataset(dac_vs)
        return dac_pins, dac_pins_voltages
    
    @rpc(flags={"async"})
    def set_DC_dataset(self,dac_vs):
        for e in dac_vs:
            self.set_dataset(key="main_sequence.e."+e, value=dac_vs[e], broadcast=True)
    
    @rpc(flags={"async"})
    def set_multipole_dataset(self,dac_ms):
        for m in dac_ms:
            self.set_dataset(key="main_sequence.multipole."+m, value=dac_ms[m], broadcast=True)

    def update_multipoles(self):
        
        # Create multiple list of floats
        dac_ms = {}
        for m in self.controlled_multipoles:
            dac_ms[m] = getattr(self,m)
        self.set_multipole_dataset(dac_ms)

        df = pd.read_csv(self.c_file_csv,index_col = 0)
        voltages = pd.Series(np.zeros(len(self.pin_matching.keys())-len(self.excess_e)),index = df.index.values)
        # print("Multipoles:",dac_ms)
        for m in self.controlled_multipoles:   
            voltages += df[m] * dac_ms[m]
        dac_vs = voltages.to_dict()
        for e in self.excess_e:
            dac_vs[e] = getattr(self,e)

        return dac_vs
        

class load_DAC(DAC, EnvExperiment):
    """
    Load DAC voltages
    """
    def build(self):
        return DAC.build(self)

    def prepare(self): 
        return DAC.prepare(self)
    
    def run(self): 
        DAC.run(self)





