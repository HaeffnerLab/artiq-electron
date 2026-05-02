# from edes.modules.devices.base import RigolDP832A

import sys
import os
#import datetime import datetime
import select
from artiq.experiment import *
import time
import numpy as np


import time  # We need this for host-side timing
from artiq.experiment import *
from artiq.experiment import delay, kernel
from artiq.experiment import ms, s
from artiq.experiment import BooleanValue, NumberValue, TFloat

import pyvisa as visa
from time import sleep
import matplotlib.pyplot as plt
import numpy as np
import importlib
spec = importlib.util.spec_from_file_location("device_lib", "/home/electron/artiq/experiment/devices/base.py")
device_lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device_lib)
Valon5015 = device_lib.Valon


    
class ValonTesting(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("sampler0")
        self.setattr_device("scheduler")
        
        self.setattr_argument("save_data", BooleanValue(default=False), group="Data Saving")
        self.setattr_argument("time_interval", NumberValue(default=1, unit='s', scale=1, ndecimals=1, step=0.1), group="Data Saving")
        

    def prepare(self):
        self.Valon = Valon5015(address='ASRL/dev/ttyUSB1::INSTR')
        self.set_dataset("current_temperature", 0.0, broadcast=True, archive=False)
        
        if self.save_data:
            self.set_dataset("temperature_history", [], broadcast=True, archive=True)
            self.set_dataset("time_history", [], broadcast=True, archive=True) 

    # Removed the @rpc decorator. Since our loop is now on the Host, 
    # we don't need RPCs to talk to the datasets!
    def update_datasets(self, temp: float, elapsed_time: float):
        display_temp = round(temp, 2)
        self.set_dataset("current_temperature", display_temp, broadcast=True, archive=False)
        
        if self.save_data:
            self.append_to_dataset("temperature_history", temp)
            self.append_to_dataset("time_history", elapsed_time) 

    @kernel
    def measure_single_point(self) -> TFloat:
        """
        Dips into the FPGA just long enough to take one reading.
        """
        # Very important: Reset the core every time we enter! 
        # If a priority 0 experiment just finished running, it might have left 
        # the FPGA timeline far in the future. This syncs us back up.
        self.core.reset()
        self.sampler0.init()
        delay(1 * ms)
        
        smp = [0.0] * 8
        self.sampler0.sample(smp)
        
        return smp[0]

    # Notice: 'run' DOES NOT have @kernel anymore! 
    # This runs purely on the standard Python Host PC.
    def run(self):
        start_time = time.time()
        self.Valon.set_power(0)
        self.Valon.output_on()
        frequency_steps = np.linspace(-50, 50, 50)*1e6 + 1452e6
        for f in frequency_steps:
            # 1. Mark exactly when this specific loop started
            loop_start = time.time() 
            
            # 2. Get the data
            self.Valon.set_frequency(f)
            temp = self.measure_single_point()
            
            # Use loop_start so the timestamp matches exactly when we asked for the data
            # current_time = loop_start - start_time 
            self.update_datasets(temp, f/1e9)
            
            # 3. Check for pauses
            if self.scheduler.check_pause():
                self.scheduler.pause() 
            
            # 4. Calculate dynamic sleep time
            # How long did the measurement, GUI updates, and potential pausing take?
            time_taken = time.time() - loop_start
            sleep_time = self.time_interval - time_taken
            
            # Only sleep if we haven't already burned through our interval time
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.Valon.output_off()