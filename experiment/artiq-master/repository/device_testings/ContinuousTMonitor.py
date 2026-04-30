

import sys
import os
#import datetime import datetime
import select
from artiq.experiment import *
import time
import numpy as np


class ContinuousTemperatureMonitor(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("sampler0")
        
        # We define a single variable dataset, not a massive array.
        self.set_dataset("current_temperature", 0.0, broadcast=True)

    @kernel
    def run(self):
        self.core.reset()
        self.sampler0.init()
        delay(1 * ms)
        
        smp = [0.0] * 8
        
        # The Infinite Loop
        while True:
            # 1. Read the hardware
            self.sampler0.sample(smp)
            temp = smp[0] / 0.01 
            
            # 2. Send the data to the Host PC (RPC)
            self.set_dataset("current_temperature", temp)
            
            # 3. Yield to the Scheduler (RPC)
            # This checks if you have submitted another experiment (like a laser pulse sequence).
            # If yes, this monitor pauses, the other experiment runs, and then this monitor resumes.
            self.scheduler.pause()
            
            # 4. Advance the timeline and wait before the next reading (e.g., 1 second)
            delay(1 * s)

