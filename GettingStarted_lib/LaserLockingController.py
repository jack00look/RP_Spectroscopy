from GettingStarted_lib.Interface import Interface
from GettingStarted_lib.general_lib import setup_logging, find_monitor_signal_peak

from pathlib import Path
import logging
from matplotlib import pyplot as plt
from linien_common.common import ANALOG_OUT_V
from IPython.display import clear_output
import pickle
import time
from time import sleep
from IPython import display
import numpy as np
from scipy.ndimage import gaussian_filter1d
import matplotlib.dates as mdates
from scipy.signal import find_peaks



class LaserLockingController():
    """
    Controller for managing the laser lock system, including hardware interface, signal analysis, and data handling.
    """

    LOG_FILE = Path(__file__).parent / "laser_locking_controller.log"

    def __init__(self, interface):
        self.logger = logging.getLogger(self.__class__.__name__)
        setup_logging(self.logger, self.LOG_FILE)

        self.lock_unlock_logger = logging.getLogger("UnlockEventsLogger")
        setup_logging(self.lock_unlock_logger, Path(__file__).parent / "lock_unlock_events.log")

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
        self.expected_lock_monitor_signal_point = expected_lock_monitor_signal_point
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
            sleep(2)
            self.lock_unlock_logger.info("Laser locked at time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
        except Exception:
            print("Locking the laser failed :(")
            return

    def start_locking_monitor(self):
        self.stop = False

        try:
            self.hardware_interface.wait_for_lock_status(True)
            print("Laser is locked! Starting locking monitor...")
        except Exception:
            print("Laser is not locked. Cannot start locking monitor.")
            return
        
        while True:

            history = self.hardware_interface.get_history()

            self.detect_unlock_event()

            self.show_history()

            if self.stop:
                print("Laser lost locking:")

                print("Exiting locking monitor...")
                break

            sleep(2)

    def show_history(self):

        display.clear_output(wait=True)

        fig, axs = plt.subplots(3,1, sharex=True, tight_layout=True)
        ax0, ax1, ax2 = axs

        fig.suptitle("History data")

        # ---- Control Signal History ----

        ax0.set_title("Control Signal")
        ax0.plot(self.hardware_interface.history['fast_control_times_mpl'], self.hardware_interface.history['fast_control_values'])
        ax0_d = ax0.twinx()
        ax0_d.plot(self.hardware_interface.history['fast_control_times_mpl'][:-1], self.hardware_interface.history['d_fast_control_values'], color="red", alpha=0.5)
        ax0_d.set_ylabel("Derivative", color="red")
        ax0_d.tick_params(axis='y', colors="red")
        ax0_d.spines['right'].set_color("red")

        if self.unlock_events['unlock_event_fast_control_signal']:
            ax0_d.vlines(self.unlock_events['unlock_event_fast_control_signal_at_time'], ymin=ax0_d.get_ylim()[0], ymax=ax0_d.get_ylim()[1], color="orange", label="Fast variation detected")
            ax0_d.legend()

        # ---- Slow Control Signal History ----

        ax1.set_title("Slow Control Signal")
        ax1.plot(self.hardware_interface.history['slow_control_times_mpl'], self.hardware_interface.history['slow_control_values'])
        ax1_d = ax1.twinx()
        ax1_d.plot(self.hardware_interface.history['slow_control_times_mpl'][:-1], self.hardware_interface.history['d_slow_control_values'], color="red", alpha=0.5)
        ax1_d.set_ylabel("Derivative", color="red")
        ax1_d.tick_params(axis='y', colors="red")
        ax1_d.spines['right'].set_color("red")

        if self.unlock_events['unlock_event_slow_control_signal']:
            ax1_d.vlines(self.unlock_events['unlock_event_slow_control_signal_at_time'], ymin=ax1_d.get_ylim()[0], ymax=ax1_d.get_ylim()[1], color="orange", label="Fast variation detected")
            ax1_d.legend()

        # ---- Monitor Signal ----

        ax2.set_title("Monitor Signal")
        ax2.plot(self.hardware_interface.history['monitor_times_mpl'], self.hardware_interface.history['monitor_values'])
        ax2.axhline(self.expected_lock_monitor_signal_point[1], color="gray")

        # ----

        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
        # Rotate labels if needed
        fig.autofmt_xdate()

        display.display(fig)

        plt.close(fig)

    def detect_unlock_event(self):
        """
        We have different ways to detect an unlock event:
            1) Fast variations of the fast control signal (derivative too high)
            2) Fast variation of the slow control signal (derivative too high)
            3) If fast control signal is saturated
            4) If slow control signal is saturated
        """

        temp_unlock_events = {}
        temp_unlock_events['unlock_event_fast_control_signal'] = False
        temp_unlock_events['unlock_event_slow_control_signal'] = False

        time_now = time.time()

        # 1) Fast variations of the fast control signal (derivative too high)

        detected_peaks, _ = find_peaks(np.abs(self.hardware_interface.history['d_fast_control_values']), height=500)
        detected_peaks = [i for i in detected_peaks if  i > int(len(self.hardware_interface.history['d_fast_control_values'])/2)] #only consider recent peaks

        if len(detected_peaks) > 0:
            xs = [self.hardware_interface.history['fast_control_times_mpl'][i] for i in detected_peaks]
            print("Fast variation of the fast control signal detected at time:", self.hardware_interface.history['fast_control_times_dt'][detected_peaks[0]].strftime("%Y-%m-%d %H:%M:%S"))
            self.lock_unlock_logger.info(f"Fast variation of the fast control signal detected at time: {self.hardware_interface.history['fast_control_times_dt'][detected_peaks[0]].strftime('%Y-%m-%d %H:%M:%S')}")
            temp_unlock_events['unlock_event_fast_control_signal'] = True
            temp_unlock_events['unlock_event_fast_control_signal_at_time'] = xs
            self.stop = True

        # 2) Fast variation of the slow control signal (derivative too high)

        detected_peaks, _ = find_peaks(np.abs(self.hardware_interface.history['d_slow_control_values']), height=40)
        detected_peaks = [i for i in detected_peaks if  i > int(len(self.hardware_interface.history['d_slow_control_values'])/2)] #only consider recent peaks


        if len(detected_peaks) > 0:
            xs = [self.hardware_interface.history['slow_control_times_mpl'][i] for i in detected_peaks]
            print("Fast variation of the slow control signal detected at time:", self.hardware_interface.history['slow_control_times_dt'][detected_peaks[0]].strftime("%Y-%m-%d %H:%M:%S"))
            self.lock_unlock_logger.info(f"Fast variation of the slow control signal detected at time: {self.hardware_interface.history['slow_control_times_dt'][detected_peaks[0]].strftime('%Y-%m-%d %H:%M:%S')}")
            temp_unlock_events['unlock_event_slow_control_signal'] = True
            temp_unlock_events['unlock_event_slow_control_signal_at_time'] = xs
            self.stop = True

        # 3) If fast control signal is saturated
        # 4) If slow control signal is saturated

        self.unlock_events = temp_unlock_events

        return


