from time import sleep
import matplotlib as mpl
from IPython import display
from  matplotlib import pyplot as plt

def locking_monitor(c):
    print("Starting locking monitor...")
    counter = 0
    limit = 200

    c.parameters.check_for_changed_parameters()

    while True:

        #if counter >= limit:
            #break

        counter +=1

        control_history = c.parameters.control_signal_history.value
        signal_history = c.parameters.monitor_signal_history.value

        display.clear_output(wait=True)
        plt.clf()

        fig, axs = plt.subplots(3,1, sharex=True, tight_layout=True)
        fig.suptitle("History data")

        ax0, ax1, ax2 = axs

        ax0.set_title("Control Signal")
        ax0.plot(control_history["times"], control_history["values"])

        ax1.set_title("Slow Control Signal")
        ax1.plot(control_history["slow_times"], control_history["slow_values"])

        ax2.set_title("Monitor Signal")
        ax2.plot(signal_history["times"], signal_history["values"])

        display.display(plt.gcf())

        sleep(2)

def find_locked_monitor_signal_height(monitor_signal, error_signal, x0, x1):
    monitor_signal_selected_region = monitor_signal[x0:x1]
    #expected_height = 
    return