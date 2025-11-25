from linien_client.device import Device
from linien_client.connection import LinienClient
from linien_common.common import  MHz, Vpp, ANALOG_OUT_V,AutolockMode
from spectroscopy_lib.main import setup_logging

import sys
import logging
from pathlib import Path
import numpy as np
import pickle
import time
import threading
import rpyc
import yaml
from rpyc.utils.classic import obtain

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class NewDataListener:
    def __init__(self,name,is_writeable):
        self.new_data_event = threading.Event()
        self._writeable = is_writeable
        self._name = name
        self.value = None
        self.written_value = None
        

    def notify_new_data(self,value=None):
        logger.info(f"New data notification for parameter {self._name}: value={value}, writeable={self._writeable}")
        if not(self._writeable):
            #print('parameter ',self._name,' is not writeable')
            #print('value is ',value)
            if value!= self.value:
                self.new_data_event.set()
                self.value = value
        elif self._writeable:
            #print('parameter ',self._name,' is writeable')
            #print('value is: ',value)
            if value == self.written_value:
                self.new_data_event.set()
                self.value = value

    def set_written_value(self,value):
        self.written_value = value

    def get_value(self):
        return self.value
    
    def set_writeable(self,is_writeable):
        self._writeable = is_writeable

    def reset_new_data_event(self):
        self.new_data_event.clear()

    def is_new_data_available(self):
        return self.new_data_event.is_set()

class ParameterImplementationBasic:
    def __init__(self, name : str, client : LinienClient):
        self._name = name
        self._client = client
        self._writeable = False
        self.new_data_listener = NewDataListener(self._name,self._writeable)
        self.remote_value = None
        self.get_local_parameter().add_callback(self.new_data_listener.notify_new_data)

    def write_parameter(self):
        self._client.connection.root.write_registers()

    def wait_for_update(self, timeout : float = 10.0):
        """
        Waits until the parameter value is updated from the remote side.
        This is useful to ensure that the value is set correctly before proceeding.
        """
        self.new_data_listener.reset_new_data_event()
        #print('new data event reset')
        time_0 = time.time()
        while not self.new_data_listener.is_new_data_available():
            self._client.parameters.check_for_changed_parameters()
            #print('no update yet')
            if (time.time() - time_0) > timeout:
                raise TimeoutError(f"Timeout while waiting for parameter {self._name} to update.")
            time.sleep(0.1)  # Sleep to avoid busy waiting
        self.remote_value = obtain(self.new_data_listener.get_value())

    def get_raw_value(self):
        return self.remote_value

    def get_local_parameter(self):
        local_parameter = getattr(self._client.parameters, self._name)
        if local_parameter is None:
            raise ValueError(f"Parameter {self._name} does not exist in the client parameters.")
        return local_parameter

class ParameterImplementationWriteable(ParameterImplementationBasic):

    def __init__(self, name : str, start_value : float, conversion : float, client : LinienClient):
        super().__init__(name, client)
        self._writeable = True
        self.new_data_listener.set_writeable(self._writeable)
        self.value = start_value
        self._conversion = conversion
        self._initialize_parameter()

    def _initialize_parameter(self):
        if self._conversion is not None:
            self.get_local_parameter().value = self.value * self._conversion
            self.new_data_listener.set_written_value(self.value * self._conversion)
        else:
            self.get_local_parameter().value = self.value
            self.new_data_listener.set_written_value(self.value)

        self.write_parameter()
    
    def set_value(self, value : float):
        #print('setting ',self._name,' to ',value)
        if self.value != value:
            #print('new value detected')
            self.value = value
            if self._conversion is not None:
                self.get_local_parameter().value = value * self._conversion
                if self._conversion == 1.:
                    self.new_data_listener.set_written_value(int(value))
                else:
                    self.new_data_listener.set_written_value(self.value * self._conversion)
            else:
                self.get_local_parameter().value = self.value
                self.new_data_listener.set_written_value(self.value)

            #print('new value written')
        #else:
            #print('no new value detected')
        self.write_parameter()

    def get_physical_value(self):
        #print('getting phisical value')
        if self.remote_value is None:
            return None
        if self._conversion is not None:
            if self._conversion == 1.:
                return int(self.remote_value)
            else:
                return self.remote_value/self._conversion
        else:
            return self.remote_value
    
def wait_for_multiple_parameters_update(client, parameters_list : list[ParameterImplementationBasic]):
    update_finished = False
    for param in parameters_list:
        param.new_data_listener.reset_new_data_event()
    while not update_finished:
        client.parameters.check_for_changed_parameters()
        #for param in parameters_list:
            #print(param._name, '   ',param.new_data_listener._writeable,'   ',param.new_data_listener.is_new_data_available())
        update_finished = all(param.new_data_listener.is_new_data_available() for param in parameters_list)
        if not update_finished:
            time.sleep(0.1)
    for param in parameters_list:
        param.remote_value = obtain(param.new_data_listener.get_value())




class LinienHardwareInterface:
    CONNECT_CONFIG_PATH = Path(__file__).parent / 'linien_connect_config.yaml' #all three will already be class elements if written like that
    PARAMS_CONFIG_PATH = Path(__file__).parent / 'linien_params_config.yaml'
    LOG_FILE = Path(__file__).parent / "linien_hardware_interface.log"


    def __init__(self):

        self.logger = logging.getLogger(self.__class__.__name__)
        setup_logging(self.logger, self.LOG_FILE)

        self._load_config()

        self.device = None
        self.client = None
        self._connect()
        self._basic_configure()

    def _load_config(self):

        if not self.CONNECT_CONFIG_PATH.exists():
            self.logger.error(f"Configuration file {self.CONNECT_CONFIG_PATH} does not exist.")
            raise FileNotFoundError(f"Configuration file {self.CONNECT_CONFIG_PATH} does not exist.")

        with open(self.CONNECT_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)

        self.DEVICES = {}
        for device in config.get("devices", []):
            self.DEVICES[device["name"]] = {
                "ip": device["ip"],
                "linien_port": device["linien_port"],
                "ssh_port": device["ssh_port"]
            }
            self.logger.debug(f"Loaded device {device['name']} with IP {device['ip']}, Linien port {device['linien_port']}, SSH port {device['ssh_port']}")
        self.USERNAME = config["username"]
        self.PASSWORD = config["password"]

        self.logger.info(f"Configuration loaded from {self.CONNECT_CONFIG_PATH}:\n")
        self.logger.debug(f"Username: {self.USERNAME}")

    def _connect(self):
        """Try connecting to Red Pitaya using multiple fallback addresses."""

        for name, device_info in self.DEVICES.items():
            try:
                self.logger.info(f"Attempting connection via {name} address ({device_info['ip']}:{device_info['linien_port']})")
                self.device = Device(host=device_info['ip'], username=self.USERNAME, password=self.PASSWORD)
                self.client = LinienClient(self.device)
                self.client.connect(autostart_server=True, use_parameter_cache=False)
                self.logger.info(f"Connected to device via {name} address")

                return
            except Exception as e:
                self.logger.warning(f"Failed to connect via {name} address: {e}")

        self.logger.error("No network connection found.")
        raise ConnectionError("Failed to connect to Linien device via all known methods.")
    
    def load_parameter_config(self):
        """
        Load writeable and readable parameters from a YAML config file.

        Args:
            config_path (str or Path): Path to the YAML file.
            client: The hardware interface client.

        Returns:
            Tuple (writeable_params, readable_params) as dictionaries.
        """
        
        if not self.PARAMS_CONFIG_PATH.exists():
            raise FileNotFoundError(f"Parameter config file not found: {self.PARAMS_CONFIG_PATH}")

        with open(self.PARAMS_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)

        self.writeable_params = {}
        for name, entry in config.get("writeable_parameters", {}).items():
            self.logger.debug(f"Loading writeable parameter {name} with hardware name {entry['hardware_name']}, initial value {entry['initial_value']}, scaling {entry['scaling']}")
            self.writeable_params[name] = ParameterImplementationWriteable(
                entry["hardware_name"],
                entry["initial_value"],
                entry["scaling"],
                self.client
            )

        self.readable_params = {}
        for name,entry in config.get("readable_parameters", {}).items():
            self.readable_params[name] = ParameterImplementationBasic(entry['hardware_name'], self.client)
        
    def _basic_configure(self):

        self.load_parameter_config()
        self.set_debug_mode()
        wait_for_multiple_parameters_update(self.client, list(self.writeable_params.values()) + list(self.readable_params.values()))

        # setup the autolock mode
        self.client.parameters.autolock_mode_preference.value = AutolockMode.ROBUST # use robust autolock mode
        self.client.parameters.autolock_determine_offset.value = False # do not determine offset automatically
        self.client.connection.root.write_registers()

    def get_param(self, param_name):
        if param_name not in self.writeable_params and param_name not in self.readable_params:
            raise ValueError(f"Parameter {param_name} does not exist.")
        if param_name in self.writeable_params:
            return self.writeable_params[param_name].get_physical_value()
        if param_name in self.readable_params:
            return self.readable_params[param_name].get_raw_value()
    
    def set_param(self, param_name, value):
        #print('--- Entered in set_param ---')
        #print('setting param ',param_name,' to value ',value)
        if param_name not in self.writeable_params:
            raise ValueError(f"Parameter {param_name} does not exist.")
        physical_value = self.writeable_params[param_name].get_physical_value()
        #print('physical value is ',physical_value, ' type is ',type(physical_value))
        #print('value is ',value, ' type is ',type(value))
        #print('np.abs((value - physical_value)/value)', np.abs((value - physical_value)/value))
        if physical_value is None:
            #print('yet no physical value')
            self.writeable_params[param_name].set_value(value)
            self.writeable_params[param_name].wait_for_update()
        if np.abs((value - physical_value)/value) > 0.0001:
            #print('new value')
            self.writeable_params[param_name].set_value(value)
            self.writeable_params[param_name].wait_for_update()
        #else:
            #print('no value to update')

    def get_pid(self):
        """
        Returns the PID parameters as a dictionary.
        """
        pid_params = {
            "p": self.writeable_params['pid_p'].get_physical_value(),
            "i": self.writeable_params['pid_i'].get_physical_value(),
            "d": self.writeable_params['pid_d'].get_physical_value(),
            "slow_strength": self.parameters_dict['pid_slow_strength'].get_remote_value()
        }
        self.logger.debug(f"PID parameters: {pid_params}")
        return pid_params
    
    def set_pid(self, p = None, i = None, d = None, slow_strength = None):
        """
        Sets the PID parameters.
        If a parameter is None, it will not be changed.
        """
        if p is not None:
            self.writeable_params['pid_p'].set_value(p)
            self.logger.debug(f"Setting PID P to {p}")
        if i is not None:
            self.writeable_params['pid_i'].set_value(i)
            self.logger.debug(f"Setting PID I to {i}")
        if d is not None:
            self.writeable_params['pid_d'].set_value(d)
            self.logger.debug(f"Setting PID D to {d}")
        if slow_strength is not None:
            self.writeable_params['pid_slow_strength'].set_value(slow_strength)
            self.logger.debug(f"Setting PID slow strength to {slow_strength}")

        wait_for_multiple_parameters_update(self.client, [
            self.writeable_params['pid_p'],
            self.writeable_params['pid_i'],
            self.writeable_params['pid_d'],
            self.writeable_params['pid_slow_strength']
        ])


    def get_filter_frequency(self):
        filter_1_frequency = self.writeable_params['filter_1_frequency'].get_remote_value()
        filter_2_frequency = self.writeable_params['filter_2_frequency'].get_remote_value()
        if filter_1_frequency != filter_2_frequency:
            self.logger.warning("Filter frequencies for filter 1 ({:.2f}) and filter 2 ({:.2f}) are not equal. This may lead to unexpected behavior.".format(filter_1_frequency, filter_2_frequency))
        self.logger.debug(f"Filter 1 frequency: {filter_1_frequency} Hz, Filter 2 frequency: {filter_2_frequency} Hz")
        return filter_1_frequency
    
    def set_filter_frequency(self, frequency):
        self.writeable_params['filter_1_frequency'].set_value(frequency)
        self.writeable_params['filter_2_frequency'].set_value(frequency)
        wait_for_multiple_parameters_update(self.client, [
            self.writeable_params['filter_1_frequency'],
            self.writeable_params['filter_2_frequency']
        ])

    def set_sweep_parameters(self, center : float = 0.0, amplitude : float = 0.9, speed : float = 1):
        """
        Sets the sweep parameters.
        :param center: Center frequency of the sweep in V.
        :param amplitude: Amplitude of the sweep in V.
        :param speed: Speed of the sweep in Hz, will be rounded to closest available value.
        """
        sweep_speed_available = np.linspace(0,15,16)
        closest_speed = min(sweep_speed_available, key=lambda x: abs(3800/2**x - speed))
        self.writeable_params['sweep_center'].set_value(center)
        print(f"Setting sweep center to {center} V")
        self.writeable_params['sweep_amplitude'].set_value(amplitude)
        print(f"Setting sweep amplitude to {amplitude} V")
        self.writeable_params['sweep_speed'].set_value(closest_speed)
        print(f"Setting sweep speed to {3800/2**closest_speed} Hz (closest available speed: {closest_speed})")
        wait_for_multiple_parameters_update(self.client, [
            self.writeable_params['sweep_center'],
            self.writeable_params['sweep_amplitude'],
            self.writeable_params['sweep_speed']
        ])
        self.logger.info("Sweep parameters set: center={:.2f} V, amplitude={:.2f} V, speed={:.2f} Hz".format(center, amplitude, 3800/2**closest_speed))

    def start_sweep(self):
        self.client.connection.root.start_sweep()

    def get_sweep(self):
        self.start_sweep()
        self.readable_params['sweep_signal'].wait_for_update()
        self.logger.debug("Sweep signal received from server.")
        to_plot = pickle.loads(self.readable_params['sweep_signal'].get_raw_value())
        dual_channel = bool(self.writeable_params['dual_channel'].get_raw_value())
        error_signal_strength = None
        if dual_channel:
            mixing = self.client.parameters.channel_mixing.value
            error_signal_1 = np.array(to_plot['error_signal_1'])/(2*Vpp)
            error_signal_2 = np.array(to_plot['error_signal_2'])/(2*Vpp)
            error_signal = ((error_signal_1*(127-mixing) + error_signal_2*(127+mixing))/254)
        else:
            error_signal = np.array(to_plot['error_signal_1'])/(2*Vpp)
            if 'error_signal_1_quadrature' in to_plot:
                error_signal_quadrature = np.array(to_plot['error_signal_1_quadrature'])/(2*Vpp)
                error_signal_strength = np.sqrt(error_signal**2 + error_signal_quadrature**2)
        sweep_center = self.writeable_params['sweep_center'].get_raw_value()
        sweep_range = self.writeable_params['sweep_amplitude'].get_raw_value()
        sweep_scan = np.linspace(sweep_center - sweep_range, sweep_center + sweep_range, len(error_signal))
        sweep_signal = {}
        sweep_signal['x'] = sweep_scan
        sweep_signal['y'] = error_signal
        if error_signal_strength is not None:
            sweep_signal['s'] = error_signal_strength
        return sweep_signal
    
    def wait_for_lock_status(self, should_be_locked):
        """A helper function that waits until the laser is locked or unlocked."""
        counter = 0
        while True:
            self.readable_params['sweep_signal'].wait_for_update()
            print("checking lock status...")
            to_plot = pickle.loads(self.readable_params['sweep_signal'].get_raw_value())

            print(f"to_plot keys: {list(to_plot.keys())}")

            is_locked = "error_signal" in to_plot

            if is_locked == should_be_locked:
                break

            counter += 1
            if counter > 50:
                raise Exception("waited too long")

            time.sleep(1)

    # def wait_for_lock_status(self, should_be_locked):
    #     """Wait until the laser reaches the desired lock state."""
    #     counter = 0
    #     while True:
    #         print("checking lock status...")
    #         to_plot = pickle.loads(self.client.parameters.to_plot.value)

    #         print(f"to_plot keys: {list(to_plot.keys())}")

    #         is_locked = "error_signal" in to_plot

    #         if is_locked == should_be_locked:
    #             break

    #         counter += 1
    #         if counter > 10:
    #             raise Exception("waited too long")

    #         time.sleep(1)
    
    def get_lock_history(self):
        control_signal_history = self.readable_params['control_signal_history'].get_raw_value()
        monitor_signal_history = self.readable_params['monitor_signal_history'].get_raw_value()
        dict = {}
        dict['fast_control_values'] = np.array(control_signal_history['values'])/(2*Vpp)
        dict['fast_control_times'] = np.array(control_signal_history['times'])
        if not(bool(self.writeable_params['dual_channel'].get_raw_value())):
            dict['monitor_values'] = np.array(monitor_signal_history['values'])/(2*Vpp)
            dict['monitor_times'] = np.array(monitor_signal_history['times'])
        if bool(self.writeable_params['pid_on_slow_enabled'].get_raw_value()):
            dict['slow_control_values'] = np.array(control_signal_history['slow_values'])/(2**13-1)*0.9
            dict['slow_control_times'] = np.array(control_signal_history['slow_times'])
        self.history = dict
        return dict
        
    def set_debug_mode(self):
        self.logger.setLevel(logging.DEBUG)
        for handler in self.logger.handlers:
            handler.setLevel(logging.DEBUG)
        
    def unset_debug_mode(self):
        self.logger.setLevel(logging.INFO)
        for handler in self.logger.handlers:
            handler.setLevel(logging.INFO)
