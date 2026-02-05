from .logging_config import setup_logging
import os
import logging
import yaml

from linien_client.device import Device
from linien_client.connection import LinienClient


class HardwareInterface():
    """
    This class is the interface between the user and the Red Pitaya.
    It contains all the low level methods to communicate with the device.
    """

    def __init__(self, config, board):
        self.config = config
        self.board = board

        # Setup Logging
        log_path = self.config.get('paths', {}).get('logs', './logs')
        log_file = os.path.join(log_path, 'interface.log')
        self.logger = logging.getLogger('HardwareInterface')
        setup_logging(self.logger, log_file)

        self.device = None
        self.client = None
        self._connect()
        self._basic_configure()

        self.logger.info("HardwareInterface initialized.")

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
        program is turned off) and loads the other fundamental parameters.
        """

        self.logger.info("Loading RedPitaya initial configurationparameters...")

        self.load_RedPitaya_parameters()

        #self.load_advanced_settings()

        #self.load_additional_hardware_parameters()

        # setup the autolock mode
        #self.client.parameters.autolock_mode_preference.value = AutolockMode.ROBUST # use robust autolock mode
        #self.client.parameters.autolock_determine_offset.value = False # do not determine offset automatically
        #self.client.connection.root.write_registers()

    def load_RedPitaya_parameters(self):
        """
        Load writeable and readable parameters from a YAML config file and create corresponding parameter objects. It also
        writes the initial values of the writeable parameters to the device only once at the end of the loading procedure.   
        """
        
        board_config_file_path = self.config.get('paths', {}).get('hardware', './boards')
        board_config_file = os.path.join(board_config_file_path, f"{self.board['name']}_parameters.yaml")

        if not os.path.exists(board_config_file):
            raise FileNotFoundError(f"Parameter config file not found: {board_config_file}")

        with open(board_config_file, 'r') as f:
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

    def start_sweep(self):
        self.client.connection.root.start_sweep()

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