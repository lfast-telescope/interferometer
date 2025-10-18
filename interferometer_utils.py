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
from .surface_processing import import_4D_map_auto, import_cropped_4D_map, measure_h5_circle, format_data_from_avg_circle, process_wavefront_error
from ..shared.wavefront_propagation import propagate_wavefront

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

def save_image_set(folder_path,Z,remove_coef = [],mirror_type='uncoated'):
    #Store a folder containing h5 files as a tuple
    output = []
    for file in os.listdir(folder_path):
        if file.endswith(".h5"):
            try:
                if mirror_type == 'uncoated':
                    if len(remove_coef) == 0:
                        surf = import_4D_map_auto(folder_path + file,Z)
                    else:
                        surf = import_4D_map_auto(folder_path + file,Z,normal_tip_tilt_power=False,remove_coef = remove_coef)
                else:
                    surf = import_cropped_4D_map(folder_path + file,Z,normal_tip_tilt_power=False,remove_coef = remove_coef)
                output.append(surf[1])

                if False:
                    plt.imshow(surf[1])
                    plt.colorbar()
                    plt.title(file)
                    plt.show()
            except OSError as e:
                print('Could not import file ' + file)
    return output

def load_interferometer_maps(array_of_paths, Z, clear_aperture_outer, clear_aperture_inner, remove_coef=[0, 1, 2, 4], new_load_method=False, pupil_size=None):
    array_of_outputs = []
    for path in array_of_paths:
        if new_load_method:
            data_holder = []
            coord_holder = []
            wf_maps = []
            wf_maps = []
            for file in os.listdir(path):
                if file.endswith(".h5"):
                    data, circle_coord = measure_h5_circle(path + file)
                    data_holder.append(data)
                    coord_holder.append(circle_coord)

            for data in data_holder:
                if remove_coef == [0, 1, 2, 4]:
                    wf_maps.append(format_data_from_avg_circle(data, circle_coord, Z, normal_tip_tilt_power=True)[1])
                else:
                    wf_maps.append(format_data_from_avg_circle(data, circle_coord, Z, normal_tip_tilt_power=False,
                                                               remove_coef=remove_coef)[1])
            output_ref = np.flip(np.mean(wf_maps, 0), 0)

        else:
            output_ref = process_wavefront_error(path, Z, remove_coef, clear_aperture_outer, clear_aperture_inner,
                                                 compute_focal=False)

        array_of_outputs.append(output_ref)
    return array_of_outputs

def process_wavefront_error(path,Z,remove_coef,clear_aperture_outer,clear_aperture_inner,compute_focal = True,mirror_type='uncoated'): #%% Let's do some heckin' wavefront analysis!
    #Load a set of mirror height maps in a folder and average them
    references = save_image_set(path,Z,remove_coef,mirror_type)
    avg_ref = np.flip(np.mean(references,0),0)
    output_ref = avg_ref.copy()
     
    if compute_focal:
        output_foc,throughput,x_foc,y_foc = propagate_wavefront(avg_ref,clear_aperture_outer,clear_aperture_inner,Z,use_best_focus=True)     
        return output_ref, output_foc,throughput,x_foc,y_foc
    else:
        return output_ref

def return_neighborhood(surface, x_linspace, x_loc, y_loc, neighborhood_size):
    #For an input coordinate on the mirror [x_loc,y_loc], return the average pixel value less than neighborhood_size away  
    [X, Y] = np.meshgrid(x_linspace, x_linspace)
    dist = np.sqrt((X - x_loc) ** 2 + (Y - y_loc) ** 2)
    neighborhood = dist < neighborhood_size
    return np.nanmean(surface[neighborhood])  
