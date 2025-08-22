#%%
import sys
import os
import datetime
import numpy as np

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_mirror_params
from mirror_processing import take_new_measurement
from data_loader import load_measurements
from compare_surfaces import prepare_surface
from primary_mirror.General_zernike_matrix import General_zernike_matrix
from primary_mirror.LFAST_wavefront_utils import get_M_and_C, remove_modes
from LFASTfiber.libs.libNewport import smc100
from plotting_interface import plot_processed_surface, plot_psf_from_surface
from mi

def main(mirror_num="10", take_new=True, save_date = -1, save_instance = -1):
    config = get_mirror_params(mirror_num)
    OD, ID = config["OD"], config["ID"]
    clear_outer, clear_inner = 0.5 * OD, 0.5 * ID

    # Setup paths
    mirror_path = config["base_path"]
    os.makedirs(mirror_path, exist_ok=True)

    save_subfolder = setup_paths(mirror_path, take_new, save_date, save_instance)


    Z = General_zernike_matrix(44, int(clear_outer * 1e6), int(clear_inner * 1e6))

    if take_new:
        take_new_measurement(save_subfolder, number_alignment_iterations=3)

    surface = load_measurements(save_subfolder, clear_outer, clear_inner, Z)
    updated_surface = surface.copy()

    coefs = [[0,1,2,4], [0,1,2,4,12,24,40], [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44]]
    coef_names = ['uncorrected', 'sph corrected', 'trefoil corrected']
    coef_dict = dict(zip([tuple(c) for c in coefs],coef_names))

    for coefs_tuple, name in coef_dict.items():
        remove_coef = list(coefs_tuple)
        updated_surface = prepare_surface(surface, Z, remove_coef, config, crop_ca = True)
        plot_psf_from_surface(updated_surface, Z, f"N{mirror_num}" +' (' + name + ')', config)
    

#%%

if __name__ == "__main__":
    main()


