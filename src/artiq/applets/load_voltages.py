from artiq.experiment import *
import subprocess
class setVoltage(EnvExperiment):
    def build(self):
        self.setattr_device('core')
        self.setattr_device('zotino0') 
        
        self.pin_matching = {
            'bl1':19,
            'bl2':18,
            'bl3':6,
            'bl4':1,
            'bl5':4,
            'br1':7,
            'br2':17,
            'br3':2,
            'br4':10,
            'br5':15,
            'tl1':24,
            'tl2':25,
            'tl3':13,
            'tl4':22,
            'tl5':23,
            'tr1':20,
            'tr2':8,
            'tr3':11,
            'tr4':21,
            'tr5':12,
            }
    def prepare(self):
        self.voltage_list = []
        print('here')
        for e in self.pin_matching.keys():
            self.voltage_list.append(self.get_dataset("new_ARTIQ_dataset_for_the_dashboard.electrode"+e))
        print('hello')

    @kernel
    def run(self):
        # self.core.reset()

        # self.zotino0.init()
        
        # self.zotino0.set_dac([self.target_voltage], [self.dac_channel])
        # self.zotino0.load()
        print(self.voltage_list)
    