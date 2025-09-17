

import sys
import os
#import datetime import datetime
import select
from artiq.experiment import *
from artiq.coredevice.ad9910 import AD9910
from artiq.coredevice.ad53xx import AD53xx
import time
import numpy as np

from extraction_sequence import pulse_sequence
import start_devices
import load_DAC
from load_DAC import DAC
import artiq
from Instruments import SSA3032X_R

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class ROI_count_with_driving(DAC, pulse_sequence, EnvExperiment):

    def build(self):
        DAC.build(self)
        pulse_sequence.build(self)
        start_devices.Devices.build(self)

        self.setattr_device("ccb")
        # self.setattr_argument("output_pulse", BooleanValue(default = True), group = "Main sequence")
        self.setattr_argument('number_of_datapoints', NumberValue(default=5000,unit=' ',scale=1,ndecimals=0,step=1)) #how many data points on the plot, run experiment & pulse counting
        self.setattr_argument('number_of_warmup_points',NumberValue(default=100,scale=1,ndecimals=0,step=1))
        self.setattr_argument('att',NumberValue(default=20,unit='dB',scale=1,ndecimals=0,step=1)) #
        self.setattr_argument('freq_drive',NumberValue(default=290,unit='MHz',scale=1,ndecimals=0,step=1)) # driving freq
        self.setattr_argument('t_load',NumberValue(default=100,unit='us',scale=1,ndecimals=0,step=1)) # load time
        self.setattr_argument('t_wait',NumberValue(default=100,unit='us',scale=1,ndecimals=0,step=1)) # wait time
        self.setattr_argument('t_initial_delay',NumberValue(default=30,unit='s',scale=1,ndecimals=0,step=1)) # delay time at the beginning of the experiment
        self.dds_tickle = self.get_device("urukul0_ch0")
        self.setattr_argument("continuous_loading", BooleanValue(default=False))
        self.setattr_argument("apply_extraction", BooleanValue(default=True))
        self.setattr_argument("apply_driving", BooleanValue(default=True))
        self.setattr_argument("use_external_driving", BooleanValue(default=False))
        self.setattr_argument("N_SA_avg", NumberValue(default=100,scale=1,ndecimals=0,step=1))
        self.setattr_argument("SSA_data_trace", NumberValue(default=3,scale=1,ndecimals=0,step=1))
        self.setattr_argument("SSA_IP_addr", StringValue(default=f'TCPIP::192.168.1.101::INSTR'))
        # self.setattr_argument("SSA_flag_on_counts", BooleanValue(default=False))
        self.setattr_device("ttl12")

    def prepare(self):
        pulse_sequence.prepare(self)
        self.set_dataset('optimize.result.countrate_ROI',[-2]*self.number_of_datapoints,broadcast=True) # Number of pulses sent to ttl_MCP_in with ROI in optimize without accumulating
        self.set_dataset('optimize.result.SSA_power',[-2]*self.number_of_datapoints,broadcast=True) # Number of pulses sent to ttl_MCP_in with ROI in optimize without accumulating
        #self.set_dataset('count_tickle_x',np.arange(1,self.number_of_datapoints+1,1),broadcast=True)
        self.set_dataset('drive_freq',self.freq_drive,broadcast=True)
        self.set_dataset('att',self.att,broadcast=True)
        self.set_dataset('rid',self.scheduler.rid,broadcast=True)
        self.SSA = SSA3032X_R(ip=self.SSA_IP_addr, N_AVG=self.N_SA_avg, data_trace=self.SSA_data_trace)
        print(f">>> RID: {self.scheduler.rid}")
    
    
    def run(self):
        
        start_devices.Devices.start_rigol(self)
        self.load_DAC()
        self.kernel_run_initial()
        print(">>> Start")
        self.kernel_run_driving_experiment()
        print(">>> {:d} finished".format(self.scheduler.rid) )
    
    
    @ kernel
    def kernel_run_initial(self):
        self.core.reset()
        self.core.break_realtime()
        self.dds_tickle.cpld.init()
        self.dds_tickle.init()
        self.dds_tickle.set_att(self.att*dB)
        
        for i in range(self.number_of_warmup_points):
            self.core.break_realtime()
            t_wait = 100
            t_load = 100
            n_repetitions = 500
            count_tot = 0
            for j in range(n_repetitions):
                self.core.break_realtime()
                with sequential:
                    self.ttl_390.on()
                    delay(t_load*us)
                    with parallel:
                        if not self.continuous_loading:
                            self.ttl_390.off()
                        self.ttl_Tickle.on()
                    delay(t_wait*us)
                    with parallel:
                        self.ttl_Tickle.off()
                        self.ttl_Extraction.pulse(2*us)
                        self.ttl_TimeTagger.pulse(2*us)
                        with sequential:
                            delay(200*ns)
                            self.ttl12.pulse(2*us)
                        with sequential:
                            delay(self.t_delay*ns)
                            t_count = self.ttl_MCP_in.gate_rising(self.t_acquisition*ns)
                    count = self.ttl_MCP_in.count(t_count)
                    if count > 0:
                        count = 1
                    count_tot += count
                    delay(10*us)
                    

    @ kernel
    def kernel_run_driving_experiment(self):

        self.core.reset()
        self.core.break_realtime()
        
        delay(self.t_initial_delay*s) # wait for a while before starting the experiment
        for i in range(self.number_of_datapoints):
            self.core.break_realtime()
            freq_drive = self.freq_drive
            t = now_mu()
            self.dds_tickle.set(freq_drive*MHz, phase=0., ref_time_mu=t)
            
            if self.continuous_loading:
                self.ttl_390.on()
            count_tot = 0
            i_avg = 0
            power = 0.
            for j in range(self.n_repetitions):
                self.core.break_realtime()
                with sequential:
                    if not self.continuous_loading:
                        self.ttl_390.on()
                    delay(self.t_load*us)
                    with parallel:
                        if not self.continuous_loading:
                            self.ttl_390.off()
                        if self.apply_driving:
                            self.dds_tickle.sw.on()
                        if self.use_external_driving:
                            self.ttl_Tickle.on()
                    delay(self.t_wait*us)
                    with parallel:
                        if self.use_external_driving:
                            self.ttl_Tickle.off()
                        if self.apply_driving:
                            self.dds_tickle.sw.off()
                        if self.apply_extraction:
                            self.ttl_Extraction.pulse(2*us)
                        self.ttl_TimeTagger.pulse(2*us)
                        with sequential:
                            delay(200*ns)
                            self.ttl12.pulse(2*us)
                        with sequential:
                            delay(self.t_delay*ns)
                            t_count = self.ttl_MCP_in.gate_rising(self.t_acquisition*ns)
                    count = self.ttl_MCP_in.count(t_count)
                    if count > 0:
                        count = 1
                    count_tot += count
                    i_avg += 1
                    if i_avg == int(self.N_SA_avg): 
                        self.SSA.reset_avg(trace=self.SSA_data_trace)
                    if i_avg == int(2.2*self.N_SA_avg): 
                        power = self.SSA.get_tot_power_nW(trace=self.SSA_data_trace) 
                    delay(10*us)
            
            # cycle_duration = t_load+self.t_wait+2+self.t_delay/1000+self.time_window_width/1000+1
            self.mutate_dataset('optimize.result.countrate_ROI',i,count_tot)
            self.mutate_dataset('optimize.result.SSA_power',i,power)


    # @kernel
    # def test(self): 
        # power = self.