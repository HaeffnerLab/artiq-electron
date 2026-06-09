from artiq.experiment import *
from artiq.language.types import TInt32, TFloat
import numpy as np
from datetime import datetime
import time
import os
import pyvisa as visa
import tkinter as tk
from tkinter import messagebox, simpledialog

class zotino_calibration_keithley(EnvExperiment):
    def build(self): 
        self.setattr_device("core")                
        self.setattr_device("zotino0")  
        self.setattr_device("ttl18")
        
        # User Interface Arguments
        self.setattr_argument("keithley_address", StringValue("USB0::1510::8448::1243106::0::INSTR"))
        self.setattr_argument(
            "voltage_scan_range",
            Scannable(
                default=RangeScan(start=-3*V, stop=3*V, npoints=13),
                global_min=-10*V,  
                global_max=10*V,
                unit="V"
            )
        )
        self.setattr_argument("enable_measurement", BooleanValue(default=True))
        self.setattr_argument("enable_save", BooleanValue(default=True))
        self.setattr_argument("save_folder", StringValue(default="/home/electron/artiq/experiment/zotino_calibration"))
        self.setattr_argument("file_prefix", StringValue(default="PUT_YOUR_PREFIX_HERE"))
        self.setattr_argument('total_zotino_channels', NumberValue(default=32, unit='', scale=1, ndecimals=0, step=1))
        self.setattr_argument('measurement_delay_ms', NumberValue(default=100, unit='ms', scale=1, ndecimals=0, step=1))

    def prepare(self):
        """Prepare variables and host-side connections before locking the ARTIQ core."""
        # Convert Scannable into a standard Python list of voltages
        self.voltages = [v for v in self.voltage_scan_range]
        
        # Initialize empty datasets that will broadcast to the dashboard
        self.set_dataset("calib_v_set", [], broadcast=True)
        self.set_dataset("calib_v_meas", [], broadcast=True)
        
        # Initialize default arrays for all channels (uncalibrated state: slope=1, offset=0)
        num_channels = int(self.total_zotino_channels)
        self.y0 = np.zeros(num_channels)
        self.slope = np.ones(num_channels)

        self.delay_seconds = self.measurement_delay_ms / 1000.0

        if self.enable_measurement:
            self.rm = visa.ResourceManager()
            try:
                self.keithley = self.rm.open_resource(self.keithley_address)
                self.keithley.timeout = 5000 
                # Reset Keithley
                self.keithley.write("*rst; status:preset; *cls")
            except Exception as e:
                raise Exception(f"Failed to connect to Keithley: {e}")

    @kernel
    def init_zotino(self):
        """Kernel function to purely reset and initialize the Zotino."""
        self.core.reset()
        self.core.break_realtime()
        self.zotino0.init()
        
        # for i in range(int(self.total_zotino_channels)):
        #     self.zotino0.write_dac(i, 0.0)
        # self.zotino0.load()
        # print("Zotino initialized and all channels set to 0V.")
        self.core.wait_until_mu(now_mu())

    @kernel
    def set_voltage(self, channel: TInt32, voltage: TFloat):
        """Kernel function to just set the Zotino voltage safely."""
        self.core.reset()
        
        # MUST BE 150 ms! The FPGA soft-core CPU takes ~108 ms just to calculate 
        # the floating-point math for Zotino voltage offsets. 
        delay(100*us)

        self.zotino0.write_dac(channel, voltage)
        self.zotino0.load() # Instantly updates the output
    
    @kernel
    def init_voltage(self, total_channels=32):
        """Kernel function to initialize all channels to 0V at the start."""
        self.core.reset()
        self.core.break_realtime()
        self.zotino0.init()
        
        for i in range(total_channels):
            delay(500*us) # avoid RTIO underflow error
            self.zotino0.write_dac(i, 0.0)
            # delay(100*ms) # Short delay to prevent RTIO underflow
        
        self.zotino0.load()
        print("Zotino initialized and all channels set to 0V.")

    def run(self):
        """Main loop executed on the host server."""
        self.init_zotino()
        total_channels = int(self.total_zotino_channels)
        # time.sleep(5)
        self.init_voltage(total_channels=total_channels) # Ensure all channels start at 0V
        # time.sleep(5)
        # Initialize Tkinter ONCE before the loop starts
        root = tk.Tk()
        root.withdraw() 
        root.attributes('-topmost', True)
        # --- CHANGED: Use a while loop for infinite random-access ---
        while True:
            # Ask the user for the channel number using a text input dialog
            user_input = simpledialog.askstring(
                "Select Channel", 
                f"1. Connect the Keithley to the Zotino channel you want to calibrate.\n"
                f"2. Enter that channel number (0 to {total_channels - 1}) below.\n\n"
                f"Note: To recalibrate a channel, just enter its number again.\n\n"
                f"Click 'Cancel' or leave blank to finish and save all data.",
                parent=root
            )
            
            # If the user clicks Cancel or submits an empty box, exit the loop
            if user_input is None or user_input.strip() == "":
                print("\nUser finished calibration. Proceeding to save...")
                break 
            
            # Validate that the user typed a valid integer
            try:
                pin = int(user_input.strip())
                if pin < 0 or pin >= total_channels:
                    messagebox.showerror("Invalid Input", f"Channel must be between 0 and {total_channels - 1}.", parent=root)
                    continue
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid integer.", parent=root)
                continue
                
            print(f"\n--- Calibrating Channel {pin} ---")
            
            # Clear live datasets for the dashboard
            self.set_dataset("calib_v_set_live", [], broadcast=True)
            self.set_dataset("calib_v_meas_live", [], broadcast=True)
            
            # Overwrite permanent datasets for this specific pin
            self.set_dataset(f"calib_v_set_ch{pin}", [], broadcast=True)
            self.set_dataset(f"calib_v_meas_ch{pin}", [], broadcast=True)
            
            volt_measure = []

            for v in self.voltages:
                voltage_safe = float(v)  
                
                # 1. Hardware Step: Update Zotino voltage 
                self.set_voltage(pin, voltage_safe)
                
                # 2. Host Step: Decide what to do based on Auto Calibration flag
                if self.enable_measurement:
                    time.sleep(self.delay_seconds) # Wait interval to ensure voltage is stable before measurement
                    
                    reading = float(self.keithley.query("MEAS:VOLT:DC?")) 
                    volt_measure.append(reading)
                    
                    # --- UPDATE BOTH DATASETS ---
                    # Append to live datasets (for the GUI Applet)
                    self.append_to_dataset("calib_v_set_live", voltage_safe)
                    self.append_to_dataset("calib_v_meas_live", reading)
                    
                    # Append to permanent datasets (for the ARTIQ .h5 file)
                    self.append_to_dataset(f"calib_v_set_ch{pin}", voltage_safe)
                    self.append_to_dataset(f"calib_v_meas_ch{pin}", reading)

                    print(f"  CH {pin} | Set: {voltage_safe:.3f} V -> Measured: {reading:.6f} V")
                
                else:
                    print(f"  CH {pin} | Set to {voltage_safe:.3f} V. Waiting {self.delay_seconds:.2f}s...")
                    time.sleep(self.delay_seconds)
                    volt_measure.append(voltage_safe) # Dummy data to prevent crash
            
            # Safely set the pin to 0V before the user moves the wire to the next channel
            self.set_voltage(pin, 0.0)
            
            # Calculate fit immediately and store it in our arrays
            if self.enable_measurement:
                m, b = np.polyfit(self.voltages, volt_measure, 1)
                self.slope[pin] = m
                self.y0[pin] = b
                print(f"  -> Fit Complete | Slope: {m:.5f}, Offset: {b:.5f}")

        print("\nVoltage scan complete across all requested channels.")

    def analyze(self):
        """Runs automatically at the end to save data and clean up host connections."""
        if self.enable_save:
            print("Saving calibration matrix...")
            
            # 1. Ensure the folder exists
            if not os.path.exists(self.save_folder):
                os.makedirs(self.save_folder)
                
            # 2. Combine arrays exactly like your Jupyter Notebook (2 rows, 32 columns)
            fits = np.array([self.y0, self.slope])
            
            # --- NEW: Generate Unique Filename ---
            # Fetch the ARTIQ Run ID (falls back to "Standalone" if running via command line without master)
            # rid = getattr(self.scheduler, "rid", "Standalone")
            
            # Create a timestamp (e.g., "20260522_143005")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Stitch it together: prefix + timestamp + RID + .txt
            actual_filename = f"{self.file_prefix}_{timestamp}.txt"
            full_path = os.path.join(self.save_folder, actual_filename)
            
            # 3. Save the matrix to text file
            np.savetxt(full_path, fits)
            print(f"Calibration matrix saved successfully to:\n{full_path}")
        else:
            print("Save option disabled. Skipping file write.")
        
        # 4. Clean up Keithley connection
        if hasattr(self, 'keithley'):
            self.keithley.close()
            self.rm.close()