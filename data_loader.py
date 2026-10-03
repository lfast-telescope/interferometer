import os
import numpy as np
import sys

try:
    # Try relative import (when run as part of package)
    from .surface_processing import measure_h5_circle, format_data_from_avg_circle
    from .plotting_utils import save_surface_plot
except ImportError:
    # Fall back to absolute import (when run directly)
    from surface_processing import measure_h5_circle, format_data_from_avg_circle
    from plotting_utils import save_surface_plot

def load_measurements(folder, clear_outer, clear_inner, Z, ID_crop=1.25, save_png=True):
    data_holder, coord_holder, ID_holder = [], [], []

    for file in os.listdir(folder):
        if file.endswith(".h5"):
            data, circle_coord, ID = measure_h5_circle(os.path.join(folder, file), use_optimizer=True)
            data_holder.append(data)
            coord_holder.append(circle_coord)
            ID_holder.append(ID)

    if not data_holder:
        raise ValueError(
            f"No .h5 measurement files found in '{folder}'. "
            "The measurement capture may have failed before saving any frames."
        )

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
    if save_png:
        try:
            save_surface_plot(surface, folder)
        except Exception as e:
            print(f"Warning: Failed to save averaged_surface.png: {e}")
        try:
            save_surface_plot(surface, folder, filename='average_surface.png')
        except Exception as e:
            print(f"Warning: Failed to save average_surface.png: {e}")
    return surface

def load_multiple_surfaces(shared_path, dates, measurements, clear_outer, clear_inner, Z, ID_crop=1.25, recompute=False):
    surfaces = []

    if isinstance(dates, str):
        dates = [dates]
        measurements = [measurements]

    for num, date in enumerate(dates):
        folder = os.path.join(shared_path, date)
        subfolder = measurements[num] if isinstance(measurements[num], str) else str(measurements[num])
        subfolder_path = os.path.join(folder, subfolder)
        if os.path.isdir(subfolder_path):        
            surface = load_single_surface(subfolder_path, clear_outer=clear_outer, clear_inner=clear_inner, Z=Z, ID_crop=ID_crop, recompute=recompute)
            surfaces.append(surface)
    return surfaces

def load_single_surface(subfolder_path, filename='averaged_surface.npy', clear_outer=None, clear_inner=None, Z=None, ID_crop=1.25, recompute=False, save_png=True):
    npy_path = os.path.join(subfolder_path, filename)
    if not recompute and os.path.exists(npy_path):
        surface = np.load(npy_path)
        if save_png:
            png_path = os.path.join(subfolder_path, 'averaged_surface.png')
            if not os.path.exists(png_path):
                try:
                    save_surface_plot(surface, subfolder_path)
                except Exception as e:
                    print(f"Warning: Failed to save averaged_surface.png: {e}")
            avg_png_path = os.path.join(subfolder_path, 'average_surface.png')
            if not os.path.exists(avg_png_path):
                try:
                    save_surface_plot(surface, subfolder_path, filename='average_surface.png')
                except Exception as e:
                    print(f"Warning: Failed to save average_surface.png: {e}")
    else:
        surface = load_measurements(subfolder_path, clear_outer, clear_inner, Z, ID_crop, save_png=save_png)

    return surface