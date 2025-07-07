from artiq.language import EnvExperiment, kernel, dB, now_mu, MHz, us, ms, delay, s
from artiq.coredevice.ad9910 import PHASE_MODE_TRACKING
from artiq.experiment import NumberValue
import time

class TriggeredPulse(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_argument('attenuation',NumberValue(default=10,unit='dB',scale=1,ndecimals=0,step=1)) #
        self.setattr_argument('frequency',NumberValue(default=100,unit='MHz',scale=1,ndecimals=3),tooltip='[MHz]') # 
        self.setattr_argument('duration',NumberValue(default=1,unit='ms',scale=1,step=0.01,ndecimals=2), tooltip='TTL on+off time [ms]') # 
        self.setattr_argument('repetition',NumberValue(default=10,scale=1,step=1,min=1,ndecimals=0,type='int'))
        self.setattr_argument('delay_time', NumberValue(default=1,scale=1,unit='ms',step=0.01,ndecimals=2), tooltip='Delay between each pulse [ms]')
        self.setattr_argument('TTL_channel',NumberValue(default=12,scale=1,step=1,min=0,max=23,ndecimals=0,type='int'))
        self.setattr_argument('DDS_channel',NumberValue(default=0,scale=1,step=1,min=0,max=3,ndecimals=0,type='int'))
        self.setattr_device('scheduler') # scheduler used

    def prepare(self):
        self.d0 = self.get_device(f"urukul0_ch{self.DDS_channel}")
        self.t = self.get_device(f"ttl{self.TTL_channel}")
        self.run_outputting()
        time.sleep((self.duration+self.delay_time)/1000*self.repetition)

    @kernel
    def run_outputting(self):
        self.core.reset()
        self.core.break_realtime()
        delay(500*ms)
        self.d0.cpld.init()
        self.d0.init()
        
        # # This calibration needs to be done only once to find good values.
        # # The rest is happening at each future init() of the DDS.
        # if self.d0.sync_delay_seed == -1:
        #     delay(100*us)
        #     d0, w0 = self.d0.tune_sync_delay()
        #     t0 = self.d0.tune_io_update_delay()
        #     d1, w1 = self.d1.tune_sync_delay()
        #     t1 = self.d0.tune_io_update_delay()
        #     d2, w2 = self.d2.tune_sync_delay()
        #     t2 = self.d0.tune_io_update_delay()
        #     d3, w3 = self.d3.tune_sync_delay()
        #     t3 = self.d0.tune_io_update_delay()
        #     print("sync_delay_seed", [d0, d1, d2, d3])
        #     print("io_update_delay", [t0, t1, t2, t3])
        #     return
        
        # self.d0.set_phase_mode(PHASE_MODE_TRACKING)
        # self.d1.set_phase_mode(PHASE_MODE_TRACKING)
        # self.d2.set_phase_mode(PHASE_MODE_TRACKING)
        # self.d3.set_phase_mode(PHASE_MODE_TRACKING)

        self.d0.set_att(self.attenuation*dB)
        t = now_mu()
        self.d0.set(self.frequency*MHz, phase=0., ref_time_mu=t)

        for _ in range(self.repetition):
            
            # self.d1.set(40*MHz, phase=0., ref_time_mu=t)
            # self.d2.set(40*MHz, phase=0., ref_time_mu=t)
            # self.d3.set(40*MHz, phase=0., ref_time_mu=t)

            self.t.on()
            
            self.d0.sw.on()

            self.t.pulse(self.duration*ms)
            # self.d1.sw.on()
            # self.d2.sw.on()
            # self.d3.sw.on()

            delay(self.duration*ms)
            # delay(2*s)
            # self.d1.set(200*MHz)
            # self.d2.set(250*MHz)
            # self.d3.set(20*MHz)
            # delay(2*s)
            # self.d1.set(80*MHz, ref_time_mu=t)
            # self.d2.set(80*MHz, ref_time_mu=t)
            # self.d3.set(80*MHz, ref_time_mu=t)

            #delay(2*us)
            self.t.off()
            self.d0.sw.off()

            delay(self.delay_time*ms)
        self.t.off()
        self.d0.sw.off()
    
    @kernel
    def run(self):
        print(">>> Test Ended")
        # self.d1.sw.off()
        # self.d2.sw.off()
        # self.d3.sw.off()
       

        
        