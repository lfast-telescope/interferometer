#%%
import sys
import os
import datetime
from matplotlib import dates
import numpy as np

# Add the parent and superparent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

#%%
from config import get_mirror_params
from interferometer_utils import take_new_measurement, setup_paths
from data_loader import load_measurements, load_multiple_surfaces, load_single_surface
from surface_processing import prepare_surface
from shared.General_zernike_matrix import General_zernike_matrix
from shared.zernike_utils import get_M_and_C, remove_modes
from plotting_interface import plot_processed_surface, compare_surfaces
#%%
base_path = r"C:\Users\lfast-admin\Documents\mirrors\M23\sixtydeg_rot_belly_band_test_with_braces"

belly_band_data = {}

for subfolder in os.listdir(base_path):
    subfolder_path = os.path.join(base_path, subfolder)
    torque_value = subfolder.split('_')[1]
    if os.path.isdir(subfolder_path):
        list_of_good_tests = []
        list_of_tests = os.listdir(subfolder_path)
        for test in list_of_tests:
            valid_test = any([file.endswith('.npy') for file in os.listdir(os.path.join(subfolder_path, test))])
            if valid_test:
                list_of_good_tests.append(test)       
        highest_test_index = max([int(test) for test in list_of_good_tests])
        test_path = os.path.join(subfolder_path, str(highest_test_index))
        for file in os.listdir(test_path):
            if file.endswith(".npy"):
                surface = np.load(os.path.join(test_path, file))
                belly_band_data[torque_value] = surface

for torque, surface in belly_band_data.items():
    if torque != '0':
        diff = surface - belly_band_data['0']
        compare_surfaces(diff, belly_band_data['0'], f"Changes from {torque}in-lb torque", subtitles=['Baseline: ','Torque delta: '],plot_cs = False, plot_bounds=None)
    else:
        plot_processed_surface(surface, None, f"Torque {torque}in-lb (baseline)", None)
