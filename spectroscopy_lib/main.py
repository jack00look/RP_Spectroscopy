from linien_client.device import Device
from linien_client.connection import LinienClient
import matplotlib.pyplot as plt
import numpy as np
from linien_common.common import  MHz, Vpp, ANALOG_OUT_V,AutolockMode
import pickle
import time
from scipy.signal import correlate
from scipy.stats import pearsonr
import pylab as pl
import os
from IPython import display
import logging
import sys

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

HISTORY_FILE = '/home/jacklook/Documents/Projects/CodeRed/history.npy'

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

def find_shift(sweep_signal,reference_signal):
    """
    Find how much the reference signal needs to be shifted to match the sweep signal
    """
    shift = np.argmax(correlate(sweep_signal[10:-10],reference_signal,mode='full')) + 10 - len(reference_signal)
    return shift

def correlate_signals(sweep_signal,reference_signal):
    """
    Shift the reference signal to match the sweep signal, and return the x axis for both signals
    """
    shift = find_shift(sweep_signal,reference_signal)
    xaxis_1 = np.arange(len(sweep_signal))
    xaxis_2 = np.arange(len(reference_signal))+shift
    return xaxis_1,sweep_signal,xaxis_2,reference_signal

def find_correlation(sweep_signal,reference_signal):
    """
    Find the correlation between the sweep signal and the reference signal, and return the correlation coefficient and the length of the match
    I both shift the reference signal to match the sweep signal and rescale the amplitude of the sweep signal to match the reference signal
    """
    shift = find_shift(sweep_signal,reference_signal)
    xmin_sweep = np.max(np.array([0,shift]))
    xmax_sweep = np.min(np.array([len(sweep_signal),shift+len(reference_signal)]))
    xmin_ref = np.max(np.array([0,-shift]))
    xmax_ref = np.min(np.array([len(reference_signal),-shift+len(sweep_signal)]))
    # correlation is zero if the signals are not overlapping
    len_match = xmax_sweep - xmin_sweep
    if xmin_sweep == xmax_sweep:
        return 0,0
    sweep_signal_cropped = sweep_signal[xmin_sweep:xmax_sweep]
    reference_signal_cropped = reference_signal[xmin_ref:xmax_ref]
    a_coeff = np.sum(reference_signal_cropped**2)/np.sum(sweep_signal_cropped*reference_signal_cropped)
    sweep_signal_cropped = sweep_signal_cropped * a_coeff
    sweep_signal_cropped_zeroavg = sweep_signal_cropped - np.mean(sweep_signal_cropped)
    reference_signal_cropped_zeroavg = reference_signal_cropped - np.mean(reference_signal_cropped)
    sum1 = np.sum(sweep_signal_cropped_zeroavg**2)
    sum2 = np.sum(reference_signal_cropped_zeroavg**2)
    # avoid division by zero
    if sum1 == 0 or sum2 == 0:
        return 0,0
    r_coeff = np.sum(sweep_signal_cropped_zeroavg*reference_signal_cropped_zeroavg)/np.sqrt(sum1*sum2)
    return r_coeff,len_match


FOLDER_REFERENCE_LINES = '/home/jacklook/Documents/Projects/CodeRed'


class RP_linien:
    def __init__(self, host, username='root', password='root',port = 18862):
        self.host = host
        self.username = username
        self.password = password
        self.device = Device(host=host, port=port,username=username, password=password)
        self.client = LinienClient(self.device)
        self.client.connect(autostart_server=True, use_parameter_cache=False)
        self.D2_LINE_0 = np.load(FOLDER_REFERENCE_LINES + '/D2_REFERENCE_LINE_0.npy')
        self.D2_LINE_1 = np.load(FOLDER_REFERENCE_LINES + '/D2_REFERENCE_LINE_1.npy')
        self.D2_LINE_2 = np.load(FOLDER_REFERENCE_LINES + '/D2_REFERENCE_LINE_2.npy')
        self.D2_LINE_0_START = 550
        self.D2_LINE_0_END = 800

        c = self.client

        c.parameters.analog_out_1.value = 0.9/ANALOG_OUT_V
        c.parameters.analog_out_2.value = 0.9/ANALOG_OUT_V
        self.offset = 0.9
        self.smalloffset = 0.

        c.parameters.dual_channel.value = False
        c.parameters.channel_mixing.value = int(0)

        c.parameters.mod_channel.value = 2 -1
        c.parameters.modulation_amplitude.value = 1.8*Vpp
        c.parameters.modulation_frequency.value = 0.05*MHz

        c.parameters.sweep_channel.value = 1 -1
        c.parameters.sweep_amplitude.value = 0.9
        c.parameters.sweep_center.value = 0
        c.parameters.sweep_speed.value = 9

        c.parameters.demodulation_phase_a.value = 150
        c.parameters.demodulation_multiplier_a.value = 1
        c.parameters.offset_a.value = 0
        c.parameters.invert_a.value = False
        c.parameters.filter_automatic_a.value = False
        c.parameters.filter_1_enabled_a.value = True
        c.parameters.filter_1_type_a.value = 0 # low pass
        c.parameters.filter_1_frequency_a.value = 500 # Hz
        c.parameters.filter_2_enabled_a.value = True
        c.parameters.filter_2_type_a.value = 0 # low pass
        c.parameters.filter_2_frequency_a.value = 500 # Hz
        c.parameters.control_channel.value = 1 -1
        c.parameters.slow_control_channel.value = 3 -1
        c.parameters.polarity_fast_out1.value = 0
        c.parameters.polarity_analog_out0.value = 1
        
        c.parameters.pid_on_slow_enabled.value = True
        c.parameters.p.value = 5000
        c.parameters.i.value = 100
        c.parameters.d.value = 0
        c.parameters.pid_on_slow_strength.value = 1000

        c.parameters.autolock_mode_preference.value = AutolockMode.ROBUST
        c.parameters.autolock_determine_offset.value = False

        c.connection.root.write_registers()
        self.update()

    def update_pid(self, p = None, i = None, d = None, slow_strength = None):
        if p is None:
            p = self.pid_p
        if i is None:
            i = self.pid_i
        if d is None:
            d = self.pid_d
        if slow_strength is None:
            slow_strength = self.pid_slow_strength
        self.pid_p = p
        self.pid_i = i
        self.pid_d = d
        self.pid_slow_strength = slow_strength

        self.client.parameters.p.value = p
        self.client.parameters.i.value = i
        self.client.parameters.d.value = d
        self.client.parameters.pid_on_slow_strength.value = slow_strength
        self.update()
    
    def get_pid_values(self):
        return (self.pid_p, self.pid_i, self.pid_d, self.pid_slow_strength)
    
    def update_filter(self,filter_frequency):
        self.filter_frequency = filter_frequency
        self.client.parameters.filter_1_frequency_a.value = filter_frequency
        self.client.parameters.filter_2_frequency_a.value = filter_frequency
        self.update()

    def get_control_history_length(self):
        p = self.client.parameters.control_signal_history_length.value
        return p
    
    def update_control_history_length(self, length):
        self.client.parameters.control_signal_history_length.value = length
        self.update()

    def get_filter_frequency(self):
        return self.filter_frequency

    def update_OFFSET(self, offset):
        self.offset = offset
        self.client.parameters.analog_out_2.value = offset/ANALOG_OUT_V
        self.update()
    
    def update_smallOFFSET(self, offset):
        self.smalloffset = self.smalloffset + offset
        self.client.parameters.analog_out_1.value = (offset+0.9)/ANALOG_OUT_V
        self.update()

    def get_smallOFFSET(self):
        return self.smalloffset

    def get_OFFSET(self):
        return self.offset

    def update_phase(self, phase):
        self.phase = phase
        self.client.parameters.demodulation_phase_a.value = phase
        self.update()
    
    def get_phase(self):
        return self.phase
    
    def optimize_phase(self):
        phases = np.linspace(0, 180,20)
        signal_strengths = np.zeros(len(phases))
        for i in range(len(phases)):
            self.update_phase(phases[i])
            time.sleep(1.)
            signal = self.get_sweep_signal_raw()
            signal_strengths[i] = np.var(np.abs(signal))
        plt.plot(phases, signal_strengths)
        plt.xlabel('Phase [°]')
        plt.ylabel('Signal strength [V²]')
        plt.title('Phase optimization')
        ind = np.argmax(signal_strengths)
        self.update_phase(phases[ind])
        print('optimal phase = {}'.format(phases[ind]))
        return


    def update(self):
        self.client.connection.root.write_registers()
        self.client.parameters.check_for_changed_parameters()

    def get_lock_history(self):
        control_signal_history = self.client.parameters.control_signal_history.value
        monitor_signal_history = self.client.parameters.monitor_signal_history.value
        dict = {}
        dict['fast_control_values'] = np.array(control_signal_history['values'])/(2*Vpp)
        dict['fast_control_times'] = np.array(control_signal_history['times'])
        if not(bool(self.client.parameters.dual_channel.value)):
            dict['monitor_values'] = np.array(monitor_signal_history['values'])/(2*Vpp)
            dict['monitor_times'] = np.array(monitor_signal_history['times'])
        if bool(self.client.parameters.pid_on_slow_enabled.value):
            dict['slow_control_values'] = np.array(control_signal_history['slow_values'])/(2**13-1)*0.9
            dict['slow_control_times'] = np.array(control_signal_history['slow_times'])
        self.history = dict
        return dict
    
    def wait_for_lock_status(self, should_be_locked):
        """A helper function that waits until the laser is locked or unlocked."""
        counter = 0
        while True:
            to_plot = pickle.loads(self.client.parameters.to_plot.value)
            is_locked = "error_signal" in to_plot

            if is_locked == should_be_locked:
                break

            counter += 1
            if counter > 10:
                raise Exception("waited too long")

            time.sleep(1)
    
    def get_sweep_signal(self):
        self.client.connection.root.start_sweep()
        self.wait_for_lock_status(False)
        to_plot = pickle.loads(self.client.parameters.to_plot.value)
        dual_channel = bool(self.client.parameters.dual_channel.value)
        if dual_channel:
            mixing = self.client.parameters.channel_mixing.value
            error_signal_1 = np.array(to_plot['error_signal_1'])/(2*Vpp)
            error_signal_2 = np.array(to_plot['error_signal_2'])/(2*Vpp)
            error_signal = ((error_signal_1*(127-mixing) + error_signal_2*(127+mixing))/254)
        else:
            error_signal = np.array(to_plot['error_signal_1'])/(2*Vpp)
        self.sweep_signal = error_signal
        return error_signal
    
    def get_sweep_signal_raw(self):
        self.client.connection.root.start_sweep()
        self.wait_for_lock_status(False)
        to_plot = pickle.loads(self.client.parameters.to_plot.value)
        dual_channel = bool(self.client.parameters.dual_channel.value)
        if dual_channel:
            mixing = self.client.parameters.channel_mixing.value
            error_signal_1 = np.array(to_plot['error_signal_1']).astype(np.float64)
            error_signal_2 = np.array(to_plot['error_signal_2']).astype(np.float64)
            error_signal = ((error_signal_1*(127-mixing) + error_signal_2*(127+mixing))/254)
        else:
            error_signal = np.array(to_plot['error_signal_1']).astype(np.float64)
        self.sweep_signal = error_signal
        return error_signal
    
    def lock_laser(self):
        self.delete_history()
        error_signal = self.get_sweep_signal_raw()
        shift = int(np.argmax(correlate(error_signal[10:-10], self.D2_LINE_0,mode='valid')))+10
        x0 = self.D2_LINE_0_START + shift
        x1 = self.D2_LINE_0_END + shift
        plt.plot(error_signal)
        plt.plot(np.arange(len(self.D2_LINE_0))+shift,self.D2_LINE_0,'--')
        plt.axvline(x0, color='r', linestyle='--')
        plt.axvline(x1, color='r', linestyle='--')
        self.client.connection.root.start_autolock(x0,x1,pickle.dumps(error_signal))
        try:
            self.wait_for_lock_status(True)
            print("locking the laser worked \o/")
        except Exception:
            print("locking the laser failed :(")

    def scan_lines(self):
        V_offset_scan = np.linspace(0.05,1.75,20)
        correlations = np.zeros((3,len(V_offset_scan)))
        len_matches = np.zeros((3,len(V_offset_scan)))
        signals = np.zeros((len(V_offset_scan),2048))
        for i in range(len(V_offset_scan)):
            print('scanning V_offset = {:.2f}'.format(V_offset_scan[i]))
            self.update_OFFSET(V_offset_scan[i])
            time.sleep(1.)
            signal = self.get_sweep_signal_raw()
            correlation,len_match = find_correlation(signal,self.D2_LINE_0)
            correlations[0,i] = correlation
            len_matches[0,i] = len_match
            correlation,len_match = find_correlation(signal,self.D2_LINE_1)
            correlations[1,i] = correlation
            len_matches[1,i] = len_match
            correlation,len_match = find_correlation(signal,self.D2_LINE_2)
            correlations[2,i] = correlation
            len_matches[2,i] = len_match
            signals[i,:] = signal[:]
        fig,ax = plt.subplots(ncols = 1,nrows = 4,figsize=(10,10),tight_layout=True)
        ax[0].plot(V_offset_scan,correlations[0,:],label='D2_LINE_0',color='r')
        ax[0].plot(V_offset_scan,correlations[1,:],label='D2_LINE_1',color='g')
        ax[0].plot(V_offset_scan,correlations[2,:],label='D2_LINE_2',color='b')
        ax[0].legend()
        ax[0].set_xlabel('V_offset [V]')
        ax[0].set_ylabel('Correlation')
        ind_0 = find_best_correlation(correlations[0,:],len_matches[0,:],len(self.D2_LINE_0))
        ax[0].axvline(x=V_offset_scan[ind_0], color='r', linestyle='--')
        ind_1 = find_best_correlation(correlations[1,:],len_matches[1,:],len(self.D2_LINE_1))
        ax[0].axvline(x=V_offset_scan[ind_1], color='g', linestyle='--')
        ind_2 = find_best_correlation(correlations[2,:],len_matches[2,:],len(self.D2_LINE_2))
        ax[0].axvline(x=V_offset_scan[ind_2], color='b', linestyle='--')
        x1,s1,x2,s2 = correlate_signals(signals[ind_0,:],self.D2_LINE_0)
        ax[1].plot(x1,s1)
        ax[1].plot(x2,s2,'--')
        ax[1].set_title('D2_LINE_0, Vscan = {:.2f}, correlation = {:.2f}'.format(V_offset_scan[ind_0],correlations[0,ind_0]))
        x1,s1,x2,s2 = correlate_signals(signals[ind_1,:],self.D2_LINE_1)
        ax[2].plot(x1,s1)
        ax[2].plot(x2,s2,'--')

        ax[2].set_title('D2_LINE_1, Vscan = {:.2f}, correlation = {:.2f}'.format(V_offset_scan[ind_1],correlations[0,ind_1]))
        x1,s1,x2,s2 = correlate_signals(signals[ind_2,:],self.D2_LINE_2)
        ax[3].plot(x1,s1)
        ax[3].plot(x2,s2,'--')
        ax[3].set_title('D2_LINE_2, Vscan = {:.2f}, correlation = {:.2f}'.format(V_offset_scan[ind_2],correlations[0,ind_2]))

        self.D2_LINE_0_offset = V_offset_scan[ind_0]
        self.D2_LINE_1_offset = V_offset_scan[ind_1]
        self.D2_LINE_2_offset = V_offset_scan[ind_2]
        self.scan_V_offset = V_offset_scan
        self.scan_signals = signals
        return V_offset_scan, signals
    
    def plot_scan(self):
        V_offset_scan = self.scan_V_offset
        signals = self.scan_signals
        L = len(V_offset_scan)
        fig,ax = plt.subplots(ncols=1,nrows = L,figsize=(10,3*L),tight_layout=True)
        for i in range(L):
            ax[i].plot(signals[i,:])
            ax[i].set_title('V_offset = {:.2f}'.format(V_offset_scan[i]))

    def get_line_positions(self):
        dict = {}
        dict['D2_LINE_0'] = self.D2_LINE_0_offset
        dict['D2_LINE_1'] = self.D2_LINE_1_offset
        dict['D2_LINE_2'] = self.D2_LINE_2_offset
        return dict
    
    def get_reference_lines(self):
        dict = {}
        dict['D2_LINE_0'] = self.D2_LINE_0
        dict['D2_LINE_1'] = self.D2_LINE_1
        dict['D2_LINE_2'] = self.D2_LINE_2
        return dict
    
    def update_line_positions(self,line_name,offset):
        if line_name == 'D2_LINE_0':
            self.D2_LINE_0_offset = offset
        elif line_name == 'D2_LINE_1':
            self.D2_LINE_1_offset = offset
        elif line_name == 'D2_LINE_2':
            self.D2_LINE_2_offset = offset
        else:
            raise Exception('line name not recognized')

    def center_line(self,line_name):
        if line_name == 'D2_LINE_0':
            line = self.D2_LINE_0
            offset = self.D2_LINE_0_offset
        elif line_name == 'D2_LINE_1':
            line = self.D2_LINE_1
            offset = self.D2_LINE_1_offset
        elif line_name == 'D2_LINE_2':
            line = self.D2_LINE_2
            offset = self.D2_LINE_2_offset
        linewidth = len(line)
        free_space = 2048 - linewidth
        JITTER_THR = 100
        self.update_OFFSET(offset)
        time.sleep(1.)
        print('START offset = {}'.format(offset))
        correlations = []
        offset_0 = offset
        line_outside_arr = []
        time_0 = time.time()
        times = []
        shifts = []
        thr_cnt = 5
        line_outside = True
        frequence_stable = False
        cnt = 0
        time_last = 0
        ind_off_try = 0
        offset_try = [0.04,-0.04,0.08,-0.08,0.12,-0.12]
        while True:
            self.get_sweep_signal_raw()
            times.append(time.time() - time_0)
            correlations.append(find_correlation(self.sweep_signal,line)[0])
            shifts.append(find_shift(self.sweep_signal,line))
            plt.clf()
            plot1 = plt.subplot2grid((2,1),(0,0))
            plot2 = plt.subplot2grid((2,1),(1,0))
            plot1.set_title('Time = {:.2f}, offset = {:.2f}'.format(times[-1],offset))
            plot1.plot(self.sweep_signal)
            plot1.plot(np.arange(len(line))+shifts[-1],line,'--')
            plot1.set_ylim(-800,800)
            plot2.scatter(times,shifts)
            display.display(plt.gcf())
            if correlations[-1] < 0.5:
                line_outside_arr.append(True)
                if not(line_outside):
                    print('line has escaped')
                line_outside = True
                cnt = 0
            else:
                line_outside_arr.append(False)
                if line_outside:
                    print('line is now inside')
                line_outside = False
                cnt += 1
            line_outside_arr_temp = np.array(line_outside_arr)[int(np.max(np.array([-6,-len(line_outside_arr)]))):]
            nb_recent_line_outside = np.sum(line_outside_arr_temp)
            if (nb_recent_line_outside>3) and ((times[-1] - time_last) > 30):
                if ind_off_try == len(offset_try):
                    print('could not find a good offset starting from {}'.format(offset_0))
                    return
                print('this offset is not good, we need to scan it a bit')
                offset = offset_0 + offset_try[ind_off_try]
                print('trying offset = {}'.format(offset))
                ind_off_try += 1
                time_last = times[-1]
                self.update_OFFSET(offset)
                time.sleep(2.)

            if cnt > thr_cnt:
                avg_shift = np.mean(shifts[-thr_cnt+1:])
                std_shift = np.std(shifts[-thr_cnt+1:])
                plot2.axhline(avg_shift, color='r', linestyle='-')
                plot2.axhline(avg_shift+std_shift, color='r', linestyle='--')
                plot2.axhline(avg_shift-std_shift, color='r', linestyle='--')
                frequence_stable = std_shift < JITTER_THR
                #display.display(plt.gcf())

                #frequence_stable = np.all(np.less(np.abs(np.diff(shifts)[-thr_cnt+1:]), JITTER_THR*np.ones(thr_cnt-1)))
                if not frequence_stable:
                    print('frequence not stable enough')
                if frequence_stable:
                    space_left = shifts[-1]
                    space_right = 2048 - linewidth - shifts[-1]
                    print('space_left = {}, space_right = {}'.format(space_left,space_right))
                    if (space_left > free_space/4) and (space_right > free_space/4):
                        self.update_line_positions(line_name,self.get_OFFSET())
                        plt.plot(self.sweep_signal)
                        plt.plot(np.arange(len(line))+shifts[-1],line,'--')
                        print('line is centered')
                        return
                    elif space_left < free_space/4:
                        print('need to decrease frequency, so we need to increase offset')
                        offset = offset + 0.02
                    else:
                        print('need to increase frequency, so we need to decrease offset')
                        offset = offset - 0.02
                    self.update_OFFSET(offset)
                    time.sleep(2.)
                    cnt = 0
                    line_inside = False
                    frequence_stable = False
            time.sleep(2.)
            display.clear_output(wait=True)



    def unlock_laser(self):
        last_offset = self.get_OFFSET()
        self.update_OFFSET(1.75)
        time.sleep(1.)
        self.update_OFFSET(0.05)
        time.sleep(1.)
        self.update_OFFSET(last_offset)
        print('laser unlocked')
        return
    
    def start_saving_history(self):
        last_time = 0
        while True:
            recent_lock_history = self.get_lock_history()
            times = recent_lock_history['fast_control_times']
            fast_values = recent_lock_history['fast_control_values']
            slow_values = recent_lock_history['slow_control_values']
            history_to_date = None
            if os.path.exists(HISTORY_FILE):
                history_to_date = np.load(HISTORY_FILE)
                times_to_date = history_to_date[0,:]
                last_time = times_to_date[-1]
                fast_values_to_date = history_to_date[1,:]
                slow_values_to_date = history_to_date[2,:]
                ind_new = np.where(times > last_time)
                times_new = times[ind_new]
                fast_values_new = fast_values[ind_new]
                slow_values_new = slow_values[ind_new]
                times = np.concatenate((times_to_date,times_new))
                fast_values = np.concatenate((fast_values_to_date,fast_values_new))
                slow_values = np.concatenate((slow_values_to_date,slow_values_new))
                new_history = np.array([times,fast_values,slow_values])
                np.save(HISTORY_FILE,new_history)
                
            else:
                new_history = np.array([times,fast_values,slow_values])
                np.save(HISTORY_FILE,new_history)
            print('saving history')
            time.sleep(5.)

    def get_whole_history(self):
        if os.path.exists(HISTORY_FILE):
            history = np.load(HISTORY_FILE,allow_pickle=True)
            times = history[0,:]
            fast_values = history[1,:]
            slow_values = history[2,:]
            return times,fast_values,slow_values
        else:
            print('no history file found')
            return None
        
    def delete_history(self):
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            print('history file deleted')
        else:
            print('no history file found')
            return None

    
def plot_lock_history(signals):
    fig,ax = plt.subplots(tight_layout=True)
    keys = signals.keys()
    keys = [key for key in keys if '_times' in key]
    keys = [key[:-6] for key in keys]
    for key in keys:
        ax.plot(signals[key+'_times'], signals[key+'_values'], label=key)
    ax.legend()
    ax.set_xlabel('Time [s]')
    ax.set_ylabel('Voltage [V]')


