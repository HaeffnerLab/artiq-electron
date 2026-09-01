from artiq.experiment import *
import numpy as np
from Config import Configuration

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class SpectrumAnalyzer(Configuration):
    """
    A code to use spectrum analyzer in the code
    """

    def build(self, load_config=False):
        if load_config:
            Configuration.build(self)
        self.setattr_argument('SSA_mode', StringValue(default='SA'), group="Spectrum Analyzer")
        self.setattr_argument('SSA_freq_center',NumberValue(default=175.95e6,unit='Hz',scale=1,ndecimals=6,step=1), group="Spectrum Analyzer") # frequency center
        self.setattr_argument('SSA_freq_span',NumberValue(default=0,unit='Hz',scale=1,ndecimals=6,step=1), group="Spectrum Analyzer") # frequency span
        self.setattr_argument('SSA_SWT',NumberValue(default=100e-3,unit='s',scale=1,ndecimals=3,step=1), group="Spectrum Analyzer") # sweep time
        self.setattr_argument('SSA_RBW',NumberValue(default=1e3,unit='Hz',scale=1,ndecimals=6,step=1), group="Spectrum Analyzer") # resolution bandwidth
        self.setattr_argument('SSA_VBW',NumberValue(default=1e3,unit='Hz',scale=1,ndecimals=6,step=1), group="Spectrum Analyzer") # video bandwidth
        self.load_config = load_config

    def prepare(self):
        if self.load_config:
            Configuration.prepare(self)
        self.SSA.select_mode(self.SSA_mode)
        self.SSA.re_init(self.SSA_freq_center, self.SSA_freq_span, self.SSA_RBW, self.SSA_SWT, self.SSA_VBW)

        
class SASweep(SpectrumAnalyzer, EnvExperiment):
    """
    Run single SA sweep
    """
    def build(self):
        return SpectrumAnalyzer.build(self, load_config=True)

    def prepare(self):
        return SpectrumAnalyzer.prepare(self)
    
    def run(self):
        self.SSA.select_mode(self.SSA_mode)
        self.SSA.re_init(self.SSA_freq_center, self.SSA_freq_span, self.SSA_RBW, self.SSA_SWT, self.SSA_VBW)
        data = self.SSA.get_full_trace()
        self.set_dataset('SSA_power', np.array(data), broadcast=True)
