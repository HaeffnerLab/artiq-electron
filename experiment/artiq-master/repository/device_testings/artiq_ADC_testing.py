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



class Instrument: 
    def __init__(self, address):
        self.rm = visa.ResourceManager()
        self.instrument = self.rm.open_resource(address)
        self.instrument.timeout = 2000 # 2 seconds

    def query(self, command):
        return self.instrument.query(command)

    def write(self, command):
        self.instrument.write(command)
    
    def close(self):
        self.instrument.close() 

class RigolDP832A(Instrument):
    def __init__(self, address):
        super().__init__(address)
        idn_response = self.query('*IDN?')
        if 'RIGOL' in idn_response.upper() and 'DP832A' in idn_response.upper():
            print(f"Rigol DP832A found: {idn_response.strip()}")
        else:
            raise Exception("Connected instrument is not a Rigol DP832A.")
    
    def select_channel(self, channel):
        self.write(f"INST:NSEL {channel}")

    def set_voltage(self, channel, voltage):
        self.select_channel(channel)
        self.write(f'VOLT {voltage}') 
    
    def set_current(self, channel, current):
        self.select_channel(channel)
        self.write(f'CURR {current}')

    def output_on(self, channel):   
        self.select_channel(channel)
        self.write(f'OUTP ON')    
    
    def output_off(self, channel):  
        self.select_channel(channel)
        self.write(f'OUTP OFF')  
    
    def measure_voltage(self, channel):
        self.select_channel(channel)
        response = self.query(f'MEAS:VOLT?')
        return float(response.strip())
    
    def measure_current(self, channel):
        self.select_channel(channel)
        response = self.query(f'MEAS:CURR?')
        return float(response.strip())  
    
class ADCTesting(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("sampler0")
        self.setattr_device("scheduler")
        self.set_default_scheduling(priority=-10)
        
        self.setattr_argument("save_data", BooleanValue(default=False), group="Data Saving")
        self.setattr_argument("time_interval", NumberValue(default=1, unit='s', scale=1, ndecimals=1, step=0.1), group="Data Saving")
        self.PSU = RigolDP832A('USB0::6833::3601::DP8B260200018::0::INSTR')

    def prepare(self):
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
        self.PSU.set_voltage(3, 0)  # Start at 0V 
        self.PSU.output_on(3)
        voltage_steps = np.linspace(0, 5, 20)
        for v in voltage_steps:
            # 1. Mark exactly when this specific loop started
            loop_start = time.time() 
            
            # 2. Get the data
            self.PSU.set_voltage(3, v)
            temp = self.measure_single_point()
            
            # Use loop_start so the timestamp matches exactly when we asked for the data
            # current_time = loop_start - start_time 
            self.update_datasets(temp, v)
            
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