import os
import time
import requests
import datetime
import numpy as np

def take_interferometer_measurements(path,num_avg=10, onboard_averaging=True, savefile = None):
    current_time = datetime.datetime.now().strftime('%H%M%S')
    if savefile is None:
        savefile = current_time
    if onboard_averaging:
        tic = time.time()
        payload = {"analysis": "analyzed", "fileName": path + savefile, "count": str(num_avg)}
        meas = requests.get('http://localhost/WebService4D/WebService4D.asmx/AverageMeasure', params=payload)
        sav = requests.get('http://localhost/WebService4D/WebService4D.asmx/SaveArray', params=payload)
        print(str(round(time.time()-tic,3)), ' seconds to measure, analyze + save')
    else:
        time_folder = path + current_time + '/'
        os.mkdir(time_folder)
        tic = time.time()
        for i in np.arange(num_avg):
            payload = {"analysis": "analyzed", "fileName": time_folder + str(i)}
            meas = requests.get('http://localhost/WebService4D/WebService4D.asmx/Measure', params=payload)
            sav = requests.get('http://localhost/WebService4D/WebService4D.asmx/SaveArray', params=payload)
        print(str(round(time.time()-tic,3)), ' seconds to measure, analyze + save')

def take_interferometer_coefficients(num_avg=10):
    current_time = datetime.datetime.now().strftime('%H%M%S')
    savefile = current_time
    payload = {"analysis": "zernikeresidual", "count": str(num_avg), "useNAN": 'false'}
    meas = requests.get('http://localhost/WebService4D/WebService4D.asmx/AverageMeasure', params=payload)
    sav = requests.get('http://localhost/WebService4D/WebService4D.asmx/GetZernikeCoeff', params=payload)
    output = sav.content.decode('utf-8')
    first_split = output.split('output/')[-1]
    filename = first_split.split('</string>')[0]
    return filename

def correct_tip_tilt_power(zernikes,s,gain):
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
    tic = time.time()
    while time.time() - tic < duration:
        coef_filename = take_interferometer_coefficients(number_frames_avg)
        coef_file = "C:/inetpub/wwwroot/output/" + coef_filename
        zernikes = np.fromfile(coef_file, dtype=np.dtype('d'))
        correct_tip_tilt_power(zernikes, s, s_gain)
        time.sleep(10)

def start_alignment(iterations, number_frames_avg, s, s_gain):
    for i in range(iterations):
        coef_filename = take_interferometer_coefficients(number_frames_avg)
        coef_file = "C:/inetpub/wwwroot/output/" + coef_filename
        zernikes = np.fromfile(coef_file, dtype=np.dtype('d'))
        correct_tip_tilt_power(zernikes, s, s_gain)
        time.sleep(1)


