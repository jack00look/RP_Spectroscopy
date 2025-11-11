# This file is part of Linien and based on redpid.
#
# Copyright (C) 2016-2024 Linien Authors (https://github.com/linien-org/linien#license)
#
# Linien is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Linien is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Linien.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
from scipy.signal import correlate

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get_lock_region(spectrum, target_idxs):
    """Given a spectrum and the points that the user selected for locking,
    calculate the region where locking will work. This is the region between the
    next zero crossings after the extrema."""
    part = spectrum[target_idxs[0] : target_idxs[1]]
    extrema = tuple(
        sorted([target_idxs[0] + np.argmin(part), target_idxs[0] + np.argmax(part)])
    )

    def walk_until_sign_changes(start_idx, direction):
        current_idx = start_idx
        start_sign = sign(spectrum[start_idx])
        while True:
            current_idx += direction
            if current_idx < 0:
                return 0
            if current_idx == len(spectrum):
                return current_idx - 1

            current_value = sign(spectrum[current_idx])
            current_sign = sign(current_value)

            if current_sign != start_sign:
                return current_idx - direction

    return (
        walk_until_sign_changes(extrema[0], -1),
        walk_until_sign_changes(extrema[1], 1),
    )

def get_lock_region_v2(spectrum, target_idxs, prepared_spectrum=None, time_scale=None):
    """Given a spectrum and the points that the user selected for locking,
    calculate the region where locking will work. This is the region between the
    next zero crossings after the extrema."""
    part = spectrum[target_idxs[0] : target_idxs[1]]
    extrema = tuple(
        sorted([target_idxs[0] + np.argmin(part), target_idxs[0] + np.argmax(part)])
    )

    def walk_until_sign_changes(start_idx, direction):
        current_idx = start_idx
        start_sign = sign(spectrum[start_idx])
        while True:
            current_idx += direction
            if current_idx < 0:
                return 0
            if current_idx == len(spectrum):
                return current_idx - 1

            current_value = sign(spectrum[current_idx])
            current_sign = sign(current_value)

            if current_sign != start_sign:
                #print('found sign change at', current_idx)
                return current_idx - direction
    
    def walk_until_slope_changes(start_idx, direction, prepared_spectrum, time_scale):

        prepared_spectrum = np.array(prepared_spectrum)
        derivative_prepared_spectrum = prepared_spectrum[1:] - prepared_spectrum[:-1]
        derivative_prepared_spectrum_smooth = get_diff_at_time_scale(sum_up_spectrum(derivative_prepared_spectrum), time_scale)

        zero_crossings_smooth_derivative = []
        previous_value = derivative_prepared_spectrum_smooth[0]
        for i in range(1, len(derivative_prepared_spectrum_smooth)):
            current_value = derivative_prepared_spectrum_smooth[i]
            if previous_value*current_value <= 0 :
                zero_crossings_smooth_derivative.append(i-time_scale//2) #we take into account the delay introduced by smoothing
            previous_value = current_value

        #zero_crossings_smooth_derivative = np.array(zero_crossings_smooth_derivative)
        logger.debug(f"Zero crossings of smoothed derivative: {zero_crossings_smooth_derivative}")
        if direction == -1:
            logger.debug(f"start_idx - time_scale//5: {start_idx - time_scale//5}")
            #considered_zeros = zero_crossings_smooth_derivative[:start_idx - time_scale//5] #start_idx and the maximum of that peak
            considered_zeros = [z for z in zero_crossings_smooth_derivative if z <= start_idx - time_scale//5]
            logger.debug(f"Considered zeros (backward): {considered_zeros}")
            #could not coincide due to the moving average. So we take a small margin
            return considered_zeros[-1]
        else:
            logger.debug(f"start_idx + time_scale//5: {start_idx + time_scale//5}")
            #considered_zeros = zero_crossings_smooth_derivative[start_idx + time_scale//5:]
            considered_zeros = [z for z in zero_crossings_smooth_derivative if z >= start_idx + time_scale//5]
            logger.debug(f"Considered zeros (forward): {considered_zeros}")
            return considered_zeros[0]
        

    def walk_until_signal_is_constant(start_idx, direction, prepared_spectrum):
        '''
        returns the index in the middle of the region where the signal is "constant" 
        in the desired direction with respect to start_idx
        '''

        current_idx = start_idx
        window_size = 70
        threshold = 0.0005
        while True:
            window = prepared_spectrum[current_idx:current_idx + window_size*direction:direction]
            #print('current idx is', current_idx, ' std dev in the window is', np.std(window))
            if np.std(window) < threshold:
                #print('found constant signal region at', current_idx)
                return int(current_idx + (window_size*direction)/2)
            current_idx += direction

    def walk_until_average_reaches_minimum_and_then_increases(start_idx, direction, prepared_spectrum):
        current_idx = start_idx
        window_size = 30
        previous_average = np.abs(np.mean(
            prepared_spectrum[current_idx : current_idx + window_size * direction : direction]
        ))
        while True:
            current_idx += direction
            current_average = np.abs(np.mean(
                prepared_spectrum[current_idx : current_idx + window_size * direction : direction]
            ))
            if current_average > previous_average:
                #print('found minimum average region at', current_idx)
                return int(current_idx + (window_size * direction) / 2)
            previous_average = current_average
        
    return (
        max(walk_until_slope_changes(extrema[0], -1, prepared_spectrum, time_scale), walk_until_sign_changes(extrema[0], -1)),
        min(walk_until_slope_changes(extrema[1], 1, prepared_spectrum, time_scale), walk_until_sign_changes(extrema[1], 1)),
    )


def get_time_scale(spectrum, target_idxs):
    logger.debug("Entered in get_time_scale")
    logger.debug(f"Spectrum length:{len(spectrum)}")
    logger.debug(f"Spectrum: {spectrum[:5]}...{spectrum[-5:]}")
    logger.debug(f"Target indices: {target_idxs}")
    part = spectrum[target_idxs[0] : target_idxs[1]]
    return np.abs(np.argmin(part) - np.argmax(part))


def sum_up_spectrum(spectrum):
    sum_ = 0
    summed = []

    for value in spectrum:
        summed.append(sum_ + value)
        sum_ += value

    return summed


def get_diff_at_time_scale(summed, xscale):
    new = []

    for idx, value in enumerate(summed):
        if idx < xscale:
            old = 0
        else:
            old = summed[idx - xscale]

        new.append(value - old)

    return new


def sign(value):
    return 1 if value >= 1 else -1


def get_target_peak(summed_xscaled, target_idxs):
    selected_region = summed_xscaled[target_idxs[0] : target_idxs[1]]
    # in the selected region, we may have 1 minimum and one maximum
    # we know that we are interested in the "left" extremum --> sort extrema
    # by index and take the first one
    extremum = np.min([np.argmin(selected_region), np.argmax(selected_region)])
    current_idx = target_idxs[0] + extremum
    return current_idx


def get_all_peaks(summed_xscaled, target_idxs):
    current_idx = get_target_peak(summed_xscaled, target_idxs)

    peaks = []

    peaks.append((current_idx, summed_xscaled[current_idx]))

    while True:
        if current_idx == 0:
            break
        current_idx -= 1

        value = summed_xscaled[current_idx]
        last_peak_position, last_peak_height = peaks[-1]

        if sign(last_peak_height) == sign(value):
            if np.abs(value) > np.abs(last_peak_height):
                peaks[-1] = (current_idx, value)
        else:
            peaks.append((current_idx, value))

    return peaks

def get_all_peaks_v2(summed_xscaled, target_idxs):
    current_idx = get_target_peak(summed_xscaled, target_idxs)

    peaks = []
    print('first peak is in ', current_idx, ' with value ', summed_xscaled[current_idx])
    peaks.append((current_idx, summed_xscaled[current_idx]))
    current_idx -= 5
    peaks.append((current_idx, summed_xscaled[current_idx]))
    dummy_idx = current_idx
    dummy_value = summed_xscaled[dummy_idx]

    while True:
        if current_idx == 0:
            break
        current_idx -= 1

        value = summed_xscaled[current_idx]
        last_peak_position, last_peak_height = peaks[-1]

        if sign(last_peak_height) == sign(value):
            if np.abs(value) > np.abs(last_peak_height):
                peaks[-1] = (current_idx, value)
        else:
            peaks.append((current_idx, value))
            if peaks[-2] == (dummy_idx, dummy_value):
                peaks.pop(-2)
    if peaks[-1] == (dummy_idx, dummy_value):
        peaks.pop(-1)

    return peaks



def crop_spectra_to_same_view(spectra_with_jitter):
    logger.debug("Entered in crop_spectra_to_same_view")
    cropped_spectra = []

    shifts = [1] # first spectrum is the reference

    correlations = []

    for idx, spectrum in enumerate(spectra_with_jitter[1:]):
        correlate_temp = correlate(spectra_with_jitter[0], spectrum)
        correlations.append(np.array(correlate_temp))
        shift = np.argmax(correlate_temp) - len(spectrum)
        
        #logger.debug(f"correlation max: {np.max(correlate_temp)}")
        #logger.debug(f"correlation argmax: {np.argmax(correlate_temp)}")
        shifts.append(-shift)

    logger.debug(f"Shifts calculated for cropping: {shifts}")

    min_shift = min(shifts)
    max_shift = max(shifts)

    length_after_crop = len(spectra_with_jitter[0]) - (max_shift - min_shift)

    for shift, spectrum in zip(shifts, spectra_with_jitter):
        cropped_spectra.append(spectrum[shift - min_shift :][:length_after_crop])

    return cropped_spectra, -min_shift + 1
