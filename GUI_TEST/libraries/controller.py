from .logging_config import setup_logging
import logging
import os

class LockController():
    """
    This class manages the high level lock algorithm.
    """

    def __init__(self, interface):
        self.interface = interface
        # Access config via interface if not passed directly
        self.config = self.interface.config

        # Setup Logging
        log_path = self.config.get('paths', {}).get('logs', './logs')
        log_file = os.path.join(log_path, 'controller.log')
        self.logger = logging.getLogger('Controller')
        setup_logging(self.logger, log_file)

    def scan(self, start_voltage: float = 0.05, stop_voltage: float = 1.75, num_points: int = 40):
        """
        Scan the laser lines from start_voltage to stop_voltage with num_points. If not specified it will scan the full range.
        """
        self.logger.info(f"Starting scan from {start_voltage}V to {stop_voltage}V with {num_points} points.")
        V_scan = np.linspace(start_voltage, stop_voltage, num_points)
        self.last_Vscan = V_scan
        self.last_Vscan_results = []
        time_0 = time.time()
        for i in range(num_points):
            self.logger.debug(f"Setting voltage to {V_scan[i]}V")
            self.interface.set_value('big_offset', V_scan[i])
            self.logger.debug('getting sweep signal')
            sweep_signal = self.interface.get_sweep()
            self.last_Vscan_results.append(sweep_signal)
        self.last_Vscan_results = np.array(self.last_Vscan_results)
        self.logger.info("Scan completed successfully.")

