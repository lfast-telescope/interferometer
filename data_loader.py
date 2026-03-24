import os
import numpy as np
import sys

try:
    # Try relative import (when run as part of package)
    from .surface_processing import measure_h5_circle, format_data_from_avg_circle
except ImportError:
    # Fall back to absolute import (when run directly)
    from surface_processing import measure_h5_circle, format_data_from_avg_circle

def load_measurements(folder, clear_outer, clear_inner, Z, ID_crop=1.25):
    data_holder, coord_holder, ID_holder = [], [], []

    for file in os.listdir(folder):
        if file.endswith(".h5"):
            data, circle_coord, ID = measure_h5_circle(os.path.join(folder, file), use_optimizer=True)
            data_holder.append(data)
            coord_holder.append(circle_coord)
            ID_holder.append(ID)

    avg_circle = np.mean(coord_holder, axis=0)
    wf_maps = [
        format_data_from_avg_circle(data, avg_circle, clear_outer, clear_inner*ID_crop, Z, normal_tip_tilt_power=True)[1]
        for data in data_holder
    ]
    if False:
        surface = np.flip(np.mean(wf_maps, 0), 1)
        #DELTADELTA I CHANGED THE FLIP AXIS FROM 0->1 AFTER LOOKING AT TEC TRAINING DATA
    else:
        surface = np.mean(wf_maps, 0)
    
    if False:
        import matplotlib.pyplot as plt
        plt.imshow(surface)
        plt.show()

    np.save(os.path.join(folder, 'averaged_surface.npy'), surface)
    return surface

def load_multiple_surfaces(shared_path, dates, measurements, clear_outer, clear_inner, Z, ID_crop=1.25):
    surfaces = []

    if isinstance(dates, str):
        dates = [dates]
        measurements = [measurements]

    for num, date in enumerate(dates):
        folder = os.path.join(shared_path, date)
        subfolder = measurements[num] if isinstance(measurements[num], str) else str(measurements[num])
        subfolder_path = os.path.join(folder, subfolder)
        if os.path.isdir(subfolder_path):
            if os.path.exists(os.path.join(subfolder_path, 'averaged_surface.npy')):
                surface = np.load(os.path.join(subfolder_path, 'averaged_surface.npy'))
            else:
                surface = load_measurements(subfolder_path, clear_outer, clear_inner, Z, ID_crop)
            surfaces.append(surface)
    return surfaces
