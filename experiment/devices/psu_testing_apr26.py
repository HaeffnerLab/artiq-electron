import pyvisa
from time import sleep
from base import RigolDP832A

PSU = RigolDP832A('USB0::6833::3601::DP8B260200018::0::INSTR')
PSU.set_voltage(3, 1)
PSU.output_on(3)
sleep(5)
voltage = PSU.measure_voltage(3)
print(voltage)
PSU.output_off(3)
PSU.close()