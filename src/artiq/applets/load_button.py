from artiq.experiment import *


class loadVoltages(HasEnvironment):
    def build(self):
        self.setattr_device('core')
        self.setattr_device('zotino0')
        self.setattr_argument("voltages", StringValue())
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

    def run(self):
        self.core.reset()
        self.load_DAC()

    def load_DAC(self):
        voltage_list = [float(x) for x in self.voltages.split('')]
        print(voltage_list)
        self.core.reset()
        self.load_DAC()
        self.zotino0.set_dac(voltage_list, self.pin_matching.values().list())

class load_DAC(loadVoltages, EnvExperiment):
    def build(self):
        return loadVoltages.build(self)

    def run(self):
        loadVoltages.run(self)