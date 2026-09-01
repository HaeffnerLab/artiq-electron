from artiq.experiment import *
import time
import numpy as np
from loading_experiments import LoadingExperiments

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class LoadingWithDelayedTrapDrive(LoadingExperiments, EnvExperiment):
    """
    Loading with delayed trap drive turning on time
    """

    def build(self):
        LoadingExperiments.build(self)
        
        self.setattr_argument(
            "t_trap_drive_delay", 
            Scannable(
                default=RangeScan(start=0.1, stop=3, npoints=6),
                unit="s",
                scale=1,
            ),
            group='Loading parameters'
        )

    def prepare(self):
        LoadingExperiments.prepare(self)
        self.N_trap_drive_delay = len(list(iter(self.t_trap_drive_delay)))
        self.N_total = self.N_trap_drive_delay * self.N_repetition
        self.mutate_dataset('Progress_index', 1, self.N_total)
        self.record_dtype = np.dtype([
                    ('t_trap_drive_delay', np.float64),
                    ('rep_idx', np.int32),
                    ('trace', np.float64, (int(self.t_data/self.SSA_SWT)*751,))
                ])
        
        # 4. Initialize empty dataset for structured data
        # self.set_dataset('scan_data', np.empty(0, dtype=self.record_dtype), broadcast=True)
        self.set_dataset('scan_data', [], broadcast=True)
        
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
        prg_idx = 0
        for trap_delay in list(iter(self.t_trap_drive_delay)):
            # all_data = []
            N_data = int(self.t_data/self.SSA_SWT)
            for N in range(self.N_repetition):
                loc_data = []
                self.FEtip_PSU.set_voltage(V_on)
                time.sleep(trap_delay)
                self.Valon.output_on() 
                self.Valon.set_power(self.P_load)
                time.sleep(self.t_load-trap_delay)
                self.SSA.clear_averaging() 
                if self.tip_off_during_data:
                    self.FEtip_PSU.set_voltage(V_off)
                self.Valon.set_power(self.P_detect)
                for _ in range(N_data):
                    data = self.SSA.get_full_trace()
                    loc_data.extend(data)
                trace_array = np.array(loc_data)
                self.mutate_dataset('SSA_power', 0, trace_array)
                row = np.array([(trap_delay, N, trace_array)], dtype=self.record_dtype)
                self.append_to_dataset('scan_data', row)
                if show_progress:
                    self.mutate_dataset('Progress_index', 0, prg_idx+1)
                    prg_idx += 1
                time.sleep(self.t_rest)
        
        self.FEtip_PSU.ramp_down(0)
        self.FEtip_PSU.ramp_down_ch(self.FET_ch_fixed, 0)
        self.Valon.output_off()
        self.SSA.clear_averaging()


class LoadingWithDelayedTrapDriveSwitching(LoadingExperiments, EnvExperiment):
    """
    Loading with delayed trap drive switching time
    """

    def build(self):
        LoadingExperiments.build(self)
        
        self.setattr_argument(
            "t_trap_drive_delay", 
            Scannable(
                default=RangeScan(start=0.1, stop=3, npoints=6),
                unit="s",
                scale=1,
            ),
            group='Loading parameters'
        )

    def prepare(self):
        LoadingExperiments.prepare(self)
        self.N_trap_drive_delay = len(list(iter(self.t_trap_drive_delay)))
        self.N_total = self.N_trap_drive_delay * self.N_repetition
        self.mutate_dataset('Progress_index', 1, self.N_total)
        self.record_dtype = np.dtype([
                    ('t_trap_drive_delay', np.float64),
                    ('rep_idx', np.int32),
                    ('trace', np.float64, (int(self.t_data/self.SSA_SWT)*751,))
                ])
        
        # 4. Initialize empty dataset for structured data
        # self.set_dataset('scan_data', np.empty(0, dtype=self.record_dtype), broadcast=True)
        self.set_dataset('scan_data', [], broadcast=True)
        
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
        prg_idx = 0
        for trap_delay in list(iter(self.t_trap_drive_delay)):
            # all_data = []
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
                time.sleep(trap_delay)
                self.Valon.set_power(self.P_detect)
                for _ in range(N_data):
                    data = self.SSA.get_full_trace()
                    loc_data.extend(data)
                trace_array = np.array(loc_data)
                self.mutate_dataset('SSA_power', 0, trace_array)
                row = np.array([(trap_delay, N, trace_array)], dtype=self.record_dtype)
                self.append_to_dataset('scan_data', row)
                if show_progress:
                    self.mutate_dataset('Progress_index', 0, prg_idx+1)
                    prg_idx += 1
                time.sleep(self.t_rest)
        
        self.FEtip_PSU.ramp_down(0)
        self.FEtip_PSU.ramp_down_ch(self.FET_ch_fixed, 0)
        self.Valon.output_off()
        self.SSA.clear_averaging()