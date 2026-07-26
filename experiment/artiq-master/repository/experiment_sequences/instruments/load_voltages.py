from artiq.experiment import *
class setVoltage(EnvExperiment):
    def build(self):
        self.setattr_device('core')
        self.setattr_device('zotino0') 
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
    def prepare(self):
        self.voltages = []
        self.ms = []
        self.bs = []
        for e in self.pin_matching.keys():
            self.voltages.append(float(self.get_dataset("hidden_ARTIQ_dataset_after_calibrated_for_amplifier."+e+".v")))
            self.ms.append(float(self.get_dataset("hidden_ARTIQ_dataset_after_calibrated_for_amplifier."+e+".m")))
            self.bs.append(float(self.get_dataset("hidden_ARTIQ_dataset_after_calibrated_for_amplifier."+e+".b")))
        #print(sevoltages)
        #self.mu_list = [self.zotino0.voltage_to_mu(v) for v in voltages] # IMPORTANT: need translate to machine unit before passing into kernel
        #print(self.mu_list)
        self.channel_list = [int(x) for x in self.pin_matching.values()]

    def run(self):
        self.kernel_run()
        
    @kernel
    def kernel_run(self):
        self.core.reset()
        for i in range(20):
            delay(500*us)
            self.zotino0.write_dac(self.channel_list[i],self.voltages[i]/self.ms[i])
            self.zotino0.write_offset(self.channel_list[i],-self.bs[i]/self.ms[i])
        self.zotino0.load()
    