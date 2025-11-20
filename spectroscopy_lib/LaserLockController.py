from spectroscopy_lib.interface import LinienHardwareInterface
from spectroscopy_lib.main import setup_logging, from_sweep_signal_to_sweep_signal_raw
from spectroscopy_lib.signal_analysis import SignalAnalysis
from spectroscopy_lib.data_handler import LinienDataHandler

import logging
from IPython import display
import time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import pickle
import threading
from threading import Thread, Event
from scipy.ndimage import gaussian_filter1d

def detect_unlock_event(history, time_analysis_start,SYSTEM_TAU = 0.01, SPIKE_THR = 0.1, CHANGE_THR = 0.2):
    """
    Detects if the laser has unlocked based on the fast and slow control signals.
    Returns True if an unlock event is detected, False otherwise.
    """

    times = history['fast_control_times']
    ind_start = np.argmin(np.abs(times - time_analysis_start))
    fast_control = history['fast_control_values'][ind_start:]
    slow_control = history['slow_control_values'][ind_start:]

    fast_control = gaussian_filter1d(fast_control, sigma=SYSTEM_TAU)
    slow_control = gaussian_filter1d(slow_control, sigma=SYSTEM_TAU)

    dt = times[ind_start + 1] - times[ind_start]
    d_fast = np.diff(fast_control) / dt
    d_slow = np.diff(slow_control) / dt

    fast_high_change_mask = np.abs(d_fast) > SPIKE_THR
    slow_high_change_mask = np.abs(d_slow) > SPIKE_THR

    changes = []

    for mask, d_signal in [(fast_high_change_mask, d_fast), (slow_high_change_mask, d_slow)]:
        i = 0
        while i < len(mask):
            if mask[i]:
                start = i
                while i < len(mask) and mask[i]:
                    i += 1
                end = i
                total_change = np.sum(d_signal[start:end]) * dt
                if total_change > CHANGE_THR:
                    changes.append(times[start + ind_start])
            else:
                i += 1

    if changes is not None and len(changes) > 0:
        unlock_time = np.min(np.array(changes))
        # now find average drift in the last 5 seconds before the unlock
        ind_drift_end = np.argmin(np.abs(times - (unlock_time - 1)))
        ind_drift_start = np.argmin(np.abs(times - (unlock_time - 6)))
        drift_value = np.mean(history['slow_control_values'][ind_drift_start:ind_drift_end])
        return drift_value
    else:
        return None

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

class LaserLockController:
    """
    Controller for managing the laser lock system, including hardware interface, signal analysis, and data handling.
    """

    LOG_FILE = Path(__file__).parent / "laser_lock_controller.log"

    def __init__(self,interface):
        self.logger = logging.getLogger(self.__class__.__name__)
        setup_logging(self.logger, self.LOG_FILE)

        self.hardware_interface = interface
        self.data_handler = LinienDataHandler()

        self.logger.info("LaserLockController initialized successfully.")

    def scan_lines(self, start_voltage: float = 0.05, stop_voltage: float = 1.75, num_points: int = 40):
        """
        Scan the laser lines from start_voltage to stop_voltage with num_points.
        """
        self.logger.info(f"Starting scan from {start_voltage}V to {stop_voltage}V with {num_points} points.")
        V_scan = np.linspace(start_voltage, stop_voltage, num_points)
        self.last_Vscan = V_scan
        self.last_Vscan_results = []
        fig,ax = plt.subplots(ncols = 1,nrows=num_points, figsize=(10, 2 * num_points),tight_layout=True)
        time_0 = time.time()
        for i in range(num_points):
            
            self.logger.debug(f"Setting voltage to {V_scan[i]}V")
            self.hardware_interface.set_param('big_offset', V_scan[i])
            self.logger.debug('getting sweep signal')
            sweep_signal = self.hardware_interface.get_sweep()
            self.last_Vscan_results.append(sweep_signal)
            ax[i].plot(sweep_signal['x'], sweep_signal['y'], label=f'Voltage: {V_scan[i]}V')
            ax[i].hlines(0, np.min(sweep_signal['x']), np.max(sweep_signal['x']), color = '0.8', linestyles = 'dashed')
            # fill area between +- sweep_signal['s'] if it exists
            if 's' in sweep_signal:
                ax[i].fill_between(sweep_signal['x'],- sweep_signal['s'], + sweep_signal['s'], alpha=0.2, label='Signal Strength')
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
    
    def get_sweep_from_scan(self,Vscan):
        """
        Get the sweep signal for the last voltage scan.
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
    
    def save_reference_line(self, key: str, V_scan : float, start_voltage : float =-1., stop_voltage : float = +1.,V_lock_start = -1.,V_lock_end = +1.,offset : float = 0.):
        """
        Save a reference line to the data handler.
        """
        self.logger.info(f"Saving reference line with key {key}.")
        sweep_signal = self.get_sweep_from_scan(V_scan)
        start_index = np.argmin(np.abs(sweep_signal['x'] - start_voltage))
        true_start_voltage = sweep_signal['x'][start_index]
        stop_index = np.argmin(np.abs(sweep_signal['x'] - stop_voltage))
        true_end_voltage = sweep_signal['x'][stop_index]
        sweep_signal_cut = {}
        sweep_signal_cut['y'] = sweep_signal['y'][start_index:stop_index] + offset
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
        ax.plot(sweep_signal['x'],sweep_signal['y'])
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

    def reset_reference_lines(self):
        """
        Reset the reference lines in the data handler.
        """
        self.logger.info("Resetting reference lines.")
        self.data_handler.reset_reference_lines()
        self.logger.info("Reference lines reset successfully.")

    def find_reference_lines(self, start_voltage: float = 0.05, stop_voltage: float = 1.75, num_points: int = 40):
        """
        Find reference lines in the scanned data.
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
            self.hardware_interface.set_param('big_offset', V_scan[i])
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

    def start_lock_monitor(self, line_name):
        """
        Start monitoring the lock status of a specific line.
        """
        if line_name not in self.lines_positions:
            raise ValueError(f"Unknown line name: {line_name}")
        
        laser_unlocked_event = threading.Event()

        time_old = time.time()

        SYSTEM_TAU = 0.01 #seconds
        SPIKE_THR = 0.1 # V/s
        CHANGE_THR = 0.2 # V

        relock_value = 0. # V

        while not laser_unlocked_event.is_set():

            history = self.hardware_interface.get_lock_history()

            time_analysis_start = time_old - 5
            result = detect_unlock_event(history, time_analysis_start, SYSTEM_TAU, SPIKE_THR, CHANGE_THR)
            if result is not None:
                laser_unlocked_event.set()
                self.lines_positions[line_name] += result

            time_old = history['fast_control_times'][-1]

            time.sleep(2)
            
        self.center_and_lock_v1(line_name)

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

        self.hardware_interface.set_param('big_offset', offset)
        self.hardware_interface.set_param('offset_a', - offset_y) #the offset of the found line with respect to the reference line, so we need to apply the negative offset to center it.
        
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

        # --- Main Feedback Loop ---
        while True:
            # 1. Acquire signal and compute correlation and shift
            sweep_signal = self.hardware_interface.get_sweep()
            shift = SignalAnalysis.find_shift(sweep_signal,reference_signal)
            corr,len_match, _ = SignalAnalysis.find_correlation(sweep_signal,reference_signal)
            current_time = time.time() - time_0

            times.append(current_time)
            shifts.append(shift)
            correlations.append(corr)

            # 2. Visualization
            #display.clear_output(wait=True)
            plt.clf()
            plot1 = plt.subplot2grid((2, 1), (0, 0))
            plot2 = plt.subplot2grid((2, 1), (1, 0))
            signal_xmin = sweep_signal['x'][0] - 1.2*linewidth
            signal_xmax = sweep_signal['x'][-1] + 1.2*linewidth
            plot1.plot(sweep_signal['x'],sweep_signal['y'])
            plot1.plot(reference_signal['x'] + shift, reference_signal['y'], '--')
            plot1.hlines(0, signal_xmin, signal_xmax, color = '0.8', linestyles = 'dashed')
            plot1.set_xlim(signal_xmin, signal_xmax)
            ymax = np.max(np.array([np.max(sweep_signal['y']),np.max(reference_signal['y'])]))
            ymin = np.min(np.array([np.min(sweep_signal['y']),np.min(reference_signal['y'])]))
            ydiff = ymax - ymin
            ymax = ymax + ydiff * 0.2
            ymin = ymin - ydiff * 0.2

            plot1.set_ylim(ymin, ymax)
            plot1.set_xlim(signal_xmin, signal_xmax)
            plot2.scatter(times, shifts)
            plot2.set_xlim(0, (current_time//60 +1)*60)
            plot2.set_ylim(-1.1, 1.1)
            plot1.set_title(f'Sweep Signal with {line_name} (Offset = {offset:.2f} V) \n Correlation = {corr:.2f}, Length of match = {len_match:.2f} V')
            plot1.set_xlabel('Voltage (V)')
            plot1.set_ylabel('Signal (a.u.)')
            plot2.set_title(f'Shift over Time (Jitter Threshold = {JITTER_THR})')
            plot2.set_xlabel('Time (s)')
            plot2.set_ylabel('Shift (V)')
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
                self.hardware_interface.set_param('big_offset', offset)
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
                    edge_space_thr = free_space / 4

                    if space_left > edge_space_thr and space_right > edge_space_thr:
                        self.lines_positions[line_name] = offset
                        #display.clear_output(wait=True)
                        self.logger.info(f"Line {line_name} is centered at offset {offset}.")
                        #plt.clf()
                        plt.plot(sweep_signal['x'], sweep_signal['y'], label='Sweep Signal')
                        plt.plot(reference_signal['x'] + shift, reference_signal['y'], '--', label='Reference Line')
                        lock_start = reference_signal['V_lock_start'] + shift
                        lock_end = reference_signal['V_lock_end'] + shift
                        lock_start_ind = np.argmin(np.abs(sweep_signal['x'] - lock_start))
                        lock_end_ind = np.argmin(np.abs(sweep_signal['x'] - lock_end))
                        #print(f"Locking region: [{lock_start_ind:.2f}, {lock_end_ind:.2f}]")
                        plt.axvspan(lock_start,lock_end,color='r',alpha=0.2)
                        #print(f"sweep signal: {sweep_signal['y']}")
                        sweep_signal_raw = from_sweep_signal_to_sweep_signal_raw(sweep_signal['y'])
                        #print(f"sweep signal raw {sweep_signal_raw}")
                        self.hardware_interface.client.connection.root.start_autolock(lock_start_ind,lock_end_ind,pickle.dumps(sweep_signal_raw))
                        print("Started autolock")
                        try:
                            self.hardware_interface.wait_for_lock_status(True)
                            self.logger.info("Locking the laser worked \o/")
                        except Exception:
                            self.logger.info("Locking the laser failed :(")
                            self.hardware_interface.client.connection.root.start_sweep()
                        return
                    elif space_left < free_space / 4:
                        self.logger.debug("Too far left: increase offset to decrease frequency")
                        offset -= offset_small_jump
                    else:
                        self.logger.debug("Too far right: decrease offset to increase frequency")
                        offset += offset_small_jump

                    self.hardware_interface.set_param('big_offset', offset)
                    cnt = 0
                    line_outside = True
                    frequence_stable = False

    def set_debug_mode(self):
        self.logger.setLevel(logging.DEBUG)
        for handler in self.logger.handlers:
            handler.setLevel(logging.DEBUG)
        
    def unset_debug_mode(self):
        self.logger.setLevel(logging.INFO)
        for handler in self.logger.handlers:
            handler.setLevel(logging.INFO)