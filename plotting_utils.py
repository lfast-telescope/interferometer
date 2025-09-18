import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from hcipy import make_pupil_grid, Field, radial_profile
from mirror_control.shared.zernike_utils import return_zernike_name, remove_modes



def plot_mirror_wf_error(avg_ref,title,contour_interval=0,cmap_range = 0):
    plot_ref = avg_ref.copy()*1000
    vals = plot_ref[~np.isnan(plot_ref)]
    rms = np.sqrt(np.sum(np.power(vals,2))/len(vals))
    
    left_bound,right_bound,contour_levels = compute_cmap_and_contour(vals,cmap_range,contour_interval)
     
    plt.imshow(plot_ref,vmin=left_bound,vmax=right_bound)
    plt.colorbar()

    plt.contour(plot_ref,contour_levels,colors='w',linewidths=0.5)

    plt.xticks([])
    plt.yticks([])
    plt.title(title + ' has ' + str(round(rms)) + 'nm wavefront error',size=12,x=0.6,y=1.05)
    plt.xlabel('nm',x=1.15)
    plt.ylabel(str(int(np.mean(np.diff(contour_levels)))) + 'nm contours')
    
def plot_mirror_and_psf(title,output_ref,output_foc,throughput,x,y, bounds = None, foc_scale = None):
    output_foc = np.log10(output_foc)
    fig,axs = plt.subplots(1,2,width_ratios=[1,1],constrained_layout=True)
    plot_ref = output_ref.copy()*1000
    vals = plot_ref[~np.isnan(plot_ref)]
    rms = np.sqrt(np.sum(np.power(vals,2))/len(vals))
    
    if bounds:
        left_bound = bounds[0]
        right_bound = bounds[1]
        contour_levels = bounds[2]
    else:
        left_bound,right_bound,contour_levels = compute_cmap_and_contour(vals)

    contour_interval = int(np.mean(np.diff(contour_levels)))
    pcm = axs[0].imshow(plot_ref,vmin=left_bound,vmax=right_bound,cmap='viridis')
    cbar = fig.colorbar(pcm,ax = axs[0],shrink=0.5,location='left')
    axs[0].set_xticks([])
    axs[0].set_yticks([])
    axs[0].set_xlabel(str(contour_interval) + 'nm contours')
    axs[0].contour(plot_ref,contour_levels,colors='w',linewidths=0.5)
    cbar.set_label('    nm',y=-0.1,rotation='horizontal',va='bottom',ha='left')
    
    if foc_scale:
        axs[1].pcolormesh(x,y,output_foc,cmap='inferno', vmax = foc_scale[0],vmin=foc_scale[1])
    else:
        axs[1].pcolormesh(x,y,output_foc,cmap='inferno')
    axs[1].set_aspect('equal')
    axs[1].yaxis.tick_right()
    axs[1].set_ylabel('arcsec')
    axs[1].yaxis.set_label_position("right")
    
    center_coord = [0,0]
    radius = 1.315389
    patch = mpatches.Circle(center_coord, color = 'c', radius=1.315,fill=False,linewidth = 1)
    axs[1].add_artist(patch)
    
    fig.suptitle(title + ' has ' + str(int(rms)) + 'nm rms wavefront error and ' + str(int(throughput*100)) + '% efficiency',y=0.85, size='medium')
    plt.show()

def plot_single_mirror(title,output_ref,include_rms=False, save_path = None):
    fig,axs = plt.subplots()
    plot_ref = output_ref.copy()*1000
    vals = plot_ref[~np.isnan(plot_ref)]
    rms = np.sqrt(np.sum(np.power(vals,2))/len(vals))
    
    left_bound,right_bound,contour_levels = compute_cmap_and_contour(vals)
    
    contour_interval = int(np.mean(np.diff(contour_levels)))
    pcm = axs.imshow(plot_ref,vmin=left_bound,vmax=right_bound)
    cbar = fig.colorbar(pcm,ax = axs,shrink=0.8)
    axs.set_xticks([])
    axs.set_yticks([])
    axs.set_xlabel(str(contour_interval) + 'nm contours')
    axs.contour(plot_ref,contour_levels,colors='w',linewidths=0.5)
    cbar.set_label('nm',y=-0.1,labelpad=-30,rotation='horizontal',va='bottom',ha='left')
    
    title_x = 0.55
    title_y = 0.95
    if include_rms:
        fig.suptitle(title + ' has ' + str(int(rms)) + 'nm rms error',x=title_x,y=title_y)
    else:
        fig.suptitle(title,x=title_x,y=title_y)

    if not save_path is None:
        fig.savefig(save_path)
    plt.show()

def plot_mirror_and_cs(title,output_ref,include_reference = None,Z=None,C=None,OD=None):
    fig,axs = plt.subplots(1,2,width_ratios=[1,1],constrained_layout=True)
    plot_ref = output_ref.copy()*1000
    vals = plot_ref[~np.isnan(plot_ref)]
    rms = np.sqrt(np.sum(np.power(vals,2))/len(vals))

    if OD is None:
        grid = make_pupil_grid(plot_ref.shape,diameter=0.76)
    else:
        grid = make_pupil_grid(plot_ref.shape, diameter=OD)
    vals_field = Field(plot_ref.ravel(),grid)
    cs = radial_profile(vals_field,0.005)

    if True:
        print('Pk-pk error for ' + title + ' is ' + str(round(np.nanmax(cs[1])-np.nanmin(cs[1]),1)))            
    
    axs[0].plot(cs[0],cs[1],label = 'Surface')
    if OD is None:
        axs[0].set_xlim(0,0.4)
    axs[0].set_xlabel('Radial distance (m)')
    axs[0].set_ylabel('Wavefront error (nm)')
    axs[0].set_box_aspect(1)
    axs[0].set_title('Radial average')      
    
    if include_reference is not None:
        try:
            for coef in include_reference:
                name = return_zernike_name(coef)
                term = (Z[1].transpose(2,0,1)[coef])*C[2][coef]*1000
                vals_term = Field(term.ravel(),grid)
                cs = radial_profile(vals_term,0.005)
                axs[0].plot(cs[0],cs[1],'--',label=name)
        except:
            if coef < len(C[2]):
                term = (Z[1].transpose(2,0,1)[coef])*C[2][coef+1]*1000
                vals_term = Field(term.ravel(),grid)
                cs = radial_profile(vals_term,0.005)
                axs[0].plot(cs[0],cs[1],'--',label=name)
                
        axs[0].legend(fontsize='xx-small')
    left_bound,right_bound,contour_levels = compute_cmap_and_contour(vals)
    
    contour_interval = int(np.mean(np.diff(contour_levels)))
    pcm = axs[1].imshow(plot_ref,vmin=left_bound,vmax=right_bound)
    cbar = fig.colorbar(pcm,ax = axs[1],shrink=0.57)
    axs[1].set_xticks([])
    axs[1].set_yticks([])
    axs[1].set_xlabel(str(contour_interval) + 'nm contours')
    axs[1].contour(plot_ref,contour_levels,colors='w',linewidths=0.5)
    axs[1].set_title('Surface error')
    cbar.set_label('nm',y=-0.1,labelpad=-30,rotation='horizontal',va='bottom',ha='left')    
    
    title_x = 0.55
    title_y = 0.9
    fig.suptitle(title,x=title_x,y=title_y)
    plt.show()

def plot_many_mirror_cs(title,output_ref_set,name_set,include_reference = None,Z=None,C=None, OD=None):
    fig,axs = plt.subplots(1,1,width_ratios=[1],constrained_layout=True)
    
    for num,output_ref in enumerate(output_ref_set):
        plot_ref = output_ref.copy()*1000
        vals = plot_ref[~np.isnan(plot_ref)]
        rms = np.sqrt(np.sum(np.power(vals,2))/len(vals))

        if OD is None:
            grid = make_pupil_grid(plot_ref.shape,diameter=0.76)
        else:
            grid = make_pupil_grid(plot_ref.shape, diameter=OD)
        vals_field = Field(plot_ref.ravel(),grid)
        cs = radial_profile(vals_field,0.005)
    
        if True:
            print('Pk-pk error for ' + title + ' is ' + str(round(np.nanmax(cs[1])-np.nanmin(cs[1]),1)))            
        
        axs.plot(cs[0],cs[1],label = name_set[num])

    if OD is None:
        axs.set_xlim(0,0.4)
    axs.set_xlabel('Radial distance (m)')
    axs.set_ylabel('Wavefront error (nm)')
    axs.set_box_aspect(1)
    axs.set_title(title)      
        
    if include_reference is not None:
        try:
            for coef in include_reference:
                name = return_zernike_name(coef)
                term = (Z[1].transpose(2,0,1)[coef])*C[2][coef]*1000
                vals_term = Field(term.ravel(),grid)
                cs = radial_profile(vals_term,0.005)
                axs.plot(cs[0],cs[1],'--',return_zernike_name(coef))
        except:
            term = (Z[1].transpose(2,0,1)[include_reference])*C[2][include_reference]*1000
            vals_term = Field(term.ravel(),grid)
            cs = radial_profile(vals_term,0.005)
            axs.plot(cs[0],cs[1],'--',return_zernike_name(include_reference))
                    
    
    axs.legend(fontsize='small')
    title_x = 0.55
    title_y = 0.9
    plt.show()

def plot_mirrors_side_by_side(avg_ref_left, avg_ref_right,title,include_difference_plot = False, include_radial_average = False, subtitles = None, plot_bounds = None):
    #make mirror data for new profile
    plot_ref_new = avg_ref_left.copy()*1000
    vals_new = plot_ref_new[~np.isnan(plot_ref_new)]
    rms_new = np.sqrt(np.sum(np.power(vals_new,2))/len(vals_new))
    
    left_bound_new,right_bound_new,contour_levels_new = compute_cmap_and_contour(vals_new)

    #make mirror data for old profile
    plot_ref_old = avg_ref_right.copy()*1000
    vals_old = plot_ref_old[~np.isnan(plot_ref_old)]
    rms_old = np.sqrt(np.sum(np.power(vals_old,2))/len(vals_old))
    
    left_bound_old,right_bound_old,contour_levels_old = compute_cmap_and_contour(vals_old)

    #make difference map and determine shared scale / contour interval    
    plot_ref_diff = plot_ref_new - plot_ref_old
    vals_diff = plot_ref_diff[~np.isnan(plot_ref_diff)]
    rms_diff = np.sqrt(np.sum(np.power(vals_diff,2))/len(vals_diff))

    if plot_bounds:
        left_bound = -plot_bounds
        right_bound = plot_bounds
    else:
        left_bound = np.min([left_bound_new,left_bound_old])
        right_bound = np.max([right_bound_new,right_bound_old])

    if np.mean(np.diff(contour_levels_new)) > np.mean(np.diff(contour_levels_old)):
        contour_levels = contour_levels_new
    else:
        contour_levels = contour_levels_old
    
    #plot figures
    
    if include_difference_plot or include_radial_average:
        fig,axs = plt.subplots(1,3,width_ratios=[1,1,1],constrained_layout=True)
    else:
        fig,axs = plt.subplots(1,2,width_ratios=[1,1],constrained_layout=True)

    pcm_old = axs[0].imshow(plot_ref_new,vmin=left_bound,vmax=right_bound,cmap='viridis')
    axs[0].contour(plot_ref_new,contour_levels,colors='w',linewidths=0.5)
    axs[0].set_ylabel(str(int(np.mean(np.diff(contour_levels)))) + 'nm contours')
    
    pcm_new = axs[1].imshow(plot_ref_old,vmin=left_bound,vmax=right_bound,cmap='viridis')
    axs[1].contour(plot_ref_old,contour_levels,colors='w',linewidths=0.5)
    
    if subtitles:
        axs[0].set_title(subtitles[0] + str(int(rms_new)) + 'nm rms')
        axs[1].set_title(subtitles[1] + str(int(rms_old)) + 'nm rms')
    else:
        axs[0].set_title(str(int(rms_new)) + 'nm rms')
        axs[1].set_title(str(int(rms_old)) + 'nm rms')
    
    if include_difference_plot:
        pcm_diff = axs[2].imshow(plot_ref_diff,vmin=left_bound,vmax=right_bound)
        axs[2].contour(plot_ref_diff,contour_levels,colors='w',linewidths=0.5)
        axs[2].set_title(str(int(rms_diff)) + 'nm rms')
    
        plot_range = 2
        title_y = 0.85
    elif include_radial_average:
        grid = make_pupil_grid(plot_ref_new.shape,diameter=0.76)
        leg = ['New surface','Old surface','Difference']
        for surf in [plot_ref_new,plot_ref_old,plot_ref_diff]:
            vals_field = Field(surf.ravel(),grid)
            cs = radial_profile(vals_field,0.005)
            axs[2].plot(cs[0],cs[1])
        axs[2].set_xlim(0,0.4)
        axs[2].set_xlabel('Radial distance (m)')
        axs[2].set_ylabel('Surface error (nm)')
        axs[2].set_box_aspect(1)
        axs[2].set_title('Radial average')     
        axs[2].legend(leg,loc='lower left',fontsize='small')
        plot_range = -1
        title_y = 0.85
        
    else:
        plot_range = 1
        title_y = 0.95

    cbar = fig.colorbar(pcm_new,ax=axs[plot_range],shrink = 0.6)
    cbar.set_label('nm',y=-0.15,rotation='horizontal',va='bottom',ha='right',labelpad = -20)

    for i in np.arange(0,plot_range):
        axs[i].set_xticks([])
        axs[i].set_yticks([])
        axs[i].set_aspect('equal')   
        
    plt.xticks([])
    plt.yticks([])
    
    fig.suptitle(title ,size=12,y=title_y)
    plt.show()

def plot_multiple_surfaces(mirror_num, surfaces, dates):
    surfaces = np.multiply(surfaces, 1000)
    vmax = np.nanmax([np.nanmax(surface) for surface in surfaces])
    vmin = np.nanmin([np.nanmin(surface) for surface in surfaces])
    fig, ax = plt.subplots(1, len(surfaces), figsize=(5*len(surfaces), 5))
    im_list = []
    for i, surface in enumerate(surfaces):
        vals = surface[~np.isnan(surface)]
        left_bound,right_bound,contour_levels = compute_cmap_and_contour(vals, cmap_range=[vmin, vmax])
        rms = np.sqrt(np.sum(np.power(vals,2))/len(vals))
        im = ax[i].imshow(surface, cmap='viridis', vmin=vmin, vmax=vmax)
        im_list.append(im)
        ax[i].contour(surface, contour_levels, colors='w', linewidths=0.5)
        ax[i].set_title(f"{dates[i]}" + ' has ' + f"{rms:.0f}nm rms")
        ax[i].axis('off')

    plt.tight_layout(rect=[0, 0.05, 0.95, 0.90])  # leave space on the right for colorbar

    avg_contour = np.mean(np.diff(contour_levels))
    # Add colorbar to the right of all subplots
    cbar = fig.colorbar(im_list[0], ax=ax, orientation='vertical', fraction=0.025, pad=0.04)
    cbar.set_label('Wavefront error (nm)')
    fig.suptitle(f"M{mirror_num} wavefront error during alternate polishing stroke", fontsize=16)
    fig.supxlabel(f"{avg_contour:.0f}nm contours")
    plt.show()

def plot_zernike_modes_as_bar_chart(C,C2 = None, num_modes=15,coef_list = [3,5,12,24,40,60,84], labels = ['After','Before']):
    modes = C[2][:num_modes]*1000
    if num_modes > len(C[2]):
        num_modes = len(C[2])
    x = np.arange(num_modes)
    label = ['']*len(x)
    for coef in coef_list:
        if coef < len(modes):
            label[coef] = return_zernike_name(coef)
    fig, ax = plt.subplots()
    
    ax.set(ylabel='Normalized amplitude (nm)', title = 'Amplitude of Zernike coefficients',ylim = (np.min(modes)*1.2,np.max(modes)*1.2),xlabel='Zernike index (OSA/ANSI)')

    if C2 is not None:
        bar_container = ax.bar(x,modes,width = 0.4,label=labels[0])
        modes2 = C2[2][:num_modes]*1000
        bar_container2 = ax.bar(x+0.5,modes2,width = 0.4,label=labels[1])
        ax.legend(loc='upper right')
        mini = np.min([np.min(modes),np.min(modes2)])
        maxi = np.max([np.max(modes),np.max(modes2)])
        ax.set(ylim = (mini*1.2,maxi*1.2))
        ax.bar_label(bar_container2, labels=label,size='small')

    else:        
        bar_container = ax.bar(x,modes)
        ax.bar_label(bar_container, labels=label,size='small')

def compute_cmap_and_contour(vals,cmap_range=0,contour_interval=0):
    #Define the bounds for a colormap that excludes extreme min/max values
    sorted_vals = np.sort(vals)
    
    if cmap_range:
        left_bound = cmap_range[0]
        right_bound = cmap_range[1]
    else:    
        left_bound = sorted_vals[int(len(vals)*0.01)]
        right_bound = sorted_vals[int(len(vals)*0.99)]
    
    if True: #set bounds to be symmetric
        if abs(left_bound) > abs(right_bound):
            right_bound = -left_bound
        else:
            left_bound = -right_bound
    
    if contour_interval:
        contour_levels = np.arange(left_bound,right_bound,contour_interval)
    else:
        number_contours = 10
        contour_interval = round(int((right_bound-left_bound)/number_contours)/20)*20
        if contour_interval < 40:
            contour_interval = 40
        contour_levels = np.arange(left_bound,right_bound,contour_interval)
    return left_bound,right_bound,contour_levels

def create_4d_plot(M,C,Z,OD):
    coef_normal = [0,1,2,4]
    coef_correctable = [0,1,2,3,4,5,6,9,10,14,15,20]

    surface_normal = remove_modes(M,C,Z,coef_normal)

    fig = plt.figure()
    gs0 = gridspec.GridSpec(3,2)
    gs00 = gridspec.GridSpecFromSubplotSpec(5,5,subplot_spec = gs0[0])
    ax1 = fig.add_subplot(gs00[:-1,:-1])
    ax2 = fig.add_subplot(gs00[-1,:-1])
    ax3 = fig.add_subplot(gs00[:-1,-1])
    x_cs,y_cs = create_xy_cs(surface_normal)
    ax1.imshow(surface_normal)
    ax1.set_xticks([])
    ax1.set_yticks([])
    ax2.plot(np.linspace(-OD/2,OD/2,x_cs.size),x_cs)
    ax3.plot(y_cs,np.linspace(-OD/2,OD/2,y_cs.size))
    plt.show()

def create_xy_cs(surface):
    x_mid = int(surface.shape[0]/2)
    y_mid = int(surface.shape[1]/2)
    x_cs = surface[x_mid,:]
    y_cs = surface[:,y_mid]
    return x_cs, y_cs