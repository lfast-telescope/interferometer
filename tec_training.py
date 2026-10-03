#%%
"""
DEPRECATION NOTICE:
This legacy script managed open-loop TEC training sweeps by polling step_info.txt folders.
Superseded by mirror_control.calibration.abba_protocol and mirror_control.scripts.run_goal1_interferometer.
Retained in place for backward compatibility.
"""
import sys
import os
import time
import datetime
import numpy as np

# Add the parent and superparent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


from config import get_mirror_params
from interferometer_utils import start_alignment, take_interferometer_measurements

try:
    from shared.General_zernike_matrix import General_zernike_matrix
except ImportError:
    try:
        from mirror_control.shared.General_zernike_matrix import General_zernike_matrix
    except ImportError:
        raise ImportError('Could not import General_zernike_matrix. Ensure mirror_control repository is available.')

try:
    from LFASTfiber.libs.libNewport import smc100
    from LFASTfiber.libs import libThorlabs
except ImportError:
    print("Warning: LFASTfiber libraries not found. Cannot control hardware.")
    smc100 = None
    libThorlabs = None

# Test parameters
number_test_steps = 290
number_frames_avg = 10
align_frames_avg = 10
number_averaged_frames = 5
s_gain = 0.5

# Mirror configuration
mirror_num = "10"
config = get_mirror_params(mirror_num)
OD, ID = config["OD"], config["ID"]
clear_aperture_outer = OD 
clear_aperture_inner = ID

# Create Zernike matrix
Z = General_zernike_matrix(44, int(clear_aperture_outer * 1e6), int(clear_aperture_inner * 1e6))

# Setup paths
mirror_path = config["base_path"]
os.makedirs(mirror_path, exist_ok=True)
folder_name = datetime.datetime.now().strftime('%Y%m%d')
folder_path = os.path.join(mirror_path, folder_name) + '/'
if not os.path.exists(folder_path):
    os.mkdir(folder_path)

#%%
# Initialize hardware
if smc100 is None:
    raise RuntimeError("Cannot run TEC training without Newport SMC100 library")
s = smc100('COM3', nchannels=3)
#%%
# Initial alignment and baseline measurements
start_alignment(5, align_frames_avg, s, s_gain)

tic = time.time()
for num in np.arange(number_averaged_frames):
    take_interferometer_measurements(folder_path, num_avg=number_frames_avg, onboard_averaging=True, savefile=f'/calibration/{num+1}')

test_duration = time.time() - tic
print(f"Baseline measurements complete. Test duration: {test_duration:.2f}s")
#%%
# TEC test main loop
input('Start TEC test (press Enter when ready)')
list_of_tec_tests = os.listdir(folder_path)

# Find the most recent test directory
i = -1
current_test = list_of_tec_tests[i]
test_path = os.path.join(folder_path, current_test) + '/'
while not os.path.isdir(test_path):
    i = i - 1
    current_test = list_of_tec_tests[i]
    test_path = os.path.join(folder_path, current_test) + '/'

print(f"Using test directory: {test_path}")

# Process xx TEC test steps
for i in np.arange(266, number_test_steps):
    align_period = 60
    align_time = time.time() + align_period
    step_path = os.path.join(test_path, str(i)) + '/'
    
    # Wait for external TEC control to create step directory
    while not os.path.exists(step_path):
        print(f'Waiting for step {i}...')
        time.sleep(1)
    
    tic = time.time()
    
    # Read TEC parameters from step info file
    with open(os.path.join(step_path, 'step_info.txt'), 'r') as f:
        txt = f.read()
    txt_words = txt.split(' ')
    duration = int(txt_words[3])
    tec_num = int(txt_words[7][:-1])
    tec_cmd = float(txt_words[9])
    savefile = f'tec{tec_num}_cmd{txt_words[9].replace(".", "-")}'
    
    print(f"Step {i}: TEC{tec_num} = {tec_cmd}, duration = {duration}s")
    
    # Wait for thermal settling while maintaining alignment
    keep_running = True
    while keep_running:
        time.sleep(1)
        if time.time() - tic > duration - test_duration * 2.5:
            keep_running = False
        else:
            if time.time() > align_time:
                align_time = time.time() + align_period
                try:
                    start_alignment(1, align_frames_avg, s, s_gain)
                except RuntimeError as e:
                    # Don't let a transient/stuck 4Sight kill a multi-hour test; skip this
                    # correction cycle and retry at the next align_period instead.
                    print(f"WARNING: alignment check failed during step {i}, continuing without correction: {e}")
    
    # Take measurements at end of step
    for num in np.arange(number_averaged_frames):
        take_interferometer_measurements(step_path, num_avg=number_frames_avg, onboard_averaging=True, savefile=f'{savefile}_{num}')
    
    print(f"Step {i} complete")

print("TEC training complete!")
s.close()
