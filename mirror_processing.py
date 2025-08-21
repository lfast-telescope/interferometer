from primary_mirror.interferometer_utils import start_alignment
from primary_mirror.interferometer_utils import take_interferometer_measurements

def run_measurement(measurement_folder, s, s_gain, number_measurements=5, num_avg=20, number_alignment_iterations = 3):
    """Take new measurements and save them."""
    start_alignment(number_alignment_iterations, num_avg, s, s_gain)
    for i in range(number_measurements):
        take_interferometer_measurements(measurement_folder, num_avg=num_avg, onboard_averaging=True, savefile=str(i))
