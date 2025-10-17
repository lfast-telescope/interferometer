from .plotting_utils import plot_single_mirror, plot_mirror_and_psf, plot_mirrors_side_by_side, plot_mirror_and_cs, plot_many_mirror_cs, compute_cmap_and_contour, plot_multiple_surfaces
from mirror_control.shared.wavefront_propagation import propagate_wavefront

def plot_processed_surface(surface, Z, mirror_name, config):
    plot_single_mirror(mirror_name, surface, include_rms=True)

def plot_psf_from_surface(surface, Z, mirror_name, config):
    wf_foc, throughput, x_foc, y_foc = propagate_wavefront(surface, config["OD"], config["ID"], Z, use_best_focus=True)
    plot_mirror_and_psf(mirror_name,surface,wf_foc,throughput,x_foc,y_foc,foc_scale=[-3,-5.5])

def compare_surfaces(before, after, title, Z, OD):
    delta = after - before
    plot_mirrors_side_by_side(after, before, title, subtitles=['After', 'Before'])
    plot_mirror_and_cs("Delta Surface", delta)

def plot_mirror_cs(mirror_num, surfaces, dates, save_fig=False):
    title = f"Mirror {mirror_num} radially symmetric error"
    output_ref_set = [surface for surface in surfaces if surface is not None]
    plot_many_mirror_cs(title, output_ref_set, dates, include_reference=None, Z=None, C=None, OD=None, save_fig=save_fig)

def plot_surfaces(mirror_num, surfaces, dates, enforce_symmetric_bounds=False, save_fig=False):
    plot_multiple_surfaces(mirror_num, surfaces, dates, enforce_symmetric_bounds, save_fig)