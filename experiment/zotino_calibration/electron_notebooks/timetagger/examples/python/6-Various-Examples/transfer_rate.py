import numpy as np
from time import sleep, time
from TimeTagger import ChannelEdge, CustomMeasurement, createTimeTagger, getVersion, freeTimeTagger


class TransferRate(CustomMeasurement):
    def __init__(self, tagger, channels):
        CustomMeasurement.__init__(self, tagger)

        for channel in channels:
            self.register_channel(channel)

        self.clear_impl()
        self.finalize_init()

    def __del__(self):
        self.stop()

    def getData(self):
        with self.mutex:
            return self.counter

    def clear_impl(self):
        # the lock is already acquired
        self.counter = 0

    def process(self, incoming_tags, begin_time, end_time):
        self.counter = self.counter + incoming_tags.size


def probe_transfer_rate(tagger):
    [tagger.setTestSignal(i, False) for i in tagger.getChannelList()]
    [tagger.setInputDelay(i, 0) for i in tagger.getChannelList()]
    channels = tagger.getChannelList(ChannelEdge.Rising)[:3]

    tagger.setTestSignal(channels, True)

    if tagger.getModel() == 'Time Tagger Ultra':
        # default divider: 63 = 800 kHz
        min_rate = 100e6
        default_divider = 63
    else:
        # default divider: 74 ~ 800 kHz
        min_rate = 10e6
        default_divider = 74

    divider = int(default_divider * 800e3 / min_rate * len(channels))
    assert divider >= 1, "Test signal cannot reach the required data rate for the given number of channels."

    tagger.setTestSignalDivider(divider)

    time_integrate = 1  # s
    avgs = 10

    transfer_rate = TransferRate(tagger, channels)
    tagger.sync()
    tagger.clearOverflows()

    transfer_rates = np.zeros(avgs)

    start_counter = transfer_rate.getData()
    start_time = time()
    for i in range(avgs):
        sleep(time_integrate)
        stop_counter = transfer_rate.getData()
        stop_time = time()
        transfer_rates[i] = (stop_counter-start_counter) / (stop_time - start_time)
        start_counter = stop_counter
        start_time = stop_time

    transfer_rates_sorted = np.sort(transfer_rates)

    overflows = tagger.getOverflows()

    if overflows == 0:
        print("WARNING - test signal input test signal rate too low.")

    # take the median as the data rate
    data = {'transfer_rate': transfer_rates_sorted[avgs//2],
            'transfer_rates': transfer_rates,
            'overflows': overflows,
            'channels': channels,
            }

    tagger.setTestSignalDivider(default_divider)
    return data


if __name__ == '__main__':
    print("Time Tagger Software Version {}".format(getVersion()))
    tagger = createTimeTagger()
    print("Model:    {}".format(tagger.getModel()))
    print("Serial:   {}".format(tagger.getSerial()))
    print("Hardware: {}".format(tagger.getPcbVersion()))
    try:
        import cpuinfo
        print("CPU:      {}".format(cpuinfo.get_cpu_info()['brand_raw']))
    except:
        print("\nINFO: Module cpuinfo not found - please install it via pip install py-cpuinfo to display the CPU information here.")

    print("\nTest Maximum transfer data rate with three active channels\n\nPlease wait...")
    result = probe_transfer_rate(tagger)
    print("\nMeasured transfer rates:")
    for i, rate in enumerate(result['transfer_rates']):
        print("test run {:2d}: transfer rate {:.1f} MTags/s".format(i+1, rate/1e6))
    freeTimeTagger(tagger)
