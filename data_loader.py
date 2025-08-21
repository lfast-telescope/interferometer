import os
import numpy as np
from primary_mirror.LFAST_TEC_output import measure_h5_circle, format_data_from_avg_circle
from primary_mirror.LFAST_wavefront_utils import format_data_from_avg_circle

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
    surface = np.flip(np.mean(wf_maps, 0), 0)
    return surface
