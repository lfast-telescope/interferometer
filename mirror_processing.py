import os
import datetime

from primary_mirror.interferometer_utils import start_alignment
from primary_mirror.interferometer_utils import take_interferometer_measurements
from LFASTfiber.libs.libNewport import smc100


def run_measurement(measurement_folder, s, s_gain, number_measurements=5, num_avg=20, number_alignment_iterations = 3):
    """Take new measurements and save them."""
    start_alignment(number_alignment_iterations, num_avg, s, s_gain)
    for i in range(number_measurements):
        take_interferometer_measurements(measurement_folder, num_avg=num_avg, onboard_averaging=True, savefile=str(i))

def take_new_measurement(save_subfolder, number_alignment_iterations=3):
    """Take a new measurement and save it to the folder."""
    s = smc100('COM3', nchannels=3)
    run_measurement(save_subfolder, s, s_gain=0.5, number_alignment_iterations=number_alignment_iterations)
    s.close()

def setup_paths(mirror_path, take_new, save_date, save_instance):
    """Handle logic for save/load folder paths."""
    if take_new or len(os.listdir(mirror_path)) == 0:
        folder = datetime.datetime.now().strftime('%Y%m%d')
        save_path = os.path.join(mirror_path, folder) + '/'
        os.makedirs(save_path, exist_ok=True)

        measurement_number = len(os.listdir(save_path))
        save_subfolder = save_path + str(measurement_number) + '/'
        os.makedirs(save_subfolder, exist_ok=True)

    else:
        folder_list = sorted([f for f in os.listdir(mirror_path) if f.isnumeric()])
        folder = folder_list[save_date] if isinstance(save_date, int) else save_date
        save_path = os.path.join(mirror_path, folder)

        subfolder_list = sorted([f for f in os.listdir(save_path) if f.isnumeric()])
        instance = subfolder_list[save_instance] if isinstance(save_instance, int) else save_instance
        save_subfolder = os.path.join(save_path, instance)

    return save_subfolder
