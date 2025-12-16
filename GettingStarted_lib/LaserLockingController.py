from GettingStarted_lib.Interface import Interface
from GettingStarted_lib.general_lib import setup_logging, find_monitor_signal_peak

from pathlib import Path
import logging
from matplotlib import pyplot as plt
from linien_common.common import ANALOG_OUT_V, Vpp
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

def find_best_correlation(correlations,len_matches,linewidth):
    """
    I have an array of correlations and an array of lengths of the matches, the best correlation is the maximum correlation with a match
    length greater than half the linewidth
    """
    ind_sort = np.argsort(correlations)
    ind = 0
    for i in range(len(ind_sort)-1):
        ind = ind_sort[(len(ind_sort)-1)-i]
        if len_matches[ind] > (linewidth/2):
            break
    return ind

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
        ax1.set_ylabel('Error Signal [V]', color=color1)
        ax1.tick_params(axis='y', colors=color1)
        ax1.spines['left'].set_color(color1)
        #ax1.set_xlabel('Sweep voltage [V]')

        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.plot(monitor_signal, color=color2)
        ax2.set_ylabel('Monitor Signal [V]', color=color2)
        ax2.tick_params(axis='y', colors=color2)
        ax2.spines['right'].set_color(color2)
        ax2.spines['left'].set_visible(False)

        plt.title(f'Sweep Signal (centered at {(self.hardware_interface.writeable_params["big_offset"].get_remote_value() * ANALOG_OUT_V * self.hardware_interface.writeable_params["big_offset"].scaling):.2g} V)')
        plt.show()

        # ---- ask user to select locking region ----
        print("Please specify the position of the target line.")
        x0 = int(input("Enter index of a point on the LEFT side of the target line: "))
        x1 = int(input("Enter index of a point on the RIGHT side of the target line: "))

        clear_output(wait=True)

        expected_lock_monitor_signal_point = find_monitor_signal_peak(error_signal, monitor_signal, x0, x1)
        self.expected_lock_monitor_signal_point = expected_lock_monitor_signal_point
        #print("Expected lock monitor signal point:", expected_lock_monitor_signal_point)

        # ---- plot the sweep signal with expected lock point ----
        fig, ax1 = plt.subplots(tight_layout=True)

        color1 = 'tab:blue'
        ax1.plot(error_signal, color=color1)
        ax1.axhline(y=0, color='gray')
        ax1.set_ylabel('Error Signal [V]', color=color1)
        ax1.tick_params(axis='y', colors=color1)
        ax1.spines['left'].set_color(color1)
        #ax1.set_xlabel('Sweep voltage [V]')

        ax2 = ax1.twinx()
        color2 = 'tab:red'
        ax2.plot(monitor_signal, color=color2)
        ax2.set_ylabel('Monitor Signal [V]', color=color2)
        ax2.tick_params(axis='y', colors=color2)
        ax2.spines['right'].set_color(color2)
        ax2.spines['left'].set_visible(False)

        ax2.scatter(expected_lock_monitor_signal_point[0], expected_lock_monitor_signal_point[1], marker='o', color='orange', s=40, label='Expected monitor lock point')
        
        ax1.axvline(x0, color="g")
        ax1.axvline(x1, color="g")
        ax2.axvline(x0, color="g")
        ax2.axvline(x1, color="g", label = 'Selected lock region')
        
        ax2.legend()

        plt.title(f'Sweep Signal (centered at {(self.hardware_interface.writeable_params["big_offset"].get_remote_value() * ANALOG_OUT_V * self.hardware_interface.writeable_params["big_offset"].scaling):.2g} V)')
        plt.show()

        # ----

        self.hardware_interface.client.connection.root.start_autolock(x0, x1, pickle.dumps(error_signal*2*Vpp))

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
                print("Laser lost locking")
                print("Trying to center the line looking at the slow control signal...")
                self.hardware_interface.start_sweep()
                self.center_after_unlock()
                sleep(1)
                self.hardware_interface.plot_sweep()
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
        ax0.set_ylabel("Signal [V]", color = 'tab:blue')
        ax0.tick_params(axis='y', colors="tab:blue")
        ax0.spines['left'].set_color("tab:blue")
        ax0_d = ax0.twinx()
        ax0_d.plot(self.hardware_interface.history['fast_control_times_mpl'][:-1], self.hardware_interface.history['d_fast_control_values'], color="red", alpha=0.5)
        ax0_d.set_ylabel("Derivative [V/s]", color="red")
        ax0_d.tick_params(axis='y', colors="red")
        ax0_d.spines['right'].set_color("red")

        if self.unlock_events['unlock_event_fast_control_signal']:
            ax0_d.vlines(self.unlock_events['unlock_event_fast_control_signal_at_time'], ymin=ax0_d.get_ylim()[0], ymax=ax0_d.get_ylim()[1], color="orange", label="Fast variation detected")
            ax0_d.legend()

        # ---- Slow Control Signal History ----

        ax1.set_title("Slow Control Signal")
        ax1.plot(self.hardware_interface.history['slow_control_times_mpl'], self.hardware_interface.history['slow_control_values'])
        ax1.set_ylabel("Signal [V]", color = 'tab:blue')
        ax1.tick_params(axis='y', colors="tab:blue")
        ax1.spines['left'].set_color("tab:blue")
        ax1_d = ax1.twinx()
        ax1_d.plot(self.hardware_interface.history['slow_control_times_mpl'][:-1], self.hardware_interface.history['d_slow_control_values'], color="red", alpha=0.5)
        ax1_d.set_ylabel("Derivative [V/s]", color="red")
        ax1_d.tick_params(axis='y', colors="red")
        ax1_d.spines['right'].set_color("red")

        if self.unlock_events['unlock_event_slow_control_signal']:
            ax1_d.vlines(self.unlock_events['unlock_event_slow_control_signal_at_time'], ymin=ax1_d.get_ylim()[0], ymax=ax1_d.get_ylim()[1], color="orange", label="Fast variation detected")
            ax1_d.legend()

        # ---- Monitor Signal ----

        ax2.set_title("Monitor Signal")
        ax2.plot(self.hardware_interface.history['monitor_times_mpl'], self.hardware_interface.history['monitor_values'])
        ax2.set_ylabel("Signal [V]", color = 'tab:blue')
        ax2.tick_params(axis='y', colors="tab:blue")
        ax2.spines['left'].set_color("tab:blue")
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

        detected_peaks, _ = find_peaks(np.abs(self.hardware_interface.history['d_fast_control_values']), height=0.2)
        detected_peaks = [i for i in detected_peaks if  i > int(len(self.hardware_interface.history['d_fast_control_values'])/2)] #only consider recent peaks

        if len(detected_peaks) > 0:
            xs = [self.hardware_interface.history['fast_control_times_mpl'][i] for i in detected_peaks]
            print("Fast variation of the fast control signal detected at time:", self.hardware_interface.history['fast_control_times_dt'][detected_peaks[0]].strftime("%Y-%m-%d %H:%M:%S"))
            self.lock_unlock_logger.info(f"Fast variation of the fast control signal detected at time: {self.hardware_interface.history['fast_control_times_dt'][detected_peaks[0]].strftime('%Y-%m-%d %H:%M:%S')}")
            temp_unlock_events['unlock_event_fast_control_signal'] = True
            temp_unlock_events['unlock_event_fast_control_signal_at_time'] = xs
            self.stop = True

        # 2) Fast variation of the slow control signal (derivative too high)

        detected_peaks, _ = find_peaks(np.abs(self.hardware_interface.history['d_slow_control_values']), height=0.002)
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
    
    def center_after_unlock(self):
        """
        After an unlock event we try to center the line again looking at the slow control signal values before the unlocking.
        """

        slow_control_values = self.hardware_interface.history['slow_control_values']
        selected_slow_control_values = slow_control_values[:int(len(slow_control_values)/2)] #consider only the first half of the history (before unlock)
        slow_control_mean = np.mean(selected_slow_control_values)
        offset = self.hardware_interface.get_remote_value('big_offset')
        self.hardware_interface.set_value('big_offset', offset + int(slow_control_mean/2)) #due to the gains in the summator circuit used

    
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
        ax.set_ylabel('Signal (V)')
        ax.legend()
        ax1.plot(sweep_signal_cut['x'],sweep_signal_cut['y'])
        ax1.set_xlabel('Voltage (V)')
        ax1.set_ylabel('Signal (V)')
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

        time_0 = time.time()

        for i in range(num_points):
            self.logger.debug(f"Setting voltage to {V_scan[i]}V")
            self.hardware_interface.set_value('big_offset', V_scan[i])
            sweep_signal = self.hardware_interface.get_sweep()
            V_scan_results.append(sweep_signal)
            for index,key in enumerate(self.data_handler.reference_lines):
                reference_signal = self.data_handler.reference_lines[key]
                r_coeff, len_window, offset = SignalAnalysis.find_correlation({'x': sweep_signal['x'], 'y': sweep_signal['error_signal']}, reference_signal)
                correlations[index, i] = r_coeff
                len_matches[index, i] = len_window
                offsets[index, i] = offset
                self.logger.debug(f"Correlation with {key} at {V_scan[i]}V: {r_coeff}, Length of match: {len_window}, offset with respect to the reference signal: {offset}")

            # print dynamic progress
            n_10 = int(np.round((i+1) / num_points * 10))
            # dynamically update the progress bar with hastags
            progress_bar = '#' * n_10 + '-' * (10 - n_10)
            line_to_print = f"Scanning at voltage {V_scan[i]:.3f}V ({i+1}/{num_points}) [{progress_bar}] "
            if i != num_points - 1:
                print('\r' + line_to_print + f"({time.time() - time_0:.2f}s)", end="")
            else:
                print('\r' + line_to_print + f"({time.time() - time_0:.2f}s) Done!", end='\n')

        self.lines_positions = {}
        self.lines_offset = {}
        fig,ax = plt.subplots(nrows= 1 + num_reference_lines, figsize=(10, 2 * (1 + num_reference_lines)), tight_layout=True)

        colors = plt.cm.viridis(np.linspace(0, 1, num_reference_lines))
        for index,key in enumerate(self.data_handler.reference_lines):
            reference_signal = self.data_handler.reference_lines[key]
            len_reference_signal = reference_signal['x'][-1]-reference_signal['x'][0]
            ind = find_best_correlation(correlations[index,:], len_matches[index,:], linewidth=len_reference_signal)
            self.lines_positions[key] = V_scan[ind]
            self.lines_offset[key] = offsets[index, ind] + self.hardware_interface.writeable_params["offset_a"].get_remote_value()
            ax[0].plot(V_scan, correlations[index,:], label=f'Correlation with {key}', color=colors[index])
            ax[0].axvline(x=V_scan[ind], color=colors[index], linestyle='--', label=f'Detected Position {key}')
            ax[index + 1].plot(V_scan_results[ind]['x'],V_scan_results[ind]['error_signal'])
            ax[index + 1].axhline(y=0.,color='0.8',linestyle='dashed')
            ax[index + 1].set_title(f'Sweep at {V_scan[ind]}V')
            ax[index + 1].set_xlabel('Voltage (V)')
            ax[index + 1].set_ylabel('Signal (V)')
            self.logger.debug("Offset with respect to the reference line:"+str(self.lines_offset[key]))
        #print(self.lines_positions)
        #print(self.lines_offset)
        ax[0].set_title('Correlations with Reference Lines')
        ax[0].set_xlabel('Voltage (V)')
        ax[0].set_ylabel('Correlation Coefficient')
        ax[0].legend()
        plt.show()
        self.logger.info("Reference lines found successfully.")

    def center_and_lock_v1(self, line_name):
        # --- Setup ---
        if line_name not in self.lines_positions:
            raise ValueError(f"Unknown line name: {line_name}")
        
        # get starting offsets
        offset = self.lines_positions[line_name] #horizontal offset where we expect the line
        offset_y = self.lines_offset[line_name] #vertical offset
        #print('Offset y = ',offset_y)
        self.logger.debug(f"Vertical offset to apply = {- offset_y} to have the zero-crossing placed nicely.") #the offset of the found line with respect to the reference line, so we need to apply the negative offset to center it.

        #get reference line and linewidth
        reference_signal = self.data_handler.reference_lines[line_name]
        linewidth = reference_signal['x'][-1] - reference_signal['x'][0]

        self.hardware_interface.set_value('big_offset', offset)
        self.hardware_interface.set_value('offset_a', - offset_y) #the offset of the found line with respect to the reference line, so we need to apply the negative offset to center it.
        
        #print(f"offset_a: {self.hardware_interface.get_param('offset_a')}")

        # --- Logging initial offset ---
        self.logger.debug(f'START offset = {offset}')

        # --- Feedback loop parameters ---
        JITTER_THR = 0.05
        thr_cnt = 5
        offset_0 = offset

        # if do not see the line at the offset we are at we try to change it a bit summing offset_try[i]
        offset_big_jump = 0.04 # size of the offset jump if we do not see the reference line
        offset_small_jump = 0.01
        offset_try = np.array([0.,1.,-1.,2.,-2.,3.,-3.]) * offset_big_jump
        ind_off_try = 0 
        time_0 = time.time()
        time_last = 0

        correlations = []
        shifts = []
        times = []
        line_outside_arr = []
        line_outside = True
        frequence_stable = False
        cnt = 0

        not_locked = True

        # --- Main Feedback Loop ---
        while not_locked:
            # 1. Acquire signal and compute correlation and shift
            sweep_signal = self.hardware_interface.get_sweep()
            shift = SignalAnalysis.find_shift({'x' : sweep_signal['x'], 'y': sweep_signal['error_signal']} ,reference_signal)
            corr,len_match, _ = SignalAnalysis.find_correlation({'x' : sweep_signal['x'], 'y': sweep_signal['error_signal']}, reference_signal)
            current_time = time.time() - time_0

            times.append(current_time)
            shifts.append(shift)
            correlations.append(corr)

            # 2. Visualization
            display.clear_output(wait=True)
            plt.clf()
            plot1 = plt.subplot2grid((2, 1), (0, 0))
            plot2 = plt.subplot2grid((2, 1), (1, 0))
            signal_xmin = sweep_signal['x'][0] - 1.2*linewidth
            signal_xmax = sweep_signal['x'][-1] + 1.2*linewidth
            plot1.plot(sweep_signal['x'],sweep_signal['error_signal'])
            plot1.plot(reference_signal['x'] + shift, reference_signal['y'], '--')
            plot1.hlines(0, signal_xmin, signal_xmax, color = '0.8', linestyles = 'dashed')
            plot1.set_xlim(signal_xmin, signal_xmax)
            ymax = np.max(np.array([np.max(sweep_signal['error_signal']),np.max(reference_signal['y'])]))
            ymin = np.min(np.array([np.min(sweep_signal['error_signal']),np.min(reference_signal['y'])]))
            ydiff = ymax - ymin
            ymax = ymax + ydiff * 0.2
            ymin = ymin - ydiff * 0.2

            plot1.set_ylim(ymin, ymax)
            plot1.set_xlim(signal_xmin, signal_xmax)
            plot2.scatter(times, shifts)
            plot2.set_xlim(0, (current_time//60 +1)*60)
            plot2.set_ylim(-1.1, 1.1)
            plot1.set_title(f'Sweep Signal with {line_name} (Offset = {offset:.2f} V) \n Correlation = {corr:.2f}, Length of match = {len_match:.2f} V')
            plot1.set_xlabel('Voltage [V]')
            plot1.set_ylabel('Signal [V]')
            plot2.set_title(f'Shift over Time (Jitter Threshold = {JITTER_THR})')
            plot2.set_xlabel('Time [s]')
            plot2.set_ylabel('Shift [V]')
            plt.tight_layout()
            display.display(plt.gcf())

            # 3. Detect if line is inside or outside
            line_now_outside = (corr < 0.5) or (len_match < 0.5*linewidth)
            line_outside_arr.append(line_now_outside)

            if line_now_outside and not line_outside:
                self.logger.debug("Line has escaped")
            elif not line_now_outside and line_outside:
                self.logger.debug("Line is now inside")

            line_outside = line_now_outside
            cnt = cnt + 1 if not line_outside else 0

            # 4. If recent history suggests line is unstable, try different offset
            recent_history = np.array(line_outside_arr[-6:]) # last 6 points, 1 if line is outside, 0 if inside
            if np.sum(recent_history) > 3 and (current_time - time_last > 30):
                if ind_off_try >= len(offset_try):
                    self.logger.debug(f'Could not find good offset starting from {offset_0}')
                    return
                ind_off_try += 1
                offset = offset_0 + offset_try[ind_off_try]
                time_last = current_time
                self.logger.debug(f'Trying new offset = {offset}')
                self.hardware_interface.set_value('big_offset', offset)
                continue

            # 5. When enough points collected, check stability and try to center
            if cnt > thr_cnt:
                recent_shifts = shifts[-(thr_cnt - 1):]
                avg_shift = np.mean(recent_shifts)
                std_shift = np.std(recent_shifts)
                frequence_stable = std_shift < JITTER_THR

                # Plot horizontal lines for mean and std
                plot2.axhline(avg_shift, color='r', linestyle='-')
                plot2.axhline(avg_shift + JITTER_THR, color='r', linestyle='--')
                plot2.axhline(avg_shift - JITTER_THR, color='r', linestyle='--')
                # color region in between mean and std
                plot2.fill_between(times, avg_shift - std_shift, avg_shift + std_shift,color='red', alpha=0.1, label='Stable Region')

                if not frequence_stable:
                    self.logger.debug("Frequency not stable enough")
                else:
                    self.logger.debug("Frequency stable enough")
                    space_left = shift - sweep_signal['x'][0]
                    len_sweep_signal = sweep_signal['x'][-1] - sweep_signal['x'][0]
                    space_right = len_sweep_signal - linewidth - space_left
                    free_space = len_sweep_signal - linewidth
                    edge_space_thr = free_space / 3

                    if space_left > edge_space_thr and space_right > edge_space_thr:
                        self.lines_positions[line_name] = offset
                        #display.clear_output(wait=True)
                        self.logger.info(f"Line {line_name} is centered at offset {offset}.")
                        #plt.clf()
                        ##plt.plot(sweep_signal['x'], sweep_signal['error_signal'], label='Sweep Signal')
                        ##plt.plot(reference_signal['x'] + shift, reference_signal['y'], '--', label='Reference Line')
                        lock_start = reference_signal['V_lock_start'] + shift
                        lock_end = reference_signal['V_lock_end'] + shift
                        lock_start_ind = np.argmin(np.abs(sweep_signal['x'] - lock_start))
                        lock_end_ind = np.argmin(np.abs(sweep_signal['x'] - lock_end))
                        #print(f"Locking region: [{lock_start_ind:.2f}, {lock_end_ind:.2f}]")
                        plot1.axvspan(lock_start,lock_end,color='r',alpha=0.2)
                        #print(f"sweep signal: {sweep_signal['y']}")
                        sweep_signal_raw = sweep_signal['error_signal'] * 2 * Vpp
                        #print(f"sweep signal raw {sweep_signal_raw}")
                        self.logger.debug(f"Starting autolock between indices {lock_start_ind} and {lock_end_ind}.")
                        self.logger.debug(f"First 10 values of sweep signal raw: {sweep_signal_raw[:10]}")
                        # plt.plot(reference_signal['x'] + shift, reference_signal['y'], '--', label='Reference Line')
                        # plt.plot([lock_start, lock_end], [0, 0], 'k-', lw=4, label='Locking Region')
                        # plt.show()
                        expected_lock_monitor_signal_point = find_monitor_signal_peak(sweep_signal['error_signal'], sweep_signal["monitor_signal"], lock_start_ind, lock_end_ind)
                        self.expected_lock_monitor_signal_point = expected_lock_monitor_signal_point
                        self.hardware_interface.client.connection.root.start_autolock(lock_start_ind,lock_end_ind,pickle.dumps(sweep_signal_raw))
                        print("Started autolock")
                        try:
                            self.hardware_interface.wait_for_lock_status(True)
                            self.logger.info("Locking the laser worked \o/")
                            sleep(2)
                            self.lock_unlock_logger.info("Laser locked at time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
                            not_locked = False
                        except Exception:
                            self.logger.info("Locking the laser failed :(")
                            self.hardware_interface.client.connection.root.start_sweep()
                            not_locked = False
                        self.logger.info("Exiting centering and locking procedure.")
                        return
                    elif space_left < edge_space_thr:
                        self.logger.debug("Too far left: increase offset to decrease frequency")
                        offset -= offset_small_jump
                    else:
                        self.logger.debug("Too far right: decrease offset to increase frequency")
                        offset += offset_small_jump

                    self.hardware_interface.set_value('big_offset', offset)
                    cnt = 0
                    line_outside = True
                    frequence_stable = False

    def automatic_lock_relock(self, line_name, relock: bool = True):
        """
        relock tells the function to relock automatically after detecting an unlock event
        or not to do so.
        """
        self.logger.info(f"Starting automatic lock for line {line_name} with relock = {relock}.")
        # The first search is borad to be sure to find the line without any initial hint (2s/scan) 
        self.find_reference_lines(0.75, 1.25, 15)
        try:
            self.center_and_lock_v1(line_name)
        except Exception:
            self.logger.error("Automatic lock/relock failed...")
            return
        
        if not relock:
            self.start_locking_monitor()
        else:
            while True:
                self.start_locking_monitor()
                self.find_reference_lines(self.hardware_interface.get_remote_value('big_offset') - 0.02, self.hardware_interface.get_remote_value('big_offset') + 0.02, 6)
                try:
                    self.center_and_lock_v1(line_name)
                except Exception:
                    self.logger.error("Automatic relock failed...")
                    return

    def set_debug_mode(self):
        self.logger.setLevel(logging.DEBUG)
        for handler in self.logger.handlers:
            handler.setLevel(logging.DEBUG)
        
    def unset_debug_mode(self):
        self.logger.setLevel(logging.INFO)
        for handler in self.logger.handlers:
            handler.setLevel(logging.INFO)

