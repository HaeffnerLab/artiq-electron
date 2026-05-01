

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
from Instruments import SSA3032X_R, RS

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class RS_driving_with_FTSA(DAC, pulse_sequence, EnvExperiment):

    def build(self):
        DAC.build(self)
        pulse_sequence.build(self)
        start_devices.Devices.build(self)

        self.setattr_device("ccb")
        # self.setattr_argument("output_pulse", BooleanValue(default = True), group = "Main sequence")
        self.setattr_argument('number_of_datapoints', NumberValue(default=10,unit=' ',scale=1,ndecimals=0,step=1)) #how many data points on the plot, run experiment & pulse counting
        self.setattr_argument('number_of_warmup_points',NumberValue(default=100,scale=1,ndecimals=0,step=1))
        self.setattr_argument('tickle_power',NumberValue(default=-40,unit='dBm',scale=1,ndecimals=0,step=1)) #
        self.setattr_argument('freq_drive_min',NumberValue(default=290,unit='MHz',scale=1,ndecimals=6,step=1)) # driving freq
        self.setattr_argument('freq_drive_max',NumberValue(default=290,unit='MHz',scale=1,ndecimals=6,step=1)) # driving freq
        self.setattr_argument('freq_drive_stp',NumberValue(default=1,unit='MHz',scale=1,ndecimals=6,step=1)) # driving freq
        self.setattr_argument('t_load',NumberValue(default=100,unit='ms',scale=1,ndecimals=0,step=1)) # load time
        self.setattr_argument('t_wait',NumberValue(default=100,unit='ms',scale=1,ndecimals=0,step=1)) # wait time
        self.setattr_argument('t_initial_delay',NumberValue(default=30,unit='s',scale=1,ndecimals=0,step=1)) # delay time at the beginning of the experiment
        # self.dds_tickle = self.get_device("urukul0_ch0")
        self.setattr_argument("continuous_loading", BooleanValue(default=False))
        self.setattr_argument("apply_extraction", BooleanValue(default=True))
        self.setattr_argument("apply_driving", BooleanValue(default=True))
        self.setattr_argument("use_external_driving", BooleanValue(default=False))
        self.setattr_argument("RS_IP_addr", StringValue(default=r'USB0::2733::84::104542::0::INSTR'))
        self.setattr_argument("N_SA_avg", NumberValue(default=100,scale=1,ndecimals=0,step=1))
        self.setattr_argument("SSA_data_trace", NumberValue(default=2,scale=1,ndecimals=0,step=1))
        self.setattr_argument("SSA_IP_addr", StringValue(default=f'TCPIP::192.168.169.161::INSTR'))
        # self.setattr_argument("SSA_flag_on_counts", BooleanValue(default=False))
        self.setattr_argument("use_SSA", BooleanValue(default=True))
        self.setattr_argument('SSA_freq_cent',NumberValue(default=184.566138,unit='MHz',scale=1,ndecimals=6,step=0.1))
        self.setattr_argument('SSA_freq_span',NumberValue(default=1,unit='MHz',scale=1,ndecimals=2,step=0.1))
        self.setattr_argument('ttl_ch_SSA',NumberValue(default=22,min=0,max=23,ndecimals=0,step=1,type='int'), 
                                                          group='TTL Channels', 
                                                          tooltip = "use this channel to trigger SSA data taking") 
        self.setattr_device("ttl12")
    
    def prepare(self):
        pulse_sequence.prepare(self)
        if self.freq_drive_min != self.freq_drive_max: 
            self.trap_freqs = np.arange(self.freq_drive_min, self.freq_drive_max, self.freq_drive_stp)
            self.number_of_datapoints = len(self.trap_freqs)
        else: 
            self.trap_freqs = [self.freq_drive_min] * self.number_of_datapoints
        self.set_dataset('optimize.result.countrate_ROI',[-2]*self.number_of_datapoints,broadcast=True) # Number of pulses sent to ttl_MCP_in with ROI in optimize without accumulating
        
        self.set_dataset('SSA_power',[[-210]*751]*self.number_of_datapoints, broadcast=True) 
        # self.set_dataset('SSA_freq_plot', [-200]*751, broadcast=True)
        # self.set_dataset('SSA_power_plot',[-210]*751, broadcast=True)
        #self.set_dataset('count_tickle_x',np.arange(1,self.number_of_datapoints+1,1),broadcast=True)
        
        if self.freq_drive_min != self.freq_drive_max: 
            self.trap_freqs = np.arange(self.freq_drive_min, self.freq_drive_max, self.freq_drive_stp)
        else: 
            self.trap_freqs = [self.freq_drive_min] * self.number_of_datapoints
        self.set_dataset('freq_drive',self.trap_freqs,broadcast=True)
        self.set_dataset('tickle_power',self.tickle_power,broadcast=True)
        self.set_dataset('rid',[self.scheduler.rid],broadcast=True)
        self.setattr_ttl_nickname(f'ttl{self.ttl_ch_SSA}','ttl_SSA') 
        if self.use_SSA:
            self.SSA = SSA3032X_R(ip=self.SSA_IP_addr, N_AVG=self.N_SA_avg, data_trace=self.SSA_data_trace)
            self.SSA.set_freq_range(self.SSA_freq_cent, self.SSA_freq_span)
            self.SSA_freq_list = np.linspace(self.SSA_freq_cent-self.SSA_freq_span/2, self.SSA_freq_cent+self.SSA_freq_span/2, 751)
            self.SSA_data = np.array([-2.0]*751)
            self.set_dataset('SSA_freq', [self.SSA_freq_list]*self.number_of_datapoints, broadcast=True)
        
        self.n_repetitions = int(self.N_SA_avg)+3
        print(f">>> RID: {self.scheduler.rid}")
        self.RS = RS(ip=self.RS_IP_addr, triggered=True)
    
    
    def run(self):
        
        start_devices.Devices.start_rigol(self)
        self.load_DAC()
        self.kernel_run_initial()
        print(">>> Start")
        self.kernel_run_driving_experiment()
        self.RS.set_all_off()
        print(">>> {:d} finished".format(self.scheduler.rid) )
    
    
    @ kernel
    def kernel_run_initial(self):
        self.core.reset()
        self.core.break_realtime()
        # self.dds_tickle.cpld.init()
        # self.dds_tickle.init()
        # self.dds_tickle.set_att(self.att*dB)
        
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
        # self.dds_tickle.cpld.init()
        # self.dds_tickle.init()
        # self.dds_tickle.set_att(self.att*dB)
        delay(self.t_initial_delay*s) # wait for a while before starting the experiment
        for i in range(self.number_of_datapoints):
            self.core.break_realtime()
            # freq_tickle = self.step_size*i+self.freq_start
            freq_tickle = self.trap_freqs[i]
            # t = now_mu()
            self.RS.set_freq_pwr(freq_tickle*1e6, self.tickle_power)
            
            if self.continuous_loading:
                delay(1*ms) # wait for a while before starting the experiment
                self.ttl_390.on()
            count_tot = 0
            # delay(self.t_initial_delay*s) # wait for a while before starting the experiment
            for j in range(self.n_repetitions):
                if j == 1: 
                    self.SSA.reset_avg(trace=self.SSA_data_trace)
                if j == self.N_SA_avg + 2: 
                    self.SSA_data = self.SSA.get_data(trace=self.SSA_data_trace)
                self.core.break_realtime()
                with sequential:
                    if not self.continuous_loading:
                        self.ttl_390.on()
                    delay(self.t_load*ms)
                    with parallel:
                        if not self.continuous_loading:
                            self.ttl_390.off()
                        self.ttl_Tickle.on()
                        self.ttl_SSA.on()
                        # self.RS.set_output_on() # NOTE: update 9/9, moving the switch on/off in each repetition
                    delay(self.t_wait*ms)
                    with parallel:
                        self.ttl_Extraction.pulse(2*us)
                        # self.RS.set_output_off() # NOTE: update 9/9, moving the switch on/off in each repetition
                        self.ttl_Tickle.off()
                        self.ttl_SSA.off()
                        
                        # self.ttl_TimeTagger.pulse(2*us)
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
            # self.dds_tickle.sw.off() NOTE: update 9/9, moving the switch on/off in each repetition
            # self.RS.set_output_off()  ## NOTE: RTIO error if inside cycle, turn on has some PC delay
            # cycle_duration = t_load+self.t_wait+2+self.t_delay/1000+self.time_window_width/1000+1
            self.mutate_dataset('optimize.result.countrate_ROI',i,count_tot)
            # self.append_to_dataset('SSA_freq_plot',i,self.SSA_freq_list)
            if self.use_SSA:
                self.mutate_dataset('SSA_power',i,self.SSA_data)
            self.mutate_dataset('rid',0,self.scheduler.rid/100000+i)
            # self.append_to_dataset('SSA_freq_plot',i,self.SSA_freq_list)


    # @kernel
    # def test(self): 
        # power = self.