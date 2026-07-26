from artiq.experiment import *
import time
import numpy as np

from Config import Configuration

class FETip(Configuration, HasEnvironment):
    """
    A field emission tip calibration/sweep code. All experiments using FEtip should inherit this block.
    Has two functions, one is to perform a normal sweep based on V_sweep range,
    the other is to do a calibration to find the voltage needed to reach I_nominal current. The calibration will start a sweep
    from V_nomial - V_calibration_range, then if none of the measured current reaches I_nominal, then increase the largest voltage
    in the sweep by V_calibration step.
    """

    def build(self):
        Configuration.build(self)
        self.setattr_argument(
                    "FET_V_sweep", 
                    Scannable(
                        default=RangeScan(start=100, stop=300, npoints=11),
                        unit="V",
                        scale=1
                    ),
                    group='Field emission tip'
                )
        self.setattr_argument('FET_load_calibration',BooleanValue(default=True), group='Field emission tip') # Whether to use previous calibration data
        self.setattr_argument('FET_V_nominal',NumberValue(default=100,unit='V',scale=1,ndecimals=1,step=1),group="Field emission tip")
        self.setattr_argument('FET_V_fixed',NumberValue(default=40,unit='V',scale=1,ndecimals=1,step=1),group="Field emission tip")
        self.setattr_argument('FET_V_calibration_range',NumberValue(default=100,unit='V',scale=1,ndecimals=1,step=1),group="Field emission tip")
        self.setattr_argument('FET_V_calibration_step',NumberValue(default=5,unit='V',scale=1,ndecimals=1,step=1),group="Field emission tip")
        self.setattr_argument('FET_V_warning',NumberValue(default=1400,unit='V',scale=1,ndecimals=1,step=1),group="Field emission tip")
        self.setattr_argument('FET_N_calibration_points',NumberValue(default=11,unit='',scale=1,ndecimals=1,step=1),group="Field emission tip")
        self.setattr_argument('FET_I_max',NumberValue(default=35e-9,unit='A',scale=1,ndecimals=12,step=1e-9),group="Field emission tip")
        self.setattr_argument('FET_I_nominal',NumberValue(default=30e-9,unit='A',scale=1,ndecimals=12,step=1e-9),group="Field emission tip")
        self.setattr_argument('FET_R_measure',NumberValue(default=200e6,unit='MOhm',scale=1e6,ndecimals=2,step=1),group="Field emission tip")
        self.setattr_argument('FET_N_avg',NumberValue(default=1,unit='',scale=1,ndecimals=0,step=1),group="Field emission tip")
        self.setattr_argument('FET_t_PSU_settle',NumberValue(default=2,unit='s',scale=1,ndecimals=1,step=1),group="Field emission tip")
        self.setattr_argument('FET_t_meas_delay',NumberValue(default=0.2,unit='s',scale=1,ndecimals=1,step=0.1),group="Field emission tip")
        self.setattr_argument('FET_ch_sweep', StringValue(default='neg'), group="Field emission tip")
        self.setattr_argument('FET_ch_fixed', StringValue(default='pos'), group="Field emission tip")
        self.setattr_argument('FET_multimeter', StringValue(default='Agilent'), group="Field emission tip")

    def prepare(self):
        Configuration.prepare(self)
        self.multimeter = getattr(self, self.FET_multimeter)
        all_V = np.array(self.FET_V_sweep.sequence)
        self.FET_all_V = all_V
        self.set_dataset('FET.all_V',all_V,broadcast=True)
        self.set_dataset('FET.all_I',np.zeros(len(all_V)),broadcast=True)
        self.set_dataset('FET.all_I_std',np.zeros(len(all_V)),broadcast=True)
        self.FET_I_max *= 1e9 
        self.FET_I_nominal *= 1e9
        if self.FET_load_calibration: 
            V_nominal = self.get_dataset('FET.calibrated_V_tip', default=None)
            self.FET_V_nominal = V_nominal if V_nominal is not None else self.FET_V_nominal
            # if V_nominal is None: 
            #     self.set_dataset('FET.calibrated_V_tip', [self.FET_V_nominal], broadcast=True)
        else: 
            V_nominal = self.get_dataset('FET.calibrated_V_tip', default=None) 
            # if V_nominal is None: 
            #     self.set_dataset('FET.calibrated_V_tip', [self.FET_V_nominal], broadcast=True)
        
    def calibrate_FET(self): 
        """
        V_tip is used to replace the nominal voltage to start with, if supplied
        """
        max_I = -1
        i_cal = 1
        V_tip = self.FET_V_nominal
        while max_I < self.FET_I_nominal:
            self.FET_all_V = np.linspace(V_tip-self.FET_V_calibration_range, V_tip, int(self.FET_N_calibration_points))
            all_I, all_V = self.run_FET_sweep()
            I = np.mean(all_I, axis=1)*1e9 
            V = np.array(all_V)
            self.set_dataset(f'FET.calibration.{i_cal}.all_V',all_V,broadcast=True)
            self.set_dataset(f'FET.calibration.{i_cal}.all_I',all_I,broadcast=True)
            i_cal += 1
            max_I = max(I)
            if max_I < self.FET_I_nominal: 
                V_tip = self.find_next_V(I, V)
            else: 
                V_tip = float(V[np.where(I-self.FET_I_nominal >= 0)[0][0]])
            if V_tip >= self.FET_V_warning: 
                print(f'>>> Tip voltage exceeding safe level at {self.V_warning}V, setting to max voltage')
                V_tip = self.FET_V_warning
                break 
        self.set_dataset('FET.calibrated_V_tip', V_tip, broadcast=True)
        self.FET_V_nominal = V_tip

    def find_next_V(self, I, V): 
        """
        May want some adaptive algo here. Currently just using some gradient ascent from current to nominal
        to increase the step size when difference is large at the beginning. Improvement can be done by doing
        a fit to extrapolate the voltage needed then directly move there. 
        """
        adjusted_gradient = min(abs(I[-1] - I[-2])/abs(V[-1]-V[-2])*10, 0.1) # adding small 0.1 value to prevent overflow
        ## using 10x here is to estimate the exponential slope based on linear slope, using 10x correction factor
        ratio = max(int(min((self.FET_I_nominal-max(I))/adjusted_gradient/self.FET_V_calibration_step, 10)), 1) # this way the ratio is controlled between 1-10
        return V[np.argmax(I)] + self.FET_V_calibration_step * ratio
    
    def run_FET_sweep(self):
        self.FEtip_PSU.ramp_up_ch(self.FET_ch_fixed, self.FET_V_fixed)
        self.FEtip_PSU.select_ch(self.FET_ch_sweep)
        all_I = [] 
        all_V = self.FET_all_V
        self.FEtip_PSU.ramp_up_ch(self.FET_ch_sweep, all_V[0])
        time.sleep(2*self.FET_t_PSU_settle)
        self.multimeter.measure_V()
        for Vi in range(len(all_V)): 
            V = self.FET_all_V[Vi]
            self.FEtip_PSU.set_voltage(V) 
            time.sleep(self.FET_t_PSU_settle) 
            I_loc = []
            for _ in range(self.FET_N_avg):
                I = self.multimeter.measure_V()/self.FET_R_measure
                I_loc.append(I)    
                time.sleep(self.FET_t_meas_delay) 
            all_I.append(I_loc) 
            self.mutate_dataset('FET.all_V', Vi, V)
            self.mutate_dataset('FET.all_I', Vi, np.mean(I_loc)*1e9)
            self.mutate_dataset('FET.all_I_std', Vi, np.std(I_loc)*1e9)
            if abs(I) >= self.FET_I_max: 
                print(f">>> Warning: Current {I} exceeds maximum allowed {self.FET_I_max}. Stopping sweep.")
                break
        self.FEtip_PSU.ramp_down(0)
        self.FEtip_PSU.ramp_down_ch(self.FET_ch_fixed, 0)
        return all_I, all_V[:len(all_I)]

class FETipSweep(EnvExperiment, FETip): 
    """
    Sweep FE-tip voltage
    """
    def build(self): 
        FETip.build(self)

    def prepare(self):
        return FETip.prepare(self)

    def run(self): 
        return FETip.run_FET_sweep(self)