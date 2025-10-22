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
import matplotlib.pyplot as plt


def get_lock_region(spectrum, target_idxs, prepared_spectrum=None):
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
    
    def walk_until_slope_changes(start_idx, direction, prepared_spectrum):
        current_idx = start_idx
        jump = 5
        relative_variations = []
        while True:
            relative_variation = (prepared_spectrum[current_idx+jump*direction] - prepared_spectrum[current_idx])/prepared_spectrum[current_idx+jump*direction]
            relative_variations.append(relative_variation)
            if np.abs(relative_variation) > 2: # arbitrary threshold to detect slope change
                return int((current_idx+start_idx)/2)
            current_idx += direction
        
    return (
        #walk_until_sign_changes(extrema[0], -1),
        #walk_until_sign_changes(extrema[1], 1),
        walk_until_slope_changes(extrema[0], -1, prepared_spectrum),
        walk_until_slope_changes(extrema[1], 1, prepared_spectrum),
    )


def get_time_scale(spectrum, target_idxs):
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
    return 1 if value >= 0 else -1


def get_target_peak(summed_xscaled, target_idxs):
    selected_region = summed_xscaled[target_idxs[0] : target_idxs[1]]
    # in the selected region, we may have 1 minimum and one maximum
    # we know that we are interested in the "left" extremum --> sort extrema
    # by index and take the first one
    print('extrema are', np.argmin(selected_region), np.argmax(selected_region))
    print('selected region is from ', target_idxs[0], 'to', target_idxs[1])
    extremum = np.min([np.argmin(selected_region), np.argmax(selected_region)])
    print('extremum is at', extremum)

    current_idx = target_idxs[0] + extremum #if there is a minimum or a maximum before the 
    #zero-crossing, inside the target region, we will set the region within which 
    #looking for peaks starting from 0 up to that point, otherwise we end as before at the left target point
    return current_idx


def get_all_peaks(summed_xscaled, target_idxs):
    current_idx = get_target_peak(summed_xscaled, target_idxs)

    peaks = []
    print('first peak is in ', current_idx, ' with value ', summed_xscaled[current_idx])
    peaks.append((current_idx, summed_xscaled[current_idx]))

    while True:
        if current_idx == 0:
            break
        current_idx -= 1

        value = summed_xscaled[current_idx]
        last_peak_position, last_peak_height = peaks[-1]

        if sign(last_peak_height) == sign(value):
            print(peaks)
            if np.abs(value) > np.abs(last_peak_height):
                peaks[-1] = (current_idx, value)
        else:
            peaks.append((current_idx, value))

    return peaks


def crop_spectra_to_same_view(spectra_with_jitter):
    cropped_spectra = []

    shifts = []

    for idx, spectrum in enumerate(spectra_with_jitter):
        shift = np.argmax(correlate(spectra_with_jitter[0], spectrum)) - len(spectrum)

        shifts.append(-shift)

    min_shift = min(shifts)
    max_shift = max(shifts)

    length_after_crop = len(spectra_with_jitter[0]) - (max_shift - min_shift)

    for shift, spectrum in zip(shifts, spectra_with_jitter):
        cropped_spectra.append(spectrum[shift - min_shift :][:length_after_crop])

    return cropped_spectra, -min_shift + 1
