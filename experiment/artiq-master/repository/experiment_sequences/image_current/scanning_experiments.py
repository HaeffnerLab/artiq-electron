from artiq.experiment import *
import time
import numpy as np
from loading_experiments import LoadingExperiments
from edes.utils.utils import sample_hyperparameters

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class LoadingWithDCScans(LoadingExperiments, EnvExperiment):
    """
    Loading with varied multipoles
    """
    def build(self):
        LoadingExperiments.build(self)
        self.setattr_argument('sampling_parameters',BooleanValue(default=True), group='Scanning parameters')
        self.setattr_argument('max_scan_points',NumberValue(default=16,unit='',scale=1,ndecimals=0,step=1), group="Scanning parameters")
        self.setattr_argument(
            "Ex_scans", 
            Scannable(
                default=RangeScan(start=-1, stop=1, npoints=2),
                unit="V/mm",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "Ey_scans", 
            Scannable(
                default=RangeScan(start=-1, stop=1, npoints=2),
                unit="V/mm",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "Ez_scans", 
            Scannable(
                default=RangeScan(start=-1, stop=1, npoints=2),
                unit="V/mm",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "U1_scans", 
            Scannable(
                default=RangeScan(start=-1, stop=1, npoints=2),
                unit="V/mm^2",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "U2_scans", 
            Scannable(
                default=RangeScan(start=-1, stop=1, npoints=2),
                unit="V/mm^2",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "U3_scans", 
            Scannable(
                default=RangeScan(start=-1, stop=1, npoints=2),
                unit="V/mm^2",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "U4_scans", 
            Scannable(
                default=RangeScan(start=-1, stop=1, npoints=2),
                unit="V/mm^2",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "U5_scans", 
            Scannable(
                default=RangeScan(start=-1, stop=1, npoints=2),
                unit="V/mm^2",
                scale=1
            ),
            group='Scanning parameters'
        )

    def prepare(self):
        LoadingExperiments.prepare(self)
        multipole_scan_dict = {'Ex': list(iter(self.Ex_scans)), 
                               'Ey': list(iter(self.Ey_scans)), 
                               'Ez': list(iter(self.Ez_scans)), 
                               'U1': list(iter(self.U1_scans)),
                               'U2': list(iter(self.U2_scans)), 
                               'U3': list(iter(self.U3_scans)), 
                               'U4': list(iter(self.U4_scans)), 
                               'U5': list(iter(self.U5_scans))}
        self.all_multipole_runs = sample_hyperparameters(multipole_scan_dict, self.max_scan_points, self.sampling_parameters)
        self.N_total = len(self.all_multipole_runs)
        self.mutate_dataset('Progress_index', 1, self.N_total)
        
    def run(self):
        progress_idx = 1
        for combo in self.all_multipole_runs: 
            data_str = f'data'
            for m in combo: 
                setattr(self, m, combo[m])
                data_str += f".{m}__{str(combo[m]).replace('.', 'p')}"
            self.load_DAC()
            result = LoadingExperiments.run(self,show_progress=False) 
            self.set_dataset(data_str, result, broadcast=True)
            self.mutate_dataset('Progress_index', 0, progress_idx)
            progress_idx += 1
            if self.recalibrate_V_tip: 
                self.calibrate_FET()


class LoadingWithRFScans(LoadingExperiments, EnvExperiment):
    """
    Loading with varied RF power
    """
    def build(self):
        LoadingExperiments.build(self)
        self.setattr_argument('sampling_parameters',BooleanValue(default=True), group='Scanning parameters')
        self.setattr_argument('max_scan_points',NumberValue(default=16,unit='',scale=1,ndecimals=0,step=1), group="Scanning parameters")
        self.setattr_argument(
            "P_load_scans", 
            Scannable(
                default=RangeScan(start=8, stop=12, npoints=2),
                unit="dBm",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "P_detect_scans", 
            Scannable(
                default=RangeScan(start=3, stop=7, npoints=5),
                unit="dBm",
                scale=1
            ),
            group='Scanning parameters'
        )
        

    def prepare(self):
        LoadingExperiments.prepare(self)
        multipole_scan_dict = {'P_load': list(iter(self.P_load_scans)), 
                               'P_detect': list(iter(self.P_detect_scans))}
        self.all_multipole_runs = sample_hyperparameters(multipole_scan_dict, self.max_scan_points, self.sampling_parameters)
        self.N_total = len(self.all_multipole_runs)
        self.mutate_dataset('Progress_index', 1, self.N_total)
        
    def run(self):
        progress_idx = 1
        for combo in self.all_multipole_runs: 
            data_str = f'data'
            for m in combo: 
                setattr(self, m, combo[m])
                data_str += f".{m}__{str(combo[m]).replace('.', 'p')}"
            result = LoadingExperiments.run(self,show_progress=False) 
            self.set_dataset(data_str, result, broadcast=True)
            self.mutate_dataset('Progress_index', 0, progress_idx)
            progress_idx += 1
            if self.recalibrate_V_tip: 
                self.calibrate_FET()


class LoadingWithTloadScans(LoadingExperiments, EnvExperiment):
    """
    Loading with varied loading time
    """
    def build(self):
        LoadingExperiments.build(self)
        self.setattr_argument('sampling_parameters',BooleanValue(default=True), group='Scanning parameters')
        self.setattr_argument('max_scan_points',NumberValue(default=16,unit='',scale=1,ndecimals=0,step=1), group="Scanning parameters")
        self.setattr_argument(
            "t_load_scans", 
            Scannable(
                default=RangeScan(start=5, stop=30, npoints=2),
                unit="s",
                scale=1
            ),
            group='Scanning parameters'
        )
        self.setattr_argument(
            "t_data_scans", 
            Scannable(
                default=RangeScan(start=0.1, stop=2, npoints=5),
                unit="s",
                scale=1
            ),
            group='Scanning parameters'
        )
        

    def prepare(self):
        LoadingExperiments.prepare(self)
        multipole_scan_dict = {'t_load': list(iter(self.t_load_scans)), 
                               't_data': list(iter(self.t_data_scans))}
        self.all_multipole_runs = sample_hyperparameters(multipole_scan_dict, self.max_scan_points, self.sampling_parameters)
        self.N_total = len(self.all_multipole_runs)
        self.mutate_dataset('Progress_index', 1, self.N_total)
        
    def run(self):
        progress_idx = 1
        for combo in self.all_multipole_runs: 
            data_str = f'data'
            for m in combo: 
                setattr(self, m, combo[m])
                data_str += f".{m}__{str(combo[m]).replace('.', 'p')}"
            result = LoadingExperiments.run(self,show_progress=False) 
            self.set_dataset(data_str, result, broadcast=True)
            self.mutate_dataset('Progress_index', 0, progress_idx)
            progress_idx += 1
            if self.recalibrate_V_tip: 
                self.calibrate_FET()