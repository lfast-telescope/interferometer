import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from .plotting_utils import plot_single_mirror, plot_mirror_and_psf, plot_mirrors_side_by_side, plot_mirror_and_cs, plot_many_mirror_cs, compute_cmap_and_contour, plot_multiple_surfaces
except ImportError:
    from plotting_utils import plot_single_mirror, plot_mirror_and_psf, plot_mirrors_side_by_side, plot_mirror_and_cs, plot_many_mirror_cs, compute_cmap_and_contour, plot_multiple_surfaces

try:
    from ..shared.wavefront_propagation import propagate_wavefront
except (ImportError, ValueError):
    # ValueError can occur with relative imports beyond top-level
    from shared.wavefront_propagation import propagate_wavefront

def plot_processed_surface(surface, Z, mirror_name, config, fig=None, ax=None):
    return plot_single_mirror(mirror_name, surface, include_rms=True, fig=fig, ax=ax)

def plot_psf_from_surface(surface, Z, mirror_name, config, fig=None, axs=None):
    wf_foc, throughput, x_foc, y_foc = propagate_wavefront(surface, config["OD"], config["ID"], Z, use_best_focus=True)
    return plot_mirror_and_psf(mirror_name,surface,wf_foc,throughput,x_foc,y_foc,foc_scale=[-3,-5.5], fig=fig, axs=axs)

def compare_surfaces(before, after, title, subtitles=['After', 'Before'],plot_cs=True, plot_bounds=None, fig=None, axs=None):
    delta = after - before
    result_sbs = plot_mirrors_side_by_side(after, before, title, subtitles=subtitles, plot_bounds=plot_bounds, fig=fig, axs=axs)
    result_cs = None
    if plot_cs:
        result_cs = plot_mirror_and_cs("Delta Surface", delta)
    return result_sbs, result_cs

def plot_mirror_cs(mirror_num, surfaces, dates, save_fig=False, fig=None, ax=None):
    title = f"Mirror {mirror_num} radially symmetric error"
    output_ref_set = [surface for surface in surfaces if surface is not None]
    return plot_many_mirror_cs(title, output_ref_set, dates, include_reference=None, Z=None, C=None, OD=None, save_fig=save_fig, fig=fig, ax=ax)

def plot_surfaces(mirror_num, surfaces, dates, enforce_symmetric_bounds=False, save_fig=False, fig=None, axs_ext=None):
    return plot_multiple_surfaces(mirror_num, surfaces, dates, enforce_symmetric_bounds, save_fig, fig=fig, axs_ext=axs_ext)