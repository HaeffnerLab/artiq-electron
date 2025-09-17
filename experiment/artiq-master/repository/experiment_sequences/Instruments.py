import vxi11
import numpy as np
import pyvisa as visa 
from artiq.language.core import rpc
from artiq.language.types import TFloat
# import time 
# from time import sleep 
# from qcodes_contrib_drivers.drivers.Valon.Valon_5015 import Valon5015

class rigol():
    def __init__(self,ip=104,pulse_width_ej=800.E-9, pulse_delay_ej=2.E-9,offset_ej=0,amplitude_ej=-20,phase=0,period_ej=1000.E-9,sampling_time=2.E-9):
        # self.sampling_time = sampling_time # 
        
        # initial phase != 0, voltage 0 ~ -20 V, need to manually adjust and see on the scope or AWG
        self.pulse_width_ej = pulse_width_ej
        self.pulse_delay_ej = pulse_delay_ej
        self.offset_ej = offset_ej
        self.amplitude_ej = amplitude_ej
        self.phase = phase
        self.period_ej = period_ej
        self.sampling_time = sampling_time
        self.inst = vxi11.Instrument('TCPIP0::192.168.169.'+str(ip)+'::INSTR')
        
       

    def run(self):
        inst = self.inst
        inst.write("OUTPUT2 OFF")
        inst.write("OUTPUT1 OFF")   
        # hardcode sampling rate for ejection pulse, since only need the first few hundred ns
        
        # ###### use channel one to extrac on the bottom two central electrodes
        # waveform_ej = np.zeros(int(self.period_ej/self.sampling_time))
        waveform_ej = np.zeros(500)
        waveform_ej[:] = -1
        waveform_ej[np.int32(self.pulse_delay_ej/self.sampling_time):np.int32((self.pulse_delay_ej+self.pulse_width_ej)/self.sampling_time)] = 1
        ej_str = ",".join(map(str,waveform_ej))
        # Channel 1
        inst.write(":OUTPut1:LOAD INFinity")
        inst.write("SOURCE1:PERIOD {:.9f}".format(self.period_ej))
        # print(inst.ask("SOURCE2:PERIOD?"))
        inst.write("SOURCE1:VOLTage:UNIT VPP")
        inst.write("SOURCE1:VOLTage {:.3f}".format(self.amplitude_ej))
        inst.write("SOURCE1:VOLTage:OFFSet {:.3f}".format(self.offset_ej))
        inst.write("SOURCE1:TRACE:DATA VOLATILE,"+ ej_str)
        # inst.write("SOURCE2:PHASe 20")
        
        inst.write("SOURce1:BURSt ON")

        # inst.write("SOURce2:BURSt:INTernal:PERiod {:.9f}".format(period_burst))

        # inst.write("SOURce1:BURSt:GATE:POL NORMal")

        # inst.write("SOURce1:BURSt:PHASe {:.3f}".format(self.phase))


        inst.write("SOURce1:BURSt:MODE TRIGgered")
        inst.write("SOURce1:BURSt:NCYCles 1")
        # inst.write("SOURce2:BURSt:TDELay {:f}".format(self.delay))
        inst.write("SOURCe1:BURSt:TRIGger:SOURce EXTernal")
        inst.write("SOURce1:BURSt:TRIGger:SLOPe POSitive")


        inst.write("OUTPUT1 ON")
        # inst.write("OUTPUT2 ON")
        return

class RS():
    def __init__(self, sampling_time=0):
        self.inst = vxi11.Instrument('TCPIP::192.168.169.101::INSTR')
        print(self.inst.ask('*IDN?'))

    def run(self, freq, power):
        self.freq = freq
        self.power = power
        inst = self.inst
        # inst.write("OUTPut OFF")
        # Channel 1
        # print(inst.ask(":OUTPut:IMPedance?"))
        inst.write("SOURce:FREQuency: MODE CW")
        inst.write("SOURce:FREQuency {:.9f}".format(self.freq))
        inst.write("SOURce:POWer:POWer {:.3f}".format(self.power))
        inst.write('SOURce:MOD:ALL:STAT ON')
        inst.write("OUTPut ON")
        #print(inst.ask("OUTPUT?"))
        return 

    # def stop(self):
    #     inst = self.inst
    #     inst.write('OUTPut OFF')
    #     inst.write('SOURce:MOD:ALL:STAT OFF')




'''
rs = RS()
frequencies = np.arange(66, 77, 0.1) * 1E6
amp_trapfreq = -20.0
U2 = -0.7
Prf = +2.5
load_time = 200 E-6
wait_time = 4000E-6
for freq_trapfreq in frequencies:
    rs.run(freq_trapfreq,amp_trapfreq)
'''

class SSA3032X_R: 
    def __init__(self, ip='TCPIP::192.168.1.101::INSTR', N_AVG=100, data_trace=3):
        rm = visa.ResourceManager()
        self.SSA = rm.open_resource(ip)
        self.N_AVG = N_AVG
        self.SSA.write(f":AVERage:TRACe{data_trace}:COUNt {N_AVG}")
        self.data_trace = data_trace
        print('>>> Initialized SSA 3032X-R')#, self.SSA.query("*IDN?"))
    
    def set_N_AVG(self, N):
        self.N_AVG = N 
        self.SSA.write(f":AVERage:TRACe{self.data_trace}:COUNt {N}")
        print(f'>>> Set N_AVG to {N}')

    @rpc(flags={"async"})
    def reset_avg(self, trace=0): 
        self.SSA.write(f":AVERage:TRAC{trace}:CLEar")

    # @rpc(flags={"async"})
    def get_data(self, trace=0):
        trace = self.data_trace if trace ==0 else trace
        # self.SSA.write(f":AVERage:TRAC{trace}:CLEar")
        # while int(self.SSA.query(f":AVERage:TRACe{trace}?")) < self.N_AVG: 
        #     continue

        data_str_C = self.SSA.query(f":TRACe{trace}:DATA?")
        return np.array([float(val) for val in data_str_C.split(',')])
    
    # @rpc(flags={"async"})
    def get_tot_power_nW(self, trace=0) -> TFloat: 
        trace = self.data_trace if trace ==0 else trace
        # self.SSA.write(f":AVERage:TRAC{trace}:CLEar")
        # while int(self.SSA.query(f":AVERage:TRACe{trace}?")) < self.N_AVG: 
        #     continue
        data_str_C = self.SSA.query(f":TRACe{trace}:DATA?")
        data_dBm = np.array([float(val) for val in data_str_C.split(',')])
        # data_dBm = self.get_data(trace) 
        data_mW = sum(10**(data_dBm/10))
        return float(data_mW)*1e6 

    

class Valon: 
    def __init__(self, ip='ASRL/dev/ttyUSB0::INSTR', freq=1452e6, power=0): 
        valon = Valon5015(name="Valon", address=ip)
        valon.frequency(freq)
        valon.offset(0)
        valon.power(power)
        valon.modulation_db(0)
        valon.modulation_frequency(1)
        valon.low_power_mode_enabled(True)
        valon.buffer_amplifiers_enabled(True)
        status = valon.status()
        self.valon = valon
        print(status)

    def set_freq(self, freq):
        self.valon.frequency(freq)

    def set_power(self, power):
        self.valon.power(power)
    
    def turn_on(self):
        self.valon.buffer_amplifiers_enabled(True)

    def turn_off(self):
        self.valon.buffer_amplifiers_enabled(False)
        #self.valon.low_power_mode_enabled(False) # ignored for now since unsure about the locking issues