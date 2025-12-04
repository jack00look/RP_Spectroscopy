from GettingStarted_lib.Interface import Interface
from GettingStarted_lib.general_lib import setup_logging, find_monitor_signal_peak

from pathlib import Path
import logging
from matplotlib import pyplot as plt
from linien_common.common import ANALOG_OUT_V
from IPython.display import clear_output
import pickle

class LaserLockingController():
    """
    Controller for managing the laser lock system, including hardware interface, signal analysis, and data handling.
    """

    LOG_FILE = Path(__file__).parent / "laser_locking_controller.log"

    def __init__(self, interface):
        self.logger = logging.getLogger(self.__class__.__name__)
        setup_logging(self.logger, self.LOG_FILE)

        self.hardware_interface = interface
        self.logger.info("LaserLockController initialized successfully.")

    def start_manual_locking(self):
        self.hardware_interface.wait_for_lock_status(False) #wait until the laser is unlocked
        # ---- plot the sweep signal ----
        to_plot = self.hardware_interface.get_sweep()
        print(to_plot.keys())
        error_signal = to_plot['error_signal']
        monitor_signal = to_plot['monitor_signal']

        fig, ax1 = plt.subplots(tight_layout=True)

        color1 = 'tab:blue'
        ax1.plot(error_signal, color=color1)
        ax1.axhline(y=0, color='gray')
        ax1.set_ylabel('Error Signal [a.u.]', color=color1)
        ax1.tick_params(axis='y', colors=color1)
        ax1.spines['left'].set_color(color1)
        #ax1.set_xlabel('Sweep voltage [V]')

        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.plot(monitor_signal, color=color2)
        ax2.set_ylabel('Monitor Signal [a.u.]', color=color2)
        ax2.tick_params(axis='y', colors=color2)
        ax2.spines['right'].set_color(color2)
        ax2.spines['left'].set_visible(False)

        plt.title(f'Sweep Signal (centered at {(self.hardware_interface.writeable_params["big_offset"].get_remote_value() * ANALOG_OUT_V):.2g}V)')
        plt.show()

        # ---- ask user to select locking region ----
        print("Please specify the position of the target line.")
        x0 = int(input("Enter index of a point on the LEFT side of the target line: "))
        x1 = int(input("Enter index of a point on the RIGHT side of the target line: "))

        clear_output(wait=True)

        expected_lock_monitor_signal_point = find_monitor_signal_peak(error_signal, monitor_signal, x0, x1)
        print("Expected lock monitor signal point:", expected_lock_monitor_signal_point)

        # ---- plot the sweep signal with expected lock point ----
        fig, ax1 = plt.subplots(tight_layout=True)

        color1 = 'tab:blue'
        ax1.plot(error_signal, color=color1)
        ax1.axhline(y=0, color='gray')
        ax1.set_ylabel('Error Signal [a.u.]', color=color1)
        ax1.tick_params(axis='y', colors=color1)
        ax1.spines['left'].set_color(color1)
        #ax1.set_xlabel('Sweep voltage [V]')

        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.plot(monitor_signal, color=color2)
        ax2.set_ylabel('Monitor Signal [a.u.]', color=color2)
        ax2.tick_params(axis='y', colors=color2)
        ax2.spines['right'].set_color(color2)
        ax2.spines['left'].set_visible(False)

        ax2.scatter(expected_lock_monitor_signal_point[0], expected_lock_monitor_signal_point[1], marker='o', color='orange', s=40, label='Expected monitor lock point')
        
        ax1.axvline(x0, color="g")
        ax1.axvline(x1, color="g")
        ax2.axvline(x0, color="g")
        ax2.axvline(x1, color="g", label = 'Selected lock region')
        
        ax2.legend()

        plt.title(f'Sweep Signal (centered at {(self.hardware_interface.writeable_params["big_offset"].get_remote_value() * ANALOG_OUT_V):.2g}V)')
        plt.show()

        # ----

        self.hardware_interface.client.connection.root.start_autolock(x0, x1, pickle.dumps(error_signal))

        try:
            self.hardware_interface.wait_for_lock_status(True)
            print("Locking the laser worked! \\o/")
            #gl.locking_monitor(c, monitor_signal_reference_point)
        except Exception:
            print("Locking the laser failed :(")

