from pathlib import Path
import logging
from GettingStarted_lib.general_lib import setup_logging
import yaml
from linien_client.device import Device
from linien_client.connection import LinienClient
from linien_common.common import AutolockMode
import pickle
from time import sleep
import numpy as np
from matplotlib import pyplot as plt
from linien_common.common import ANALOG_OUT_V, Vpp
import matplotlib.dates as mdates
from datetime import datetime
from scipy.ndimage import gaussian_filter1d
from typing import Optional, List

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Interface:
    PARAMS_CONFIG_PATH = Path(__file__).parent / 'params_config.yaml'
    HARDWARE_PARAMS_PATH = Path(__file__).parent / 'hardware_params.yaml'
    LOG_FILE = Path(__file__).parent / "interface.log"

    def __init__(self, host: str, linien_port: int, username: str, password: str, ssh_port: int = 22):
        """
        Initialize the interface and connect to a specific Red Pitaya board.
        
        :param host: IP address or hostname of the Red Pitaya.
        :param linien_port: Port for the Linien server.
        :param username: SSH/Login username.
        :param password: SSH/Login password.
        :param ssh_port: SSH port (default 22).
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        setup_logging(self.logger, self.LOG_FILE)

        self.host = host
        self.linien_port = linien_port
        self.username = username
        self.password = password
        self.ssh_port = ssh_port
        
        self.device = None
        self.client = None
        
        self._connect()
        self._basic_configure()

    def _connect(self):
        """
        Connect to the Red Pitaya using the provided parameters.
        """
        try:
            self.logger.info(f"Attempting connection to {self.host}:{self.linien_port}")
            self.device = Device(host=self.host, username=self.username, password=self.password)
            self.client = LinienClient(self.device)
            self.client.connect(autostart_server=True, use_parameter_cache=True)
            self.logger.info(f"Connected to device at {self.host}")
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.host}: {e}")
            raise ConnectionError(f"Failed to connect to Linien device at {self.host}: {e}")

    def _basic_configure(self):
        self.load_hardware_parameters() #loads the external hardware parameters
        self.load_parameter_config() # loads parameters from config file

        # setup the autolock mode
        self.client.parameters.autolock_mode_preference.value = AutolockMode.ROBUST # use robust autolock mode
        self.client.parameters.autolock_determine_offset.value = False # do not determine offset automatically
        self.client.connection.root.write_registers()

    def load_hardware_parameters(self):
        """
        Load hardware (circuits) parameters from a YAML config file.
        """
        if not self.HARDWARE_PARAMS_PATH.exists():
            raise FileNotFoundError(f"Parameter config file not found: {self.HARDWARE_PARAMS_PATH}")

        with open(self.HARDWARE_PARAMS_PATH, 'r') as f:
            config = yaml.safe_load(f)

        self.hardware_parameters_summator = {}
        for name, entry in config.get("summator_circuit", {}).items():
            self.logger.debug(f"Loading hardware parameter {name}")
            self.hardware_parameters_summator[name] = HardwareParameter(
                name=entry["hardware_name"],
                RP_out=entry["RedPitaya_connected_output"],
                RP_param=entry["RedPitaya_connected_parameter"],
                gain=entry["gain"]
            )
    
    def load_parameter_config(self):
        """
        Load writeable and readable parameters from a YAML config file.
        """
        if not self.PARAMS_CONFIG_PATH.exists():
            raise FileNotFoundError(f"Parameter config file not found: {self.PARAMS_CONFIG_PATH}")

        with open(self.PARAMS_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)

        self.writeable_params = {}
        for name, entry in config.get("writeable_parameters", {}).items():
            self.writeable_params[name] = WriteableParameter(
                name=entry["hardware_name"],
                initial_value=entry["initial_value"],
                scaling=entry["scaling"],
                client = self.client
            )

        self.readable_params = {}
        for name,entry in config.get("readable_parameters", {}).items():
            self.readable_params[name] = ReadableParameter(
                name=entry['hardware_name'],
                client = self.client
            )

        self.write_registers()

    def write_registers(self):
        self.client.connection.root.write_registers()

    def check_for_changed_parameters(self):
        self.client.parameters.check_for_changed_parameters()

    def set_value(self, param_name, value):
        if param_name in self.writeable_params:
            self.writeable_params[param_name].set_value(value)
        else:
            raise KeyError(f"Parameter {param_name} not found.")
        
    def get_remote_value(self, param_name):
        if param_name in self.readable_params:
            return self.readable_params[param_name].get_remote_value()
        elif param_name in self.writeable_params:
            return self.writeable_params[param_name].get_remote_value()
        else:
            raise KeyError(f"Parameter {param_name} not found.")
        
    def wait_for_lock_status(self, should_be_locked):
        counter = 0
        while True:
            self.check_for_changed_parameters()
            to_plot = pickle.loads(self.client.parameters.to_plot.value)
            is_locked = "error_signal" in to_plot
            
            if is_locked == should_be_locked:
                self.logger.info(f"Lock status reached: {is_locked}")
                break
            
            counter += 1
            if counter > 30: # 15 seconds timeout
                raise Exception(f"Timed out waiting for lock status to be {should_be_locked}. Current keys: {list(to_plot.keys())}")
            sleep(0.5)

    def start_sweep(self):
        self.client.connection.root.start_sweep()

    def get_sweep(self):
        self.start_sweep()
        sleep(3.0 * ((2.0**self.writeable_params["sweep_speed"].get_remote_value())/(3.8e3)))
        self.check_for_changed_parameters()
        to_plot = pickle.loads(self.readable_params["sweep_signal"].get_remote_value())
        error_signal = np.array(to_plot["error_signal_1"]/(2*Vpp))
        monitor_signal = np.array(to_plot["monitor_signal"]/(2*Vpp))
        sweep_signal = {}
        sweep_center = self.writeable_params["sweep_center"].get_remote_value()
        sweep_range = self.writeable_params["sweep_amplitude"].get_remote_value()
        sweep_scan = np.linspace(sweep_center - sweep_range, sweep_center + sweep_range, len(error_signal))
        sweep_signal['x'] = sweep_scan
        sweep_signal['error_signal'] = error_signal
        sweep_signal['monitor_signal'] = monitor_signal
        return sweep_signal
    
    def plot_sweep(self):
        sweep_signal = self.get_sweep()
        fig, ax1 = plt.subplots(tight_layout=True)
        color1 = 'tab:blue'
        ax1.plot(sweep_signal['x'], sweep_signal['error_signal'], color=color1)
        ax1.axhline(y=0, color='gray')
        ax1.set_ylabel('Error Signal [V]', color=color1)
        ax1.set_xlabel('Sweep voltage [V]')
        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.plot(sweep_signal['x'], sweep_signal['monitor_signal'], color=color2)
        ax2.set_ylabel('Monitor Signal [V]', color=color2)
        plt.title('Sweep Signal')
        plt.show()

    def get_history(self):
        control_signal_history = self.readable_params["control_signal_history"].get_remote_value()
        monitor_signal_history = self.readable_params["monitor_signal_history"].get_remote_value()
        temp_dict = {}

        times_CS_unix = np.array(control_signal_history["times"]) 
        times_CS_dt = [datetime.fromtimestamp(t) for t in times_CS_unix] 
        times_CS_mpl  = mdates.date2num(times_CS_dt)   

        times_SCS_unix = np.array(control_signal_history["slow_times"]) 
        times_SCS_dt = [datetime.fromtimestamp(t) for t in times_SCS_unix] 
        times_SCS_mpl  = mdates.date2num(times_SCS_dt)   

        times_MS_unix = np.array(monitor_signal_history["times"]) 
        times_MS_dt = [datetime.fromtimestamp(t) for t in times_MS_unix] 
        times_MS_mpl  = mdates.date2num(times_MS_dt)   

        temp_dict['fast_control_values'] = np.array(control_signal_history['values']) / ( 2 * Vpp )
        temp_dict['fast_control_times_dt'] = times_CS_dt
        temp_dict['fast_control_times_mpl'] = times_CS_mpl
        
        sigma = 5
        dt = times_CS_unix[-1] - times_CS_unix[-2] if len(times_CS_unix) > 1 else 1.0
        d_control_history = np.diff(gaussian_filter1d(temp_dict['fast_control_values'], sigma=sigma))/dt
        temp_dict['d_fast_control_values'] = d_control_history

        temp_dict['slow_control_values'] = np.array(control_signal_history['slow_values']) * ANALOG_OUT_V
        temp_dict['slow_control_times_dt'] = times_SCS_dt
        temp_dict['slow_control_times_mpl'] = times_SCS_mpl
        
        dt_slow = times_SCS_unix[-1] - times_SCS_unix[-2] if len(times_SCS_unix) > 1 else 1.0
        d_slow_control_history = np.diff(gaussian_filter1d(temp_dict['slow_control_values'], sigma = sigma))/dt_slow
        temp_dict['d_slow_control_values'] = d_slow_control_history
        
        temp_dict['monitor_values'] = np.array(monitor_signal_history['values']) / ( 2 * Vpp )
        temp_dict['monitor_times_dt'] = times_MS_dt
        temp_dict['monitor_times_mpl'] = times_MS_mpl
        
        self.history = temp_dict
        return temp_dict


# Helper Classes (ReadableParameter, WriteableParameter, HardwareParameter) remain the same
class ReadableParameter:
    def __init__(self, name, client):
        self.name = name
        self.client = client

    def get_attribute(self):
        return getattr(self.client.parameters, self.name)
    
    def get_remote_value(self):
        self.client.parameters.check_for_changed_parameters()
        return self.get_attribute().value

class WriteableParameter(ReadableParameter):
    def __init__(self, name, initial_value, scaling, client):
        super().__init__(name, client)
        self.value = initial_value
        self.scaling = scaling
        self.initialize_parameter()

    def initialize_parameter(self):
        val = self.value * self.scaling if self.scaling else self.value
        self.get_attribute().value = val

    def set_value(self, value):
        self.value = value
        val = self.value * self.scaling if self.scaling else self.value
        self.get_attribute().value = val
        self.client.connection.root.write_registers()

    def get_remote_value(self):
        self.client.parameters.check_for_changed_parameters()
        val = self.get_attribute().value
        return val / self.scaling if self.scaling else val
    
class HardwareParameter:
    def __init__(self, name, RP_out, RP_param, gain):
        self.hardware_name = name
        self.RedPitaya_connected_output = RP_out
        self.RedPitaya_connected_parameter = RP_param
        self.gain = gain