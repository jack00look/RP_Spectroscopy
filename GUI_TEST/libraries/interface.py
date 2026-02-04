from .logging_config import setup_logging

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
        #self._basic_configure()

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