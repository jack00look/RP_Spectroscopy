from pathlib import Path
import logging
from GettingStarted_lib.general_lib import setup_logging
import yaml
from linien_client.device import Device
from linien_client.connection import LinienClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Interface:
    CONNECT_CONFIG_PATH = Path(__file__).parent / 'connect_config.yaml'
    PARAMS_CONFIG_PATH = Path(__file__).parent / 'params_config.yaml'
    LOG_FILE = Path(__file__).parent / "interface.log"


    def __init__(self):

        self.logger = logging.getLogger(self.__class__.__name__)
        setup_logging(self.logger, self.LOG_FILE) #sets up the logger

        self._load_config() #loads connection configuration

        self.device = None
        self.client = None
        self._connect() #connects to the device
        self._basic_configure()

    def _load_config(self):
        '''
        Loads connection configuration from the CONNECT_CONFIG_PATH YAML file.
        '''

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
        """
        Try connecting to Red Pitaya.
        """

        for name, device_info in self.DEVICES.items():
            try:
                self.logger.info(f"Attempting connection via {name} address ({device_info['ip']}:{device_info['linien_port']})")
                self.device = Device(host=device_info['ip'], username=self.USERNAME, password=self.PASSWORD)
                self.client = LinienClient(self.device)
                self.client.connect(autostart_server=True, use_parameter_cache=True)
                self.logger.info(f"Connected to device via {name} address")

                return
            except Exception as e:
                self.logger.warning(f"Failed to connect via {name} address: {e}")

        self.logger.error("No network connection found.")
        raise ConnectionError("Failed to connect to Linien device.")
    
    def _basic_configure(self):

        self.load_parameter_config() # loads parameters from config file
        #self.set_debug_mode()

        # setup the autolock mode
        #self.client.parameters.autolock_mode_preference.value = AutolockMode.ROBUST # use robust autolock mode
        #self.client.parameters.autolock_determine_offset.value = False # do not determine offset automatically
        #self.client.connection.root.write_registers()
    
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
            self.writeable_params[name] = WriteableParameter(
                name=name,
                hardware_name=entry["hardware_name"],
                initial_value=entry["initial_value"],
                scaling=entry["scaling"]
            )

        self.readable_params = {}
        for name,entry in config.get("readable_parameters", {}).items():
            self.readable_params[name] = entry['hardware_name']
        
class WriteableParameter:
    def __init__(self, name, hardware_name, initial_value, scaling):
        self.name = name
        self.hardware_name = hardware_name
        self.initial_value = initial_value
        self.scaling = scaling

    def __repr__(self):
        return f"Parameter(name={self.name}, hardware_name={self.hardware_name}, value={self.initial_value}, scaling={self.scaling})"