"""
Interferometer hardware control utilities.

Originally from primary_mirror/interferometer_utils.py
Moved to interferometer submodule for better organization.

This module provides:
- Direct interferometer measurement control
- Zernike coefficient acquisition 
- Automated tip/tilt/power correction
- Alignment maintenance routines
"""

import os
import time
import requests
import datetime
import numpy as np

def take_interferometer_measurements(path, num_avg=10, onboard_averaging=True, savefile=None):
    """
    Take interferometer measurements and save data.
    
    Args:
        path (str): Directory path to save measurements
        num_avg (int): Number of measurements to average
        onboard_averaging (bool): Use hardware averaging vs software averaging
        savefile (str): Optional filename, defaults to timestamp
    
    Returns:
        None: Data is saved to specified path
    """
    current_time = datetime.datetime.now().strftime('%H%M%S')
    if savefile is None:
        savefile = current_time
    
    if onboard_averaging:
        tic = time.time()
        payload = {"analysis": "analyzed", "fileName": path + savefile, "count": str(num_avg)}
        meas = requests.get('http://localhost/WebService4D/WebService4D.asmx/AverageMeasure', params=payload)
        sav = requests.get('http://localhost/WebService4D/WebService4D.asmx/SaveArray', params=payload)
        print(str(round(time.time()-tic, 3)), ' seconds to measure, analyze + save')
    else:
        time_folder = path + current_time + '/'
        os.mkdir(time_folder)
        tic = time.time()
        for i in np.arange(num_avg):
            payload = {"analysis": "analyzed", "fileName": time_folder + str(i)}
            meas = requests.get('http://localhost/WebService4D/WebService4D.asmx/Measure', params=payload)
            sav = requests.get('http://localhost/WebService4D/WebService4D.asmx/SaveArray', params=payload)
        print(str(round(time.time()-tic, 3)), ' seconds to measure, analyze + save')

def take_interferometer_coefficients(num_avg=10):
    """
    Acquire Zernike coefficients directly from interferometer.
    
    Args:
        num_avg (int): Number of measurements to average
    
    Returns:
        str: Filename containing the coefficient data
    """
    current_time = datetime.datetime.now().strftime('%H%M%S')
    savefile = current_time
    payload = {"analysis": "zernikeresidual", "count": str(num_avg), "useNAN": 'false'}
    meas = requests.get('http://localhost/WebService4D/WebService4D.asmx/AverageMeasure', params=payload)
    sav = requests.get('http://localhost/WebService4D/WebService4D.asmx/GetZernikeCoeff', params=payload)
    output = sav.content.decode('utf-8')
    first_split = output.split('output/')[-1]
    filename = first_split.split('</string>')[0]
    return filename

def correct_tip_tilt_power(zernikes, s, gain):
    """
    Apply tip, tilt, and power corrections using stage controller.
    
    Args:
        zernikes (array): Zernike coefficients from interferometer
        s: Stage controller object (SMC100 or similar)
        gain (float): Correction gain factor
    
    Returns:
        None: Corrections are applied directly to hardware
    """
    print('Tilt: ' + str(zernikes[2]))
    print('Tip: ' + str(zernikes[1]))
    print('Power: ' + str(zernikes[3]))

    delta_tilt = gain * 0.18 * zernikes[2] / 20
    delta_tip = gain * 0.175 * zernikes[1] / 20
    delta_power = -gain * 2 * zernikes[3] / 4.1

    if True:
        s.setPositionRel(delta_tilt, channel=1)
        s.setPositionRel(delta_tip, channel=2)
        s.setPositionRel(delta_power, channel=3)

def hold_alignment(duration, number_frames_avg, s, s_gain):
    """
    Maintain interferometer alignment for specified duration.
    
    Args:
        duration (float): Time in seconds to maintain alignment
        number_frames_avg (int): Number of frames to average per correction
        s: Stage controller object
        s_gain (float): Stage correction gain
    
    Returns:
        None: Runs alignment loop for specified duration
    """
    tic = time.time()
    while time.time() - tic < duration:
        coef_filename = take_interferometer_coefficients(number_frames_avg)
        coef_file = "C:/inetpub/wwwroot/output/" + coef_filename
        zernikes = np.fromfile(coef_file, dtype=np.dtype('d'))
        correct_tip_tilt_power(zernikes, s, s_gain)
        time.sleep(10)

def start_alignment(iterations, number_frames_avg, s, s_gain):
    """
    Perform initial alignment sequence.
    
    Args:
        iterations (int): Number of alignment iterations
        number_frames_avg (int): Number of frames to average per correction
        s: Stage controller object
        s_gain (float): Stage correction gain
    
    Returns:
        None: Performs alignment iterations
    """
    for i in range(iterations):
        coef_filename = take_interferometer_coefficients(number_frames_avg)
        coef_file = "C:/inetpub/wwwroot/output/" + coef_filename
        zernikes = np.fromfile(coef_file, dtype=np.dtype('d'))
        correct_tip_tilt_power(zernikes, s, s_gain)
        time.sleep(1)
