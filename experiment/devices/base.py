import pyvisa as visa
from time import sleep
import matplotlib.pyplot as plt
import numpy as np
import importlib



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
    

class SiglentSPD3303X_E(Instrument): 
    def __init__(self, address): 
        super().__init__(address) 

    def select_channel(self, channel):
        self.write(f"INSTrument CH{channel}")

    def set_voltage(self, channel, voltage):
        self.select_channel(channel)
        self.write(f'VOLT {voltage}') 
    
    def set_current(self, channel, current):
        self.select_channel(channel)
        self.write(f'CURR {current}')

    def output_on(self, channel):   
        self.write(f"OUTPut CH{channel},ON")    
    
    def output_off(self, channel):  
        self.write(f"OUTPut CH{channel},OFF")
    
    def set_current_protection(self, max_current, channel): 
        self.write(f"LIMIT:CURRent {channel},{max_current}")

    def set_voltage_protection(self, max_voltage, channel): 
        self.write(f"LIMIT:VOLTage {channel},{max_voltage}")

    def measure_voltage(self, channel):
        self.select_channel(channel)
        response = self.query(f'MEAS:VOLT?')
        return float(response.strip()) 
        
    def measure_current(self, channel):
        self.select_channel(channel)
        response = self.query(f'MEAS:CURR?')
        return float(response.strip())  
    

class Valon(Instrument): 
    def __init__(self, address='ASRL/dev/ttyUSB1::INSTR'):
        spec = importlib.util.spec_from_file_location("device_lib", "/home/electron/Qcodes_contrib_drivers/src/qcodes_contrib_drivers/drivers/Valon/Valon_5015.py")
        device_lib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(device_lib)
        Valon5015 = device_lib.Valon5015
        self.valon = Valon5015(name="Valon", address=address)
        self.valon.frequency(1452e6)
        self.valon.offset(0)
        self.valon.power(0)
        self.valon.modulation_db(0)
        self.valon.modulation_frequency(1)
        self.valon.low_power_mode_enabled(True)
        self.valon.buffer_amplifiers_enabled(False)

    def output_on(self):
        self.valon.buffer_amplifiers_enabled(True)
    
    def output_off(self):
        self.valon.buffer_amplifiers_enabled(False) 
    
    def set_frequency(self, freq_hz):
        self.valon.frequency(freq_hz) 

    def set_power(self, power_dbm):
        self.valon.power(power_dbm) 
    
    def set_voltage(self, voltage): 
        self.set_power(10 * np.log10((voltage**2) / 100))  # Convert voltage to power assuming 50 ohm load

    def query(self, command):
        print(">>> Valon does not support query operations.")
        return

    def write(self, command):
        print(">>> Valon does not support write operations.")
        return
    
    def close(self):
        self.output_off()



class PS350_viaDP832A(Instrument): 
    def __init__(self, address, ch_ctrl=1, V_max=5000, V_offset=10): 
        self.rigol = RigolDP832A(address) 
        self.V_max = V_max 
        self.V_offset = V_offset
        self.ch_ctrl = ch_ctrl
        self.rigol.output_off(ch_ctrl)
        
    def set_voltage(self, V_desired): 
        self.rigol.set_voltage(self.ch_ctrl, max((V_desired-self.V_offset),0)/self.V_max*10)
        self.rigol.output_on(self.ch_ctrl)

    def output_off(self): 
        self.set_voltage(0)
        self.rigol.output_off(self.ch_ctrl)
