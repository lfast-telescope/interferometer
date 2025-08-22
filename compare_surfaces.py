import numpy as np
from primary_mirror.LFAST_wavefront_utils import get_M_and_C, remove_modes

def prepare_surface(surface, Z, remove_coef, config, crop_ca = True):
    M, C = get_M_and_C(surface, Z)

    OD = config["OD"]

    updated_surface = remove_modes(M, C, Z, remove_coef)

    if crop_ca:
        X, Y = np.meshgrid(np.linspace(-OD/2, OD/2, surface.shape[0]),
                            np.linspace(-OD/2, OD/2, surface.shape[0]))
        r = np.sqrt(X**2 + Y**2)
        pupil = (r > 3*25.4e-3) & (r < 15*25.4e-3)
        updated_surface[~pupil] = np.nan

    return updated_surface
