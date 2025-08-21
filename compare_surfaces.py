from primary_mirror.LFAST_wavefront_utils import get_M_and_C, remove_modes

def prepare_surface(surface, Z, remove_coef):
    M, C = get_M_and_C(surface, Z)
    return remove_modes(M, C, Z, remove_coef)
