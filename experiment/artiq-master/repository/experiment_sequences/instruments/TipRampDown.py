

import sys
import os
#import datetime import datetime
import select
from artiq.experiment import *
from artiq.coredevice.ad9910 import AD9910
from artiq.coredevice.ad53xx import AD53xx
import time
import numpy as np
from edes.experiments import Experiment
from edes.experiments.sequences import base as sequences
from edes.experiments.sequences import calibration as calibration_sequences

# from extraction_sequence import pulse_sequence
# import start_devices
# import load_DAC
# from load_DAC import DAC
import tqdm

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class TipRampDown(EnvExperiment):
    def build(self):
        self.setattr_argument('config_file', StringValue(default='3layer_trapping_072326'))
        # Expose calibration targets and thresholds to Dashboard
        self.setattr_argument("V_tip", NumberValue(default=0.0, unit="V"))
        self.setattr_argument('tip_channel', StringValue(default='neg'))

    def prepare(self):
        exp = Experiment(self.config_file)
        self.exp = exp
        
    def run(self):
        self.exp.FEtip_PSU.ramp_down_ch(self.tip_channel, 0)
