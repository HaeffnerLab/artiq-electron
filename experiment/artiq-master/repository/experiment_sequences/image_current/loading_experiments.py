from artiq.experiment import *
import time
import numpy as np
from edes.experiments.devices.base import TestValon
from DAC_experiments import DAC
from FET_experiments import FETip
from SA_experiments import SpectrumAnalyzer

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class LoadingExperiments(DAC, SpectrumAnalyzer, FETip):
    """
    A template for all loading experiments needing a DAC, SA, and FET.
    """
    def build(self):
        FETip.build(self)
        SpectrumAnalyzer.build(self, load_config=False) # no need to load config again since FETip already loads it
        DAC.build(self, load_config=False)
        self.setattr_argument('P_load',NumberValue(default=12,unit='dBm',scale=1,ndecimals=1,step=0.1),group="Loading parameters")
        self.setattr_argument('P_detect',NumberValue(default=5,unit='dBm',scale=1,ndecimals=1,step=0.1),group="Loading parameters")
        self.setattr_argument('t_load',NumberValue(default=20,unit='s',scale=1,ndecimals=3,step=1), group="Loading parameters") # load time
        self.setattr_argument('t_data',NumberValue(default=1,unit='s',scale=1,ndecimals=3,step=1), group="Loading parameters") # wait time
        self.setattr_argument('t_initial_delay',NumberValue(default=5,unit='s',scale=1,ndecimals=3,step=1), group="Loading parameters") # delay time at the beginning of the experiment 
        self.setattr_argument('t_rest',NumberValue(default=1,unit='s',scale=1,ndecimals=3,step=1), group="Loading parameters") # delay time in between repetitions
        self.setattr_argument('N_repetition',NumberValue(default=30,scale=1,ndecimals=0,step=1), group='Loading parameters') # Number of repetitions
        self.setattr_argument('tip_off_during_data',BooleanValue(default=True), group='Loading parameters') # A flag to indicate whether the tip is turned off during data taking
        self.setattr_argument('V_off_change',NumberValue(default=200,unit='V',scale=1,ndecimals=0,step=1), group="Loading parameters") # V_off = V_tip - V_off_change 
        self.setattr_argument('recalibrate_V_tip',BooleanValue(default=True), group='Loading parameters') # Whether to calibrate the FET voltage/current during experiment
        self.setattr_argument('is_background',BooleanValue(default=False), group='Loading parameters') # A flag to indicate whether the experiment is background
        
    def prepare(self):
        FETip.prepare(self)
        SpectrumAnalyzer.prepare(self)
        DAC.prepare(self)
        if not hasattr(self, 'Valon'): 
            self.Valon = TestValon()
        self.set_dataset('t_data',np.linspace(0, int(self.t_data/(self.SSA_SWT))*self.SSA_SWT, int(self.t_data/(self.SSA_SWT))*751),broadcast=True)
        self.set_dataset('SSA_power',[np.zeros(int(self.t_data/(self.SSA_SWT))*751)],broadcast=True)
        self.set_dataset('Progress_index',[0, self.N_repetition],broadcast=True)
        if self.is_background: 
            self.recalibrate_V_tip = False
        if self.recalibrate_V_tip: 
            self.calibrate_FET()
        self.load_DAC()

    def run(self, show_progress=True):
        if self.is_background:
            V_on = 0
            V_off = 0
        else:
            V_on = self.FET_V_nominal
            V_off = V_on - self.V_off_change
        self.FEtip_PSU.ramp_up_ch(self.FET_ch_fixed, self.FET_V_fixed)
        self.FEtip_PSU.select_ch(self.FET_ch_sweep)
        self.FEtip_PSU.ramp_up(V_off)
        
        self.SSA.clear_averaging()
        data = self.SSA.get_full_trace()
        self.SSA.set_div_scale(5) 
        self.SSA.set_ref_level(max(data)+25)

        all_data = []
        N_data = int(self.t_data/self.SSA_SWT)
        for N in range(self.N_repetition):
            loc_data = []
            self.FEtip_PSU.set_voltage(V_on)
            self.Valon.output_on() 
            self.Valon.set_power(self.P_load)
            time.sleep(self.t_load)
            self.SSA.clear_averaging() 
            if self.tip_off_during_data:
                self.FEtip_PSU.set_voltage(V_off)
            self.Valon.set_power(self.P_detect)
            for _ in range(N_data):
                data = self.SSA.get_full_trace()
                loc_data.extend(data)
            self.mutate_dataset('SSA_power', 0, np.array(loc_data))
            all_data.append(loc_data)
            if show_progress:
                self.mutate_dataset('Progress_index', 0, N+1)
            time.sleep(self.t_rest)
        self.set_dataset(f'all_meas',np.array(all_data),broadcast=True)
        self.FEtip_PSU.ramp_down(0)
        self.FEtip_PSU.ramp_down_ch(self.FET_ch_fixed, 0)
        self.Valon.output_off()
        self.SSA.clear_averaging()
        return all_data


class LoadingWithSingleConfig(LoadingExperiments, EnvExperiment):
    """
    Loading with single config
    """
    def build(self): 
        LoadingExperiments.build(self) 

    def prepare(self): 
        LoadingExperiments.prepare(self) 

    def run(self): 
        LoadingExperiments.run(self) 
        print(">>> {:d} finished".format(self.scheduler.rid) )


class LoadingWithTwoRFSteps(LoadingExperiments):
    """
    Loading with RF drive stepping twice
    """
    def build(self): 
        LoadingExperiments.build(self) 
        self.setattr_argument('delta_P_step',NumberValue(default=-0.1,unit='dBm',scale=1,ndecimals=1,step=0.1),group="Loading parameters")
        self.setattr_argument('P_stepping_threshold',NumberValue(default=-60,unit='dBm',scale=1,ndecimals=1,step=0.1),group="Loading parameters")

    def prepare(self): 
        LoadingExperiments.prepare(self) 
        self.set_dataset('t_data',np.linspace(0, int(self.t_data/(self.SSA_SWT))*self.SSA_SWT, int(self.t_data/(self.SSA_SWT))*751),broadcast=True)
        self.set_dataset('SSA_power',[np.zeros(int(self.t_data/(self.SSA_SWT))*751)],broadcast=True)
        self.set_dataset('P_detect_track',[np.zeros(int(self.t_data/(self.SSA_SWT)))]*self.N_repetition,broadcast=True)

    def run(self, show_progress=True):
        if self.is_background:
            V_on = 0
            V_off = 0
        else:
            V_on = self.FET_V_nominal
            V_off = V_on - self.V_off_change
        self.FEtip_PSU.ramp_up_ch(self.FET_ch_fixed, self.FET_V_fixed)
        self.FEtip_PSU.select_ch(self.FET_ch_sweep)
        self.FEtip_PSU.ramp_up(V_off)
        
        self.SSA.clear_averaging()
        data = self.SSA.get_full_trace()
        self.SSA.set_div_scale(5) 
        self.SSA.set_ref_level(max(data)+25)

        all_data = []
        N_data = int(self.t_data/self.SSA_SWT)
        
        for N in range(self.N_repetition):
            P_current = self.P_detect
            loc_data = []
            self.FEtip_PSU.set_voltage(V_on)
            self.Valon.output_on() 
            self.Valon.set_power(self.P_load)
            time.sleep(self.t_load)
            self.SSA.clear_averaging() 
            if self.tip_off_during_data:
                self.FEtip_PSU.set_voltage(V_off)
            self.Valon.set_power(self.P_detect)
            P_power_track = np.ones(N_data)*P_current
            for i in range(N_data):
                data = self.SSA.get_full_trace()
                loc_data.extend(data)
                if max(data) >= self.P_stepping_threshold:
                    P_current += self.delta_P_step
                    self.Valon.set_power(P_current)
                    P_power_track[i] = P_current
            self.mutate_dataset('P_detect_track', N+1, P_power_track)
            self.mutate_dataset('SSA_power', 0, np.array(loc_data))
            all_data.append(loc_data)
            if show_progress:
                self.mutate_dataset('Progress_index', 0, N+1)
            time.sleep(self.t_rest)
        self.set_dataset(f'all_meas',np.array(all_data),broadcast=True)
        self.FEtip_PSU.ramp_down(0)
        self.FEtip_PSU.ramp_down_ch(self.FET_ch_fixed, 0)
        self.Valon.output_off()
        self.SSA.clear_averaging()
        return all_data

