#%%
import sys
import os
import datetime
from matplotlib import dates
import numpy as np

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_mirror_params
from mirror_processing import take_new_measurement, setup_paths
from data_loader import load_measurements, load_multiple_surfaces
from compare_surfaces import prepare_surface
from primary_mirror.General_zernike_matrix import General_zernike_matrix
from primary_mirror.LFAST_wavefront_utils import get_M_and_C, remove_modes
from LFASTfiber.libs.libNewport import smc100
from plotting_interface import plot_processed_surface, plot_psf_from_surface, plot_mirror_cs, plot_surfaces

#mirror_num="19"; take_new=False; save_date = -1; save_instance = -1; new_folder=None

def main(mirror_num="10", take_new=True, save_date = -1, save_instance = -1, new_folder=None):
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
            take_new_measurement(save_subfolder, number_alignment_iterations=7)
        if True:
            surface = load_measurements(save_subfolder, clear_outer, clear_inner, Z)
            updated_surface = surface.copy()

            coefs = [[0,1,2,4], [0,1,2,4,12,24,40], [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44]]
            coef_names = ['uncorrected', 'sph corrected', 'trefoil corrected']
            coef_dict = dict(zip([tuple(c) for c in coefs],coef_names))

            for coefs_tuple, name in coef_dict.items():
                remove_coef = list(coefs_tuple)
                updated_surface = prepare_surface(surface, Z, remove_coef, config, crop_ca = True)
                plot_psf_from_surface(updated_surface, Z, f"N{mirror_num}" +' (' + name + ')', config)
                plot_mirror_cs(mirror_num, [updated_surface], [datetime.datetime.now().strftime('%Y%m%d')])

        else:
            remove_coef = [0,1,2,4]

            subdirs = [d for d in os.listdir(mirror_path) if os.path.isdir(os.path.join(mirror_path, d))]
            dates = subdirs[-1:]
            measurements = [0]  # Indices of measurements to load from each date
            surfaces = load_multiple_surfaces(mirror_path, dates, measurements, clear_outer, clear_inner, Z, ID_crop=1.25)
            
            cropped_surfaces = [prepare_surface(surface, Z, remove_coef, config, crop_ca = False) for surface in surfaces]
            plot_mirror_cs(mirror_num, cropped_surfaces, dates)
            plot_surfaces(mirror_num, cropped_surfaces, dates, enforce_symmetric_bounds=True)


            plot_psf_from_surface(cropped_surfaces[-1], Z, f"N{mirror_num}", config)

            delta_holder = []
            date_holder = []
            for i in np.arange(1, len(cropped_surfaces)):
                delta = cropped_surfaces[-i] - cropped_surfaces[-i-1]
                date_str = f"({dates[-i]} - {dates[-i-1]})"
                delta_holder.append(delta)
                date_holder.append(date_str)

            if len(delta_holder) > 1:
                plot_surfaces(f"N{mirror_num} Delta Surfaces", delta_holder, date_holder, enforce_symmetric_bounds=True)
            else:
                plot_processed_surface(delta_holder[0], Z, f"N{mirror_num} Delta Surface", config)

        

#%%

if __name__ == "__main__":
    main(20, take_new=False,new_folder=None)