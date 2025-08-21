#%%
import sys
import os
import datetime
import numpy as np

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_mirror_params
from mirror_processing import run_measurement
from data_loader import load_measurements
from primary_mirror.General_zernike_matrix import General_zernike_matrix
from LFASTfiber.libs.libNewport import smc100
from plotting_interface import plot_processed_surface
def main(mirror_num="10", take_new=True):
    config = get_mirror_params(mirror_num)
    OD, ID = config["OD"], config["ID"]
    clear_outer, clear_inner = 0.5 * OD, 0.5 * ID

    # Setup paths
    mirror_path = config["base_path"]
    os.makedirs(mirror_path, exist_ok=True)

    folder = datetime.datetime.now().strftime('%Y%m%d')
    save_path = os.path.join(mirror_path, folder) + '/'
    os.makedirs(save_path, exist_ok=True)

    measurement_number = len(os.listdir(save_path)) if take_new else len(os.listdir(save_path)) - 1
    save_subfolder = os.path.join(save_path, str(measurement_number)) + '/'
    os.makedirs(save_subfolder, exist_ok=True)

    # Setup instrument & Zernike matrix
    s = smc100('COM3', nchannels=3)
    Z = General_zernike_matrix(44, int(clear_outer * 1e6), int(clear_inner * 1e6))

    if take_new:
        run_measurement(save_subfolder, s, s_gain=0.5)

    surface = load_measurements(save_subfolder, clear_outer, clear_inner, Z)
    plot_processed_surface(surface, Z, f"N{mirror_num}", config)
    plot_psf_from_surface(surface, Z, f"N{mirror_num}", config)
    s.close()

#%%

if __name__ == "__main__":
    main()


