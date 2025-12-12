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
from GettingStarted_lib.data_handler import DataHandler
from GettingStarted_lib.signal_analysis import SignalAnalysis


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
        self.data_handler = DataHandler()
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
    
    def scan(self, start_voltage: float = 0.05, stop_voltage: float = 1.75, num_points: int = 40):
        """
        Scan the laser lines from start_voltage to stop_voltage with num_points. If not specified it will scan the full range.
        """
        self.logger.info(f"Starting scan from {start_voltage}V to {stop_voltage}V with {num_points} points.")
        V_scan = np.linspace(start_voltage, stop_voltage, num_points)
        self.last_Vscan = V_scan
        self.last_Vscan_results = []
        fig,ax = plt.subplots(ncols = 1,nrows=num_points, figsize=(10, 2 * num_points),tight_layout=True)
        time_0 = time.time()
        for i in range(num_points):
            
            self.logger.debug(f"Setting voltage to {V_scan[i]}V")
            self.hardware_interface.set_value('big_offset', V_scan[i])
            self.logger.debug('getting sweep signal')
            sweep_signal = self.hardware_interface.get_sweep()
            self.last_Vscan_results.append(sweep_signal)
            ax[i].plot(sweep_signal['x'], sweep_signal['error_signal'], label=f'Voltage: {V_scan[i]}V')
            ax[i].hlines(0, np.min(sweep_signal['x']), np.max(sweep_signal['x']), color = '0.8', linestyles = 'dashed')
            ax[i].set_title(f'Sweep at {V_scan[i]}V')
            # print dynamic progress
            n_10 = int(np.round((i+1) / num_points * 10))
            # dynamically update the progress bar with hastags
            progress_bar = '#' * n_10 + '-' * (10 - n_10)
            line_to_print = f"Scanning at voltage {V_scan[i]:.3f}V ({i+1}/{num_points}) [{progress_bar}] "
            if i != num_points - 1:
                print('\r' + line_to_print + f"({time.time() - time_0:.2f}s)", end="")
            else:
                print('\r' + line_to_print + f"({time.time() - time_0:.2f}s) Done!", end='\n')
        self.last_Vscan_results = np.array(self.last_Vscan_results)
        self.logger.info("Scan completed successfully.")

    def save_reference_line(self, key: str, V_scan : float, start_voltage : float =-1., stop_voltage : float = +1.,V_lock_start = -1.,V_lock_end = +1.,offset : float = 0.):
        """
        Save a reference line.
        """
        self.logger.info(f"Saving reference line with key {key}.")
        sweep_signal = self.get_sweep_from_scan(V_scan)
        start_index = np.argmin(np.abs(sweep_signal['x'] - start_voltage))
        true_start_voltage = sweep_signal['x'][start_index]
        stop_index = np.argmin(np.abs(sweep_signal['x'] - stop_voltage))
        true_end_voltage = sweep_signal['x'][stop_index]
        sweep_signal_cut = {}
        sweep_signal_cut['y'] = sweep_signal['error_signal'][start_index:stop_index] + offset
        sweep_signal_cut['x'] = sweep_signal['x'][start_index:stop_index]
        locking_region_inside = True
        if V_lock_start < true_start_voltage or V_lock_start > true_end_voltage or V_lock_end < true_start_voltage or V_lock_end > true_end_voltage or V_lock_start >= V_lock_end:
            locking_region_inside = False
        if not locking_region_inside:
            self.logger.warning(f"Locking region [{V_lock_start:.2f}V, {V_lock_end:.2f}V] is outside the scan range [{true_start_voltage:.2f}V to {true_end_voltage:.2f}V].")
        self.data_handler.save_reference_line(key, sweep_signal_cut,V_lock_start,V_lock_end)
        self.data_handler._load_reference_lines()  # Reload reference lines to ensure the new one is included
        fig,axs = plt.subplots(nrows=2,tight_layout=True)
        ax,ax1 = axs
        ax.plot(sweep_signal['x'],sweep_signal['error_signal'])
        ax.axvspan(V_lock_start,V_lock_end,color = 'r',alpha=0.2,label = 'locking region')
        ax.axvline(x=true_start_voltage, color='r', linestyle='--', label='Start Voltage')
        ax.axvline(x=true_end_voltage, color='r', linestyle='--', label='Stop Voltage')
        ax.hlines(0, np.min(sweep_signal['x']), np.max(sweep_signal['x']), color = '0.8', linestyles = 'dashed')
        ax.set_title(f'Reference Line {key}')
        ax.set_xlabel('Voltage (V)')
        ax.set_ylabel('Signal (a.u.)')
        ax.legend()
        ax1.plot(sweep_signal_cut['x'],sweep_signal_cut['y'])
        ax1.set_xlabel('Voltage (V)')
        ax1.set_ylabel('Signal (a.u.)')
        ax1.axhline(y=0.,color='0.8',linestyle='dashed')
        ax1.axvspan(V_lock_start,V_lock_end,color = 'r',alpha=0.2,label = 'locking region')

        plt.show()
        self.logger.info(f"Reference line {key} saved successfully.")

    def get_sweep_from_scan(self, Vscan):
        """
        Get the sweep signal at big_offset value Vscan from the last voltage scan.
        """
        if not hasattr(self, 'last_Vscan_results'):
            self.logger.error("No scan results available. Please run scan_lines first.")
            return None
        # find closest voltage in last_Vscan
        if not hasattr(self, 'last_Vscan'):
            self.logger.error("No last_Vscan available. Please run scan_lines first.")
            return None
        if not isinstance(Vscan, float):
            self.logger.error("Vscan must be a float.")
            return None
        ind = np.argmin(np.abs(self.last_Vscan - Vscan))
        return self.last_Vscan_results[ind]
    
    def find_reference_lines(self, start_voltage: float = 0.05, stop_voltage: float = 1.75, num_points: int = 40):
        """
        Scans the desired range and finds the voltage at which the reference line is autonomously. If not speficied it scans the full range.
        """

        self.logger.info("Finding reference lines.")

        V_scan = np.linspace(start_voltage, stop_voltage, num_points)
        V_scan_results = []

        num_reference_lines = len(self.data_handler.reference_lines)
        if num_reference_lines == 0:
            self.logger.warning("No reference lines found. Please save reference lines first.")
            return
        
        correlations = np.zeros((num_reference_lines, num_points))
        len_matches = np.zeros((num_reference_lines, num_points))
        offsets = np.zeros((num_reference_lines, num_points)) #vertical offset

        for i in range(num_points):
            self.logger.debug(f"Setting voltage to {V_scan[i]}V")
            self.hardware_interface.set_value('big_offset', V_scan[i])
            sweep_signal = self.hardware_interface.get_sweep()
            V_scan_results.append(sweep_signal)
            for index,key in enumerate(self.data_handler.reference_lines):
                reference_signal = self.data_handler.reference_lines[key]
                r_coeff, len_window, offset = SignalAnalysis.find_correlation(sweep_signal, reference_signal)
                correlations[index, i] = r_coeff
                len_matches[index, i] = len_window
                offsets[index, i] = offset
                self.logger.debug(f"Correlation with {key} at {V_scan[i]}V: {r_coeff}, Length of match: {len_window}, offset with respect to the reference signal: {offset}")
        
        self.lines_positions = {}
        self.lines_offset = {}
        fig,ax = plt.subplots(nrows= 1 + num_reference_lines, figsize=(10, 2 * (1 + num_reference_lines)), tight_layout=True)

        colors = plt.cm.viridis(np.linspace(0, 1, num_reference_lines))
        for index,key in enumerate(self.data_handler.reference_lines):
            reference_signal = self.data_handler.reference_lines[key]
            len_reference_signal = reference_signal['x'][-1]-reference_signal['x'][0]
            ind = find_best_correlation(correlations[index,:], len_matches[index,:], linewidth=len_reference_signal)
            self.lines_positions[key] = V_scan[ind]
            self.lines_offset[key] = offsets[index, ind] + self.hardware_interface.get_param('offset_a')
            ax[0].plot(V_scan, correlations[index,:], label=f'Correlation with {key}', color=colors[index])
            ax[0].axvline(x=V_scan[ind], color=colors[index], linestyle='--', label=f'Detected Position {key}')
            ax[index + 1].plot(V_scan_results[ind]['x'],V_scan_results[ind]['y'])
            ax[index + 1].set_title(f'Sweep at {V_scan[ind]}V')
            ax[index + 1].set_xlabel('Voltage (V)')
            ax[index + 1].set_ylabel('Signal (a.u.)')
            self.logger.debug("Offset with respect to the reference line:"+str(self.lines_offset[key]))
        #print(self.lines_positions)
        #print(self.lines_offset)
        ax[0].set_title('Correlations with Reference Lines')
        ax[0].set_xlabel('Voltage (V)')
        ax[0].set_ylabel('Correlation Coefficient')
        ax[0].legend()
        plt.show()
        self.logger.info("Reference lines found successfully.")

