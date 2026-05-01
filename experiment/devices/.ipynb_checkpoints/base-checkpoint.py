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