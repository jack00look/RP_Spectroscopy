from time import sleep
import matplotlib as mpl
from IPython import display
from  matplotlib import pyplot as plt
from scipy.ndimage import gaussian_filter1d
import numpy as np

def locking_monitor(c, monitor_signal_reference_point):
    print("Starting locking monitor...")
    counter = 0
    limit = 200

    c.parameters.check_for_changed_parameters()

    unlocking_time_monitor_signal = 0 #unlocking time detection from monitor signal stats pov
    old_monitor_signal_against_reference_flag = 1
    monitor_signal_against_reference_flag = 1 #1 means locking is ok from the monitor signal stats pov

    while True:

        #if counter >= limit:
            #break

        counter +=1

        control_history = c.parameters.control_signal_history.value
        signal_history = c.parameters.monitor_signal_history.value

        display.clear_output(wait=True)
        #plt.clf()

        fig, axs = plt.subplots(3,1, sharex=True, tight_layout=True)
        fig.suptitle("History data")

        ax0, ax1, ax2 = axs

        ax0.set_title("Control Signal")
        ax0.plot(control_history["times"], control_history["values"])
        #evaluation of the derivateive of the control signal
        sigma = 0.1
        dt = control_history["times"][-1] - control_history["times"][-2]
        d_control_history = np.diff(gaussian_filter1d(control_history["values"], sigma=sigma))/dt
        ax0_d = ax0.twinx()
        ax0_d.plot(control_history["times"][:-1], d_control_history, color="red", alpha=0.5)

        ax1.set_title("Slow Control Signal")
        ax1.plot(control_history["slow_times"], control_history["slow_values"])
        #evaluation of the derivateive of the slow control signal
        dt_slow = control_history["slow_times"][-1] - control_history["slow_times"][-2]
        d_slow_control_history = np.diff(gaussian_filter1d(control_history["slow_values"], sigma = sigma))/dt
        ax1_d = ax1.twinx()
        ax1_d.plot(control_history["slow_times"][:-1], d_slow_control_history, color="red", alpha=0.5)

        ax2.set_title("Monitor Signal")
        ax2.plot(signal_history["times"], signal_history["values"])
        ax2.axhline(monitor_signal_reference_point[1], color="gray")

        evaluation_time = 100

        monitor_signal_mean, monitor_signal_std = monitor_signal_stats(signal_history["values"], evaluation_time)
        
        old_monitor_signal_against_reference_flag = monitor_signal_against_reference_flag

        if (monitor_signal_mean - 2*monitor_signal_std > monitor_signal_reference_point[1]) or (monitor_signal_mean + 2*monitor_signal_std < monitor_signal_reference_point[1]):
            monitor_signal_against_reference_flag = 0
            if old_monitor_signal_against_reference_flag and not monitor_signal_against_reference_flag:
                unlocking_time_monitor_signal = signal_history["times"][-evaluation_time]
                print("Monitor signal stats detected out of locking region at time:", unlocking_time_monitor_signal)
            elif not old_monitor_signal_against_reference_flag and not monitor_signal_against_reference_flag:
                print("System is still out of locking region at time:", signal_history["times"][-evaluation_time], "(unlocked for ", signal_history["times"][-evaluation_time]-unlocking_time_monitor_signal, "s)")
        else:
            monitor_signal_against_reference_flag = 1
            if not old_monitor_signal_against_reference_flag and monitor_signal_against_reference_flag:
                print("System re-entered in the locking region at time:", signal_history["times"][-evaluation_time], "(unlocked for ", signal_history["times"][-evaluation_time]-unlocking_time_monitor_signal, "s)")
            else:
                print("System is locked at time:", signal_history["times"][-evaluation_time])
        colours = ["orange", "green"]
        ax2.fill_between(signal_history["times"][-evaluation_time:], monitor_signal_mean - 2*monitor_signal_std, monitor_signal_mean + 2*monitor_signal_std, color=colours[monitor_signal_against_reference_flag], alpha=0.3)

        display.display(fig)

        plt.close(fig)

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

