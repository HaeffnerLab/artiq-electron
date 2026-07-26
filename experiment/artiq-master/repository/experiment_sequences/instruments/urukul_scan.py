

import sys
import os
#import datetime import datetime
import select
from artiq.experiment import *
from artiq.coredevice.ad9910 import AD9910
from artiq.coredevice.ad53xx import AD53xx
import time
import numpy as np

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class Urukul_scan(EnvExperiment):
    def build(self):
         self.setattr_device('core')
        #  self.setattr_device('urukul0_ch1')
        #  self.setattr_device('dds_tickle')
         self.d0 = self.get_device("urukul0_ch0")
        #  self.d1 = self.get_device("urukul0_ch1")
        #  self.d2 = self.get_device("urukul0_ch2")
        #  self.d3 = self.get_device("urukul0_ch3")
         self.setattr_argument('att',NumberValue(default=10,unit='dB',scale=1,ndecimals=0,step=1)) #
         self.setattr_argument(
                     "driving_freq", 
                     Scannable(
                         default=RangeScan(start=150e6, stop=210e6, npoints=11),
                         unit="MHz",
                         scale=1e6
                     ),
                     group='Driving'
                 )
         self.setattr_argument('duration',NumberValue(default=5,unit='s',scale=1,ndecimals=0,step=1)) # 
         self.setattr_device('scheduler') # scheduler used

    def prepare(self):
        self.set_dataset('frequency',np.zeros(len([i for i in self.driving_freq])),broadcast=True)
        # print(self.duration)
        
    @kernel
    def kernel_set_freq(self, freq):
        self.core.reset()
        self.core.break_realtime()
        delay(50*ms)
        t = now_mu()
        self.d0.set(self.driving_freq.sequence[0], phase=0., ref_time_mu=t)

    @kernel
    def init_dds(self):
        self.core.reset()
        self.core.break_realtime()
        delay(50*ms)
        self.d0.cpld.init()
        self.d0.init()
        self.d0.set_att(self.att*dB)
        t = now_mu()
        self.d0.set(self.driving_freq.sequence[0], phase=0., ref_time_mu=t)
        self.d0.sw.on()

    @kernel 
    def turn_off_dds(self): 
        self.core.reset()
        self.core.break_realtime()
        delay(50*ms)
        self.d0.sw.off()

    def run(self):
        self.init_dds()
        i = 0
        for freq in self.driving_freq.sequence:
            self.kernel_set_freq(freq)
            self.mutate_dataset('frequency', i, freq)
            time.sleep(self.duration)
            i += 1

        
        self.turn_off_dds()

