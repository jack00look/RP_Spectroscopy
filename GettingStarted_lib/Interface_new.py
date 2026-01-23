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
from GettingStarted_lib.grafana_manager import GrafanaManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Interface():
    """
    This class is the interface between the user and the Red Pitaya.
    It contains all the low level methods to communicate with the device.
    """

    def __init__(self, board):
        self.board = board
        base_path = Path(__file__).parent / "boards"
        self.parameters_configuration_path = base_path / f"{self.board['name']}_parameters.yaml"
        self.hardware_parameters_path = base_path / f"{self.board['name']}_circuits_parameters.yaml"
        self.log_file = base_path / f"logs/{self.board['name']}_interface.log"
        self.logger = logging.getLogger(self.__class__.__name__)
        setup_logging(self.logger, self.log_file)

        self.device = None
        self.client = None
        self._connect()
        self._basic_configure()

    def _connect(self):
        """
        Connects to the RedPitaya
        """

        try:
            self.logger.info(f"Attempting connection via {self.board['name']} address ({self.board['ip']}:{self.board['linien_port']})")
            self.device = Device(host=self.board['ip'], username=self.board['username'], password=self.board['password'])
            self.client = LinienClient(self.device)
            self.client.connect(autostart_server=True, use_parameter_cache=True)
            self.logger.info(f"Connected to device {self.board['name']}")
            return
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.board['name']}: {e}")
            raise ConnectionError(f"Failed to connect to {self.board['name']}.")
    
    def _basic_configure(self):
        """
        Configures the RedPitaya with the basic configuration (this will get updated each time the
        program is turned off).
        """

        self.load_hardware_parameters()

        self.load_parameter_config()

        # setup the autolock mode
        self.client.parameters.autolock_mode_preference.value = AutolockMode.ROBUST # use robust autolock mode
        self.client.parameters.autolock_determine_offset.value = False # do not determine offset automatically
        self.client.connection.root.write_registers()

    def load_hardware_parameters(self):
        """
        Load hardware (circuits) parameters from a YAML config file in order to manage
        operations that include gains in the circuits used.
        """

        if not self.hardware_parameters_path.exists():
            raise FileNotFoundError(f"Hardware parameters file not found: {self.hardware_parameters_path}")

        with open(self.hardware_parameters_path, 'r') as f:
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
        Load writeable and readable parameters from a YAML config file and create corresponding parameter objects. It also
        writes the initial values of the writeable parameters to the device only once at the end of the loading procedure.   
        """
        
        if not self.parameters_configuration_path.exists():
            raise FileNotFoundError(f"Parameter config file not found: {self.parameters_configuration_path}")

        with open(self.parameters_configuration_path, 'r') as f:
            config = yaml.safe_load(f)

        self.writeable_params = {}
        for name, entry in config.get("writeable_parameters", {}).items():
            self.logger.debug(f"Loading writeable parameter {name} with hardware name {entry['hardware_name']}, initial value {entry['initial_value']}, scaling {entry['scaling']}")
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
        """
        Sets the value of a writeable parameter.
        """
        if param_name in self.writeable_params:
            self.writeable_params[param_name].set_value(value)
            self.write_registers() #actually it already does this in the other set_value
            self.logger.debug(f"Set parameter {param_name} to value {value}")
        else:
            self.logger.error(f"Parameter {param_name} not found among writeable parameters.")
            raise KeyError(f"Parameter {param_name} not found among writeable parameters.")
        
    def get_remote_value(self, param_name):
        """
        Gets the remote value of a parameter.
        """
        if param_name in self.readable_params:
            value = self.readable_params[param_name].get_remote_value()
            self.logger.debug(f"Got remote value {value} for parameter {param_name}")
            return value
        elif param_name in self.writeable_params:
            value = self.writeable_params[param_name].get_remote_value()
            self.logger.debug(f"Got remote value {value} for parameter {param_name}")
            return value
        else:
            self.logger.error(f"Parameter {param_name} not found among both readable and writeable parameters.")
            raise KeyError(f"Parameter {param_name} not found among both readable and writeable parameters.")
        
    def wait_for_lock_status(self, should_be_locked):
        """Wait until the laser reaches the desired lock state."""
        counter = 0
        while True:
            print("checking lock status...")
            self.logger.info("checking lock status...")
            to_plot = pickle.loads(self.client.parameters.to_plot.value)

            #print(f"to_plot keys: {list(to_plot.keys())}")

            is_locked = "error_signal" in to_plot

            if is_locked == should_be_locked:
                break

            counter += 1
            if counter > 10:
                raise Exception("waited too long")

            sleep(1)

    def start_sweep(self):
        self.client.connection.root.start_sweep()

    def get_sweep(self):
        """
        Neglectiing the mixing channel for simplicity.
        """
        self.start_sweep()
        #print("Sweep_speed ", self.writeable_params["sweep_speed"].get_remote_value())
        sleep(5.0 * ((2.0**self.writeable_params["sweep_speed"].get_remote_value())/(3.8e3))) #wait 3 sweep periods
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
        ax1.tick_params(axis='y', colors=color1)
        ax1.spines['left'].set_color(color1)
        ax1.set_xlabel('Sweep voltage [V]')

        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.plot(sweep_signal['x'], sweep_signal['monitor_signal'], color=color2)
        ax2.set_ylabel('Monitor Signal [V]', color=color2)
        ax2.tick_params(axis='y', colors=color2)
        ax2.spines['right'].set_color(color2)
        ax2.spines['left'].set_visible(False)

        plt.title(f'Sweep Signal (centered at {(self.writeable_params["big_offset"].get_remote_value() * ANALOG_OUT_V * self.writeable_params["big_offset"].scaling):.2g}V)')
        plt.show()

    def adjust_vertical_offset(self):
        actual_offset = self.writeable_params["offset_a"].get_remote_value()
        print(f"Actual offset_a: {actual_offset}")
        offset_variation = float(input("Enter offset variation to apply: "))
        new_offset = actual_offset + offset_variation
        self.set_value("offset_a", new_offset)
        print(f"New offset_a set to: {new_offset}")

    def get_history(self):
        control_signal_history = self.readable_params["control_signal_history"].get_remote_value()
        monitor_signal_history = self.readable_params["monitor_signal_history"].get_remote_value()
        temp_dict = {}

        # ---- Time conversion ----
            # Control Signal
        times_CS_unix = np.array(control_signal_history["times"]) #UNIX
        times_CS_dt = [datetime.fromtimestamp(t) for t in times_CS_unix] #datetime
        times_CS_mpl  = mdates.date2num(times_CS_dt)   #Matplotlib dates
            # Slow CS
        times_SCS_unix = np.array(control_signal_history["slow_times"]) #UNIX
        times_SCS_dt = [datetime.fromtimestamp(t) for t in times_SCS_unix] #datetime
        times_SCS_mpl  = mdates.date2num(times_SCS_dt)   #Matplotlib dates
            # Monitor Signal
        times_MS_unix = np.array(monitor_signal_history["times"]) #UNIX
        times_MS_dt = [datetime.fromtimestamp(t) for t in times_MS_unix] #datetime
        times_MS_mpl  = mdates.date2num(times_MS_dt)   #Matplotlib dates
        # ----

        temp_dict['fast_control_values'] = np.array(control_signal_history['values']) / ( 2 * Vpp )
        temp_dict['fast_control_times_unix'] = times_CS_unix
        temp_dict['fast_control_times_dt'] = times_CS_dt
        temp_dict['fast_control_times_mpl'] = times_CS_mpl
        #evaluation of the derivateive of the control signal
        sigma = 5
        dt = temp_dict['fast_control_times_unix'][-1] - temp_dict['fast_control_times_unix'][-2]
        d_control_history = np.diff(gaussian_filter1d(temp_dict['fast_control_values'], sigma=sigma))/dt
        temp_dict['d_fast_control_values'] = d_control_history

        temp_dict['slow_control_values'] = np.array(control_signal_history['slow_values']) * ANALOG_OUT_V
        temp_dict['slow_control_times_unix'] = times_SCS_unix
        temp_dict['slow_control_times_dt'] = times_SCS_dt
        temp_dict['slow_control_times_mpl'] = times_SCS_mpl
        #evaluation of the derivateive of the slow control signal
        dt_slow = temp_dict['slow_control_times_unix'][-1] - temp_dict['slow_control_times_unix'][-2]
        d_slow_control_history = np.diff(gaussian_filter1d(temp_dict['slow_control_values'], sigma = sigma))/dt_slow
        temp_dict['d_slow_control_values'] = d_slow_control_history
        
        temp_dict['monitor_values'] = np.array(monitor_signal_history['values']) / ( 2 * Vpp )
        temp_dict['monitor_times_unix'] = times_MS_unix
        temp_dict['monitor_times_dt'] = times_MS_dt
        temp_dict['monitor_times_mpl'] = times_MS_mpl
        
        self.history = temp_dict

        return temp_dict


    def set_debug_mode(self):
        self.logger.setLevel(logging.DEBUG)
        for handler in self.logger.handlers:
            handler.setLevel(logging.DEBUG)
        
    def unset_debug_mode(self):
        self.logger.setLevel(logging.INFO)
        for handler in self.logger.handlers:
            handler.setLevel(logging.INFO)


class ReadableParameter:
    def __init__(self, name, client):
        self.name = name
        self.remote_value = None
        self.client = client

    def get_attribute(self):
        attribute = getattr(self.client.parameters, self.name)
        return attribute
    
    def get_remote_value(self):
        self.client.parameters.check_for_changed_parameters()
        value = self.get_attribute().value
        self.value = value
        return value

class WriteableParameter(ReadableParameter):
    def __init__(self, name, initial_value, scaling, client):
        super().__init__(name, client) #Writeable parameters are also readable parameters so they inherits all the attributes of the parent class
        self.value = initial_value
        self.scaling = scaling
        self.initialize_parameter()

    def initialize_parameter(self):
        '''
        The initialization is faster then using set_value for each parameter because it runs
        only at the end the write_registers().
        '''
        if self.scaling is not None:
            if self.scaling == 1:
                self.get_attribute().value = self.value
            else:
                self.get_attribute().value = self.value * self.scaling
        else:
            self.get_attribute().value = self.value

    def set_value(self, value):
        self.value = value
        if self.scaling is not None:
            if self.scaling == 1:
                self.get_attribute().value = value
            else:
                self.get_attribute().value = self.value * self.scaling
        else:
            self.get_attribute().value = self.value

        self.client.connection.root.write_registers()

    def get_remote_value(self):
        self.client.parameters.check_for_changed_parameters()
        if self.scaling is not None:
            value = self.get_attribute().value / self.scaling
        else:
            value = self.get_attribute().value
        self.value = value
        return value
    
class HardwareParameter:
    def __init__(self, name, RP_out, RP_param, gain):
        self.hardware_name = name
        self.RedPitaya_connected_output = RP_out
        self.RedPitaya_connected_parameter = RP_param
        self.gain = gain