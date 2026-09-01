from artiq.experiment import *
import time
import numpy as np
from loading_experiments import LoadingExperiments

#underflow errors happen when you are out of sync in time or trying to define a process in the past
def print_underflow():
    print('RTIO underflow occured')


class LoadingWithDelayedDrivingNew(LoadingExperiments, EnvExperiment):
    """
    Loading with delayed Urukul driving and saving with structured numpy data
    """

    def build(self):
        LoadingExperiments.build(self)
        self.setattr_argument(
            "driving_freq", 
            Scannable(
                default=RangeScan(start=150e6, stop=210e6, npoints=11),
                unit="MHz",
                scale=1e6
            ),
            group='Driving'
        )
        self.setattr_argument(
            "att", 
            Scannable(
                default=RangeScan(start=20, stop=25, npoints=6),
                unit="dB",
                scale=1,
            ),
            group='Driving'
        )
        
        self.setattr_argument('phase',NumberValue(default=0,scale=1,ndecimals=1,step=0.1), group="Driving") # drive phase
        self.setattr_argument('t_driving_delay',NumberValue(default=50e-3,unit='s',scale=1,ndecimals=3,step=1), group="Driving") # delay time before applying driving with respect to the point where SA taking data
        # self.setattr_argument('t_driving_time',NumberValue(default=50e-3,unit='s',scale=1,ndecimals=3,step=1), group="Driving") # drive on time
        self.dds_tickle = self.get_device("urukul0_ch0")


    def prepare(self):
        LoadingExperiments.prepare(self)
        self.N_driving_freq = len(list(iter(self.driving_freq)))
        self.N_attenuation = len(list(iter(self.att)))
        self.N_total = self.N_attenuation * self.N_driving_freq * self.N_repetition
        self.mutate_dataset('Progress_index', 1, self.N_total)

        # 1. Calculate time axis length
        N_data_predriving = int(self.t_driving_delay / self.SSA_SWT)
        N_data_postdriving = max(int((self.t_data - self.t_driving_delay) / self.SSA_SWT), 1)
        self.N_data_total_points = (N_data_predriving + N_data_postdriving) * 751

        # 2. Save the shared time vector once
        t_data = np.linspace(0, (N_data_predriving + N_data_postdriving) * self.SSA_SWT, self.N_data_total_points)
        self.set_dataset('t_data', t_data, broadcast=True)

        # 3. Define the structured array layout
        self.record_dtype = np.dtype([
            ('driving_freq_MHz', np.float64),
            ('att_dB', np.float64),
            ('rep_idx', np.int32),
            ('trace', np.float64, (self.N_data_total_points,))
        ])

        # 4. Initialize empty dataset for structured data
        # self.set_dataset('scan_data', np.empty(0, dtype=self.record_dtype), broadcast=True)
        self.set_dataset('scan_data', [], broadcast=True)
        
    def run(self):
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


        run_idx = 1
        N_data_predriving = int(self.t_driving_delay/self.SSA_SWT)
        N_data_postdriving = max(int((self.t_data-self.t_driving_delay)/self.SSA_SWT), 1)

        for driving_freq in list(iter(self.driving_freq)):
            for att in list(iter(self.att)):
                self.driving_init(driving_freq, att, self.phase)
                # all_data = []
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
                    for _ in range(N_data_predriving):
                        data = self.SSA.get_full_trace()
                        loc_data.extend(data)
                    self.driving_on()
                    for _ in range(N_data_postdriving):
                        data = self.SSA.get_full_trace()
                        loc_data.extend(data)
                    self.driving_off()

                    # Live plot update for the single active trace
                    trace_array = np.array(loc_data)
                    self.mutate_dataset('SSA_power', 0, trace_array)
                    self.mutate_dataset('Progress_index', 0, run_idx)

                    # Append row directly to structured dataset
                    row = np.array([(driving_freq/1e6, att, N, trace_array)], dtype=self.record_dtype)
                    self.append_to_dataset('scan_data', row)

                    time.sleep(self.t_rest)
                    run_idx += 1

                if self.recalibrate_V_tip: 
                    self.calibrate_FET()

        self.FEtip_PSU.ramp_down(0)
        self.FEtip_PSU.ramp_down_ch(self.FET_ch_fixed, 0)
        self.Valon.output_off()
        self.SSA.clear_averaging()

    @kernel
    def driving_init(self, freq, attn, phase):
        self.core.reset()
        self.core.break_realtime()
        delay(self.t_initial_delay*s) # wait for a while before starting the experiment
        self.dds_tickle.init()
        # delay(self.t_initial_delay*s) # wait for a while before starting the experiment
        t = now_mu()

        self.dds_tickle.set_att(attn*dB)
        self.dds_tickle.set(freq, phase=phase, ref_time_mu=t)

    @kernel
    def driving_on(self):
        self.core.reset()
        self.core.break_realtime()

        self.dds_tickle.sw.on()

        # # 2. Advance the RTIO timeline cursor by your desired pulse duration
        # delay(self.t_drive_duration) # e.g., self.t_drive_duration = 10 * ms

        # # 3. Turn the drive OFF at the new timeline position
        # self.d0.sw.off()
    
    @kernel
    def driving_off(self):
        self.core.reset()
        self.core.break_realtime()
        self.dds_tickle.sw.off()

