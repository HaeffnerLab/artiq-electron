

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

class ADC_Monitors(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("sampler0")
        self.setattr_device("scheduler")
        self.set_default_scheduling(priority=-10)
        
        self.setattr_argument("time_interval", NumberValue(default=1, unit='s', scale=1, ndecimals=1, step=0.1))
        self.setattr_argument("displaying_digits", NumberValue(default=2, scale=1, ndecimals=0, step=1))
        
        # --- Channel Enable Flags ---
        # Enable channels 0 and 1 by default
        for i in range(2):
            self.setattr_argument(f"enable_channel_{i}", BooleanValue(default=True), group="Channels")
        # Channels 2-7 remain disabled by default
        for i in range(2, 8):
            self.setattr_argument(f"enable_channel_{i}", BooleanValue(default=False), group="Channels")
            
        # --- Channel Names ---
        # Specific names for channels 0 and 1
        self.setattr_argument("channel_0_name", StringValue(default="RF Reflection"), group="Channel_names")
        self.setattr_argument("channel_1_name", StringValue(default="RF Transmission"), group="Channel_names")
        # Generic names for channels 2-7
        for i in range(2, 8):
            self.setattr_argument(f"channel_{i}_name", StringValue(default=f"ADC Channel {i}"), group="Channel_names")
            
        # --- Data Saving ---
        for i in range(8):
            self.setattr_argument(f"save_channel_{i}_data", BooleanValue(default=False), group="Data Saving")
        

    def prepare(self):
        self.displaying_digits = int(self.displaying_digits)
        for i in range(8):
            if getattr(self, f"enable_channel_{i}"):
                self.set_dataset(f"current_channel_{i}_value", 0.0, broadcast=True, archive=False)
                if getattr(self, f"save_channel_{i}_data"):
                    self.set_dataset(f"channel_{i}_history", [], broadcast=True, archive=True)
                self.set_dataset(f"ADC_channel_{i}_name", getattr(self, f"channel_{i}_name"), broadcast=True, archive=False)
            

    # Removed the @rpc decorator. Since our loop is now on the Host, 
    # we don't need RPCs to talk to the datasets!
    def update_datasets(self, smp, elapsed_time: float):
        
        for i in range(8):
            if getattr(self, f"enable_channel_{i}"):
                channel_value = smp[i]
                display_value = round(channel_value, int(self.displaying_digits))
                self.set_dataset(f"current_channel_{i}_value", display_value, broadcast=True, archive=False)
                if getattr(self, f"save_channel_{i}_data"):
                    self.append_to_dataset(f"channel_{i}_history", channel_value)

    @kernel
    def measure_single_point_fast(self, smp_array: TArray(TFloat, 1)):
        """
        Dips into the FPGA just long enough to take one reading.
        """
        # Very important: Reset the core every time we enter! 
        # If a priority 0 experiment just finished running, it might have left 
        # the FPGA timeline far in the future. This syncs us back up.
        self.core.reset()
        self.sampler0.init()
        delay(1 * ms)
        
        # smp = [0.0] * 8
        self.sampler0.sample(smp_array)
        
        return smp_array

    # Notice: 'run' DOES NOT have @kernel anymore! 
    # This runs purely on the standard Python Host PC.
    def run(self):
        start_time = time.time()
        smp_array = np.zeros(8, dtype=float)  # Pre-allocate a numpy array for the FPGA to fill
        while True:
            # 1. Mark exactly when this specific loop started
            loop_start = time.time() 
            
            # 2. Get the data
            smp_array=self.measure_single_point_fast(smp_array)
            
            # Use loop_start so the timestamp matches exactly when we asked for the data
            current_time = loop_start - start_time 
            self.update_datasets(smp_array, current_time)
            
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