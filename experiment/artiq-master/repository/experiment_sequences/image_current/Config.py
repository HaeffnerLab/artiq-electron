from artiq.experiment import *
from edes.utils.file_handling import load_lib
from edes.experiments.devices import base


class Configuration(HasEnvironment):

    def build(self):
        self.setattr_device("ccb")
        self.setattr_argument('config_file', StringValue(default='3layer_trapping_080126'), group="Device configuration")
        self.setattr_device('scheduler') # scheduler used for RID

    def prepare(self):
        self.set_dataset('rid',self.scheduler.rid,broadcast=True)
        self.log_callback = print
        self.config = load_lib(f"/home/electron/artiq/experiment/artiq-master/repository/config_files/{self.config_file}.py")
        self.devices = self.load_devices()
    
    def load_devices(self): 
        devices = {}
        for device_name in [i for i in dir(self.config) if not i.startswith('_') and i is not None]:
            item = getattr(self.config, device_name)
            if type(item) is dict and "device" in item and "addr" in item:
                device_class = getattr(base, getattr(self.config, device_name)['device'])
                try:
                    devices[device_name] = device_class(getattr(self.config, device_name)['addr'], 
                                                **getattr(self.config, device_name).get('params', {}), log_callback=self.log_callback)
                except Exception as e:
                    self.log_callback(f">>> ERROR initializing device {device_name}: {e}")
        for device_name in devices:
            setattr(self, device_name, devices[device_name])
        return devices
    
    def load_device(self, device_name):
        if hasattr(self, device_name):
            getattr(self, device_name).close()
        item = getattr(self.config, device_name)
        if type(item) is dict and "device" in item and "addr" in item:
            device_class = getattr(base, getattr(self.config, device_name)['device'])
            try:
                self.devices[device_name] = device_class(getattr(self.config, device_name)['addr'], 
                              **getattr(self.config, device_name).get('params', {}))
                setattr(self, device_name, self.devices[device_name])
            except Exception as e:
                self.log_callback(f">>> ERROR initializing device {device_name}: {e}")

    def list_devices(self):
        return list(self.devices.keys())

    def close_all(self):
        for device in self.devices.values():
            try:
                device.close()
            except Exception as e:
                self.log_callback(f">>> ERROR closing device: {e}")

    def run(self):
        print(">>> Hello world")

