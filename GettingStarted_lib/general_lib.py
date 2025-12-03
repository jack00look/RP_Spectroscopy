import time
from time import sleep
import matplotlib as mpl
from IPython import display
from  matplotlib import pyplot as plt
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
import numpy as np
import matplotlib.dates as mdates
from datetime import datetime
import logging
import sys

def locking_monitor(c, monitor_signal_reference_point):
    print("Starting locking monitor...")
    counter = 0
    limit = 200

    c.parameters.check_for_changed_parameters()

    unlocking_time_monitor_signal = 0 #unlocking time detection from monitor signal stats pov
    old_monitor_signal_against_reference_flag = 1
    monitor_signal_against_reference_flag = 1 #1 means locking is ok from the monitor signal stats pov
    
    old_control_signal_value_flag = 1
    control_signal_value_flag = 1 #1 means ok

    old_slow_control_signal_value_flag = 1
    slow_control_signal_value_flag = 1 #1 means ok

    stop = 0

    while True:

        time_now = time.time()

        #if counter >= limit:
            #break

        counter +=1

        control_history = c.parameters.control_signal_history.value
        signal_history = c.parameters.monitor_signal_history.value

        # ---- Time conversion ----
            # Control Signal
        times_CS_unix = np.array(control_history["times"]) #UNIX
        times_CS_dt = [datetime.fromtimestamp(t) for t in times_CS_unix] #datetime
        times_CS_mpl  = mdates.date2num(times_CS_dt)   #Matplotlib dates
            # Slow CS
        times_SCS_unix = np.array(control_history["slow_times"]) #UNIX
        times_SCS_dt = [datetime.fromtimestamp(t) for t in times_SCS_unix] #datetime
        times_SCS_mpl  = mdates.date2num(times_SCS_dt)   #Matplotlib dates
            # Monitor Signal
        times_MS_unix = np.array(signal_history["times"]) #UNIX
        times_MS_dt = [datetime.fromtimestamp(t) for t in times_MS_unix] #datetime
        times_MS_mpl  = mdates.date2num(times_MS_dt)   #Matplotlib dates
        # ----

        display.clear_output(wait=True)
        #plt.clf()

        fig, axs = plt.subplots(3,1, sharex=True, tight_layout=True)
        fig.suptitle("History data")

        ax0, ax1, ax2 = axs

        # ---- Control Signal ----

        control_signal = control_history["values"]

        ax0.set_title("Control Signal")
        ax0.plot(times_CS_mpl, control_signal)
        #evaluation of the derivateive of the control signal
        sigma = 5
        dt = control_history["times"][-1] - control_history["times"][-2]
        d_control_history = np.diff(gaussian_filter1d(control_history["values"], sigma=sigma))/dt
        ax0_d = ax0.twinx()
        ax0_d.plot(times_CS_mpl[:-1], d_control_history, color="red", alpha=0.5)
        ax0_d.set_ylabel("Derivative", color="red")
        ax0_d.tick_params(axis='y', colors="red")
        ax0_d.spines['right'].set_color("red")

        detected_peaks, _ = find_peaks(np.abs(d_control_history), height=500)
        detected_peaks = [i for i in detected_peaks if  i > int(len(control_history["values"])/2)] #only consider recent peaks

        if len(detected_peaks) > 0:
            xs = [times_CS_mpl[i] for i in detected_peaks]
            ax0_d.vlines(xs, ymin=ax0_d.get_ylim()[0], ymax=ax0_d.get_ylim()[1], color="orange", label="Fast variation detected")
            ax0_d.legend()
            control_signal_value_flag = 0
            if old_control_signal_value_flag and not control_signal_value_flag:
                print("Fast variation of the control signal detected at time:", times_CS_dt[detected_peaks[0]].strftime("%Y-%m-%d %H:%M:%S"))
                stop = 1


        old_control_signal_value_flag = control_signal_value_flag

        # ---- Slow Control Signal ----

        slow_control_signal = control_history["slow_values"]

        ax1.set_title("Slow Control Signal")
        ax1.plot(times_SCS_mpl, slow_control_signal)
        #evaluation of the derivateive of the slow control signal
        dt_slow = control_history["slow_times"][-1] - control_history["slow_times"][-2]
        d_slow_control_history = np.diff(gaussian_filter1d(control_history["slow_values"], sigma = sigma))/dt
        ax1_d = ax1.twinx()
        ax1_d.plot(times_SCS_mpl[:-1], d_slow_control_history, color="red", alpha=0.5)
        ax1_d.set_ylabel("Derivative", color="red")
        ax1_d.tick_params(axis='y', colors="red")
        ax1_d.spines['right'].set_color("red")

        detected_peaks, _ = find_peaks(np.abs(d_slow_control_history), height=40)
        detected_peaks = [i for i in detected_peaks if  i > int(len(control_history["values"])/2)] #only consider recent peaks


        if len(detected_peaks) > 0:
            xs = [times_SCS_mpl[i] for i in detected_peaks]
            ax1_d.vlines(xs, ymin=ax1_d.get_ylim()[0], ymax=ax1_d.get_ylim()[1], color="orange", label="Fast variation detected")
            ax1_d.legend()
            slow_control_signal_value_flag = 0
            if old_slow_control_signal_value_flag and not slow_control_signal_value_flag:
                print("Fast variation of the slow control signal detected at time:", times_SCS_dt[detected_peaks[0]].strftime("%Y-%m-%d %H:%M:%S"))
                stop = 1


        old_slow_control_signal_value_flag = slow_control_signal_value_flag

        # ---- Monitor Signal ----

        monitor_signal = signal_history["values"]

        ax2.set_title("Monitor Signal")
        ax2.plot(times_MS_mpl, monitor_signal)
        ax2.axhline(monitor_signal_reference_point[1], color="gray")

        evaluation_time = 100

        monitor_signal_mean, monitor_signal_std = monitor_signal_stats(signal_history["values"], evaluation_time)
        
        if (monitor_signal_mean - 2*monitor_signal_std > monitor_signal_reference_point[1]) or (monitor_signal_mean + 2*monitor_signal_std < monitor_signal_reference_point[1]):
            monitor_signal_against_reference_flag = 0
            if old_monitor_signal_against_reference_flag and not monitor_signal_against_reference_flag:
                unlocking_time_monitor_signal = signal_history["times"][-evaluation_time]
                print("Monitor signal stats detected out of locking region at time:", datetime.fromtimestamp(unlocking_time_monitor_signal))
            elif not old_monitor_signal_against_reference_flag and not monitor_signal_against_reference_flag:
                print("System is still out of locking region at time:", datetime.fromtimestamp(unlocking_time_monitor_signal), "(unlocked for ", signal_history["times"][-evaluation_time]-unlocking_time_monitor_signal, "s)")
        else:
            monitor_signal_against_reference_flag = 1
            if not old_monitor_signal_against_reference_flag and monitor_signal_against_reference_flag:
                print("System re-entered in the locking region at time:", datetime.fromtimestamp(unlocking_time_monitor_signal), "(unlocked for ", signal_history["times"][-evaluation_time]-unlocking_time_monitor_signal, "s)")
            else:
                print("System is locked at time:", datetime.fromtimestamp(unlocking_time_monitor_signal))

        old_monitor_signal_against_reference_flag = monitor_signal_against_reference_flag

        colours = ["orange", "green"]
        ax2.fill_between(times_MS_mpl[-evaluation_time:], monitor_signal_mean - 2*monitor_signal_std, monitor_signal_mean + 2*monitor_signal_std, color=colours[monitor_signal_against_reference_flag], alpha=0.3)

        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
        # Rotate labels if needed
        fig.autofmt_xdate()

        display.display(fig)

        plt.close(fig)

        if stop:
            print("Exiting locking monitor...")
            break

        sleep(2)

def find_monitor_signal_reference_height(monitor_signal, error_signal, x0, x1):
    error_signal_selected_region = error_signal[x0:x1]

    maximum_error_index = np.argmax(error_signal_selected_region)
    minimum_error_index = np.argmin(error_signal_selected_region)

    if maximum_error_index < minimum_error_index:
        start_index = maximum_error_index+x0
        end_index = minimum_error_index+x0
    else:
        start_index = minimum_error_index+x0
        end_index = maximum_error_index+x0

    #print("Start and end indexs for zero crossing search:", start_index, end_index)
    zero_crossing_region = error_signal[start_index:end_index]
    #print("Selected error signal region for zero crossing search:", zero_crossing_region)

    error_signal_zero_crossings = []

    for i in range(1, len(zero_crossing_region)):
        if zero_crossing_region[i] * zero_crossing_region[i-1] <= 0:
            error_signal_zero_crossings.append(i)
            break

    #print("Zero crossings found at indices:", np.array(error_signal_zero_crossings)+start_index)

    if len(error_signal_zero_crossings) == 0:
        raise ValueError("No zero crossings found in the selected region.")
    elif len(error_signal_zero_crossings) > 1:
        raise ValueError("Multiple zero crossings found in the selected region.")
    else:
        return [start_index, end_index], [np.array(error_signal_zero_crossings[0])+start_index, monitor_signal[np.array(error_signal_zero_crossings[0])+start_index]]

def monitor_signal_stats(monitor_signal, evaluation_time):
    mean = np.mean(monitor_signal[-evaluation_time:])
    std_dev = np.std(monitor_signal[-evaluation_time:])
    return mean, std_dev

def find_unlock_event():
    """
    We want different ways of detecting unlock events.
    """

    # Look at the monitor signal value with respect to the reference one
    find_monitor_signal_fluctuations()

def find_monitor_signal_fluctuations(monitor_signal, monitor_signal_reference_point):
    evaluation_time = 10
    mean = np.mean(monitor_signal[-evaluation_time:])
    std_dev = np.std(monitor_signal[-evaluation_time:])

def setup_logging(logger,logger_file):
    """
    Sets up the logging to stream and file
    """
    logger.setLevel(logging.INFO) #sets the level of this function in the logging different levels to INFO
    console_handler = logging.StreamHandler(sys.stdout) #sends logging outputs to stream in the std output
    file_handler = logging.FileHandler(logger_file) #sends logging outputs to a disk file
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ) #organizes the log data as desired. It is a template
    console_handler.setFormatter(formatter) #chooses this formatter for the console
    file_handler.setFormatter(formatter) #chooses this formatter for the log file
    console_handler.setLevel(logging.INFO) #sets the level of this logging informations to INFO in the console
    file_handler.setLevel(logging.INFO) #sets the level of this logging informations to INFO in the file
    if not logger.hasHandlers(): #if the logger does not have handlers it gives them to it, otherwise it clears the handlers and reassign them
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    else:
        logger.handlers.clear()
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

