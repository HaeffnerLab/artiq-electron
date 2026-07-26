

import sys
import os
#import datetime import datetime
import select
from artiq.experiment import *
from artiq.coredevice.ad9910 import AD9910
from artiq.coredevice.ad53xx import AD53xx
import time
import numpy as np
from edes.experiments import Experiment
from edes.experiments.sequences import base as sequences
from edes.experiments.sequences import calibration as calibration_sequences

# from extraction_sequence import pulse_sequence
# import start_devices
# import load_DAC
# from load_DAC import DAC
import tqdm

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class ResetTipVoltage(EnvExperiment):
    def build(self):
        self.setattr_device("scheduler")

        # Expose calibration targets and thresholds to Dashboard
        self.setattr_argument("I_tip", NumberValue(default=2.0e-9, unit="nA", scale=1e-9), group="Calibration parameters")
        self.setattr_argument("V_tip_init", NumberValue(default=100.0, unit="V"), group="Calibration parameters")

        self.setattr_argument("V_warning", NumberValue(default=1300.0, unit="V"), group="Safety Limits")
        
        self.setattr_argument("I_max", NumberValue(default=20e-9, unit="nA", scale=1e-9), group="Safety Limits")
        self.setattr_argument("R", NumberValue(default=9.52e6, unit="MOhm", scale=1e6), group="Hardware Parameters")
        self.setattr_argument("V_pos", NumberValue(default=40.0, unit="V"), group="Sweep Config")
        self.setattr_argument('N_avg',NumberValue(default=1,unit=' ',scale=1,ndecimals=0,step=1),group="Sweep Config")
        self.setattr_argument('t_PSU_settle',NumberValue(default=2,unit='s',scale=1,ndecimals=1,step=1),group="Sweep Config")
        self.setattr_argument('t_meas_delay',NumberValue(default=0.2,unit='s',scale=1,ndecimals=1,step=0.1),group="Sweep Config")
        self.setattr_argument('ch_sweep', StringValue(default='neg'), group="Hardware Parameters")
        self.setattr_argument('ch_fixed', StringValue(default='pos'), group="Hardware Parameters")
        self.setattr_argument('multimeter', StringValue(default='Agilent'), group="Hardware Parameters")

        
        


        self.setattr_argument("V_range", NumberValue(default=30.0, unit="V"), group="Sweep Config")
        self.setattr_argument("V_step", NumberValue(default=2.0, unit="V"), group="Sweep Config")
        self.setattr_argument("fet_experiment_file", StringValue(default="/home/electron/artiq/experiment/artiq-master/repository/experiment_sequences/instruments/tip_characterization.py"), group="Sequence Paths")
        self.setattr_argument('device_loaded', BooleanValue(default=False), group="Additional Parameters")

    def run(self):
        self.calibrate_tip()

    def calibrate_tip(self):
        """Callable calibration routine."""
        max_I = 0.0
        # Read current V_tip if stored in dataset, otherwise default starting guess
        V_tip = self.V_tip_init

        # Work in nA for direct comparison with dataset output
        target_I_nA = self.I_tip * 1e9 

        while max_I < target_I_nA:
            # Prepare arguments for FETipCharacterization
            exp_kwargs = {
                "V_start": V_tip - self.V_range,
                "V_stop": V_tip + self.V_step / 2.0,
                "V_step": self.V_step,
                "V_fixed": self.V_pos,
                "I_max": self.I_max,
                "R": self.R,
                "N_avg": self.N_avg,
                "t_PSU_settle": self.t_PSU_settle,
                "t_meas_delay": self.t_meas_delay,
                "ch_sweep": self.ch_sweep,
                "ch_fixed": self.ch_fixed,
                "multimeter": self.multimeter,
                "device_loaded": self.device_loaded,
            }

            exp_id = {
                "file": self.fet_experiment_file,
                "class_name": "FETipCharacterization",
                "arguments": exp_kwargs,
                "log_level": 30
            }

            # Submit to ARTIQ scheduler in a sub-pipeline to prevent deadlocks
            rid = self.scheduler.submit(pipeline_name="sub_pipeline", expid=exp_id, priority=0)
            
            # Poll status until the RID is no longer in the scheduler queue
            while True:
                status = self.scheduler.get_status()
                if rid not in status:
                    break  # Experiment completed or was terminated
                time.sleep(0.5)

            # Retrieve datasets populated by FETipCharacterization
            I_data = self.get_dataset("FET.all_I")  # Values in nA
            V_data = self.get_dataset("FET.all_V")  # Values in V

            max_I = np.max(I_data)

            if max_I < (target_I_nA - 0.1):
                V_tip += 5.0
            else:
                idx = np.where(I_data - target_I_nA > -0.1)[0]
                if len(idx) > 0:
                    V_tip = float(V_data[idx[0]])

            if V_tip >= self.V_warning:
                print(f">>> Tip voltage reached warning limit ({self.V_warning} V). Stopping.")
                V_tip = self.V_warning
                break

        # Save updated calibrated V_tip back into datasets for future sequences
        self.set_dataset("FET.V_tip", V_tip, broadcast=True, persist=True)
        print(f"Calibration complete! Calibrated V_tip = {V_tip:.1f} V")
        return V_tip
