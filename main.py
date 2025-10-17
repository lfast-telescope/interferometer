#%%
import sys
import os
import datetime
import numpy as np

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#%%
from config import get_mirror_params
from mirror_processing import take_new_measurement, setup_paths
from data_loader import load_measurements, load_multiple_surfaces
from compare_surfaces import prepare_surface
from shared.General_zernike_matrix import General_zernike_matrix
from shared.zernike_utils import get_M_and_C, remove_modes
from plotting_interface import plot_processed_surface, plot_psf_from_surface, plot_mirror_cs, plot_surfaces
try:
    from LFASTfiber.libs.libNewport import smc100
except ImportError:
    smc100 = False

def main(mirror_num="10", take_new=True, save_date = -1, save_instance = -1, new_folder=None):
    if smc100 is False and take_new:
        print("Newport SMC100 library not found. Cannot take new measurements.")
        return
    config = get_mirror_params(mirror_num)
    OD, ID = config["OD"], config["ID"]
    clear_outer, clear_inner = 0.5 * OD, 0.5 * ID

    # Setup paths
    mirror_path = config["base_path"]
    os.makedirs(mirror_path, exist_ok=True)

    save_subfolder = setup_paths(mirror_path, take_new, save_date, save_instance, new_folder)


    Z = General_zernike_matrix(44, int(clear_outer * 1e6), int(clear_inner * 1e6))

    if True:
    
        if take_new:
            take_new_measurement(save_subfolder, number_alignment_iterations=3)
        if False:
            surface = load_measurements(save_subfolder, clear_outer, clear_inner, Z)
            updated_surface = surface.copy()

            coefs = [[0,1,2,4], [0,1,2,4,12,24,40], [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44]]
            coef_names = ['uncorrected', 'sph corrected', 'trefoil corrected']
            coef_dict = dict(zip([tuple(c) for c in coefs],coef_names))

            for coefs_tuple, name in coef_dict.items():
                remove_coef = list(coefs_tuple)
                updated_surface = prepare_surface(surface, Z, remove_coef, config, crop_ca = True)
                plot_psf_from_surface(updated_surface, Z, f"N{mirror_num}" +' (' + name + ')', config)
        else:
            remove_coef = [0,1,2,4]

            subdirs = [d for d in os.listdir(mirror_path) if os.path.isdir(os.path.join(mirror_path, d))]
            dates = subdirs[-3:]
            measurements = [2,0,2]  # Indices of measurements to load from each date
            surfaces = load_multiple_surfaces(mirror_path, dates, measurements, clear_outer, clear_inner, Z, ID_crop=1.25)
            cropped_surfaces = [prepare_surface(surface, Z, remove_coef, config, crop_ca = False) for surface in surfaces]
            plot_mirror_cs(mirror_num, surfaces, dates)
            plot_surfaces(mirror_num, surfaces, dates)

#%%

if __name__ == "__main__":
    main(19, take_new=True,new_folder="afternoon")

