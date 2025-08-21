from primary_mirror.plotting_utils import plot_single_mirror, plot_mirror_and_psf, plot_mirrors_side_by_side, plot_mirror_and_cs
from primary_mirror.LFAST_wavefront_utils import propagate_wavefront

def plot_processed_surface(surface, Z, mirror_name, config):
    plot_single_mirror(mirror_name, surface, include_rms=True)

def plot_psf_from_surface(surface, Z, mirror_name, config):
    wf_foc, throughput, x_foc, y_foc = propagate_wavefront(surface, config["OD"], config["ID"], Z, use_best_focus=True)
    plot_mirror_and_psf(mirror_name,surface,wf_foc,throughput,x_foc,y_foc,foc_scale=[-3,-5.5])

def compare_surfaces(before, after, title, Z, OD):
    delta = after - before
    plot_mirrors_side_by_side(after, before, title, subtitles=['After', 'Before'])
    plot_mirror_and_cs("Delta Surface", delta)



