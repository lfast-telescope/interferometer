import numpy as np
import sys
import os
import h5py
import cv2 as cv
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import cm
from matplotlib.widgets import EllipseSelector
from scipy import interpolate
from scipy.optimize import minimize

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.zernike_utils import get_M_and_C, remove_modes, Zernike_decomposition

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

def import_4D_map(filename,Z): #import measured surface from 4D h5 file. input is (filename, Zernike matrix)
    
    f = h5py.File(filename,'r')
    data = np.array(list(f['measurement0']['genraw']['data']))
    
    invalid = np.nanmax(data)
    data[data == invalid] = np.nan #remove invalid values
    data = data*(632.8/1000) #convert from waves to nm
    
    def select_callback(eclick, erelease): #callback function for cropping the mirror from background
        """
        Callback for line selection.

        *eclick* and *erelease* are the press and release events.
        """
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        print(f"({x1:3.4f}, {y1:3.4f}) --> ({x2:3.4f}, {y2:3.4f})")
        
        global data_crop
        
        data_crop = data[int((1-y2)*len(data[0])):int((1-y1)*len(data[0])),int((x1)*len(data[0])):int((x2)*len(data[0]))]
        
        if eclick.dblclick:
            print('off')
            crop.set_active(False)
    
    zs = data 
    zs_copy = zs.copy()
    zs_copy[np.isnan(zs_copy)] = 0
    
    xs = np.linspace(-387500,387500,len(zs[0]))
    ys = np.linspace(-387500,387500,len(zs.transpose()[0]))
     
    plt.axes().set_aspect('equal')
    
    ax = plt.subplot(111)

    cs = ax.contourf((xs + 387500)/(2*387500),(-ys + 387500)/(2*387500),zs*1000,14,cmap=cm.rainbow) #plot raw measurement on xy grid from 0 to 1

    cbar = plt.colorbar(cs)
    cbar.ax.tick_params(labelsize = 12)
    cbar.set_label('Z (nm)',fontsize = 12)
    
    crop = EllipseSelector(
        ax, select_callback,
        useblit=True,
        button=[1, 3],  # disable middle button
        interactive=True)
    
    plt.xlabel('X',fontsize = 12)
    plt.ylabel('Y',fontsize = 12)
    plt.title('Click and drag to crop disc.  Double click when done.',fontsize = 14)
    plt.xticks(fontsize = 12)
    plt.yticks(fontsize = 12)
    plt.xlim(0,1)
    plt.ylim(0,1)
    plt.show()
    
    while crop.active == True:  #pause script until cropping is finished
        plt.waitforbuttonpress(1)
    
    zs_cropped = np.flip(data_crop, axis = 0)/2 #cropped image, perform parity flip and divide by 2 for WFE to surface conversion
    zs_cropped_copy = zs_cropped.copy()
    zs_cropped_copy[np.isnan(zs_cropped_copy)] = 0
    
    xs = np.linspace(-387500,387500,len(zs_cropped[0]))
    ys = np.linspace(-387500,387500,len(zs_cropped.transpose()[0]))
    
    Z_int = interpolate.RectBivariateSpline(ys,xs,zs_cropped_copy)
    
    xi = yi = np.linspace(-381000,381000,500)
    X,Y = np.meshgrid(xi,yi)
    
    zi = Z_int(Y,X,grid = False)  #truncate to clear aperture radius
    
    test = np.sqrt(X**2 + Y**2)                         #
    inds = np.where((test > 381000) | (test < 63500))   #
    coords = list(zip(inds[0],inds[1]))                 #remove data points outside of clear aperture
    for j,m in enumerate(coords):                       #
        zi[coords[j][0]][coords[j][1]] = np.nan         #
        
    M = zi.flatten(),zi
    
    C = Zernike_decomposition(Z, M, -1) #Zernike fit
    
    Piston = (Z[1].transpose(2,0,1)[0])*C[2][0] #
    TiltY = (Z[1].transpose(2,0,1)[1])*C[2][1]  #remove piston, tip/tilt, and power
    TiltX = (Z[1].transpose(2,0,1)[2])*C[2][2]  #
    Power = (Z[1].transpose(2,0,1)[4])*C[2][4]  #
    
    Surf = M[1] - Piston - TiltX - TiltY - Power ##remove piston, tip/tilt, and power
       
    return Surf.flatten(),Surf #return 1D flattened surface and 2D surface

    
def import_4D_map_auto(filename,Z,normal_tip_tilt_power=True,remove_coef = []):

    #Mirror radius in um
    pixel_ID = 1.5*25.4*1e3  #original value: 63500 . Changed from 1000 on 8/15/2024
    pixel_OD = 15*25.4*1e3 #original value: 381000. Changed from 381000 on 8/15/2024
    
    f = h5py.File(filename,'r')
    data = np.array(list(f['measurement0']['genraw']['data']))

    invalid = np.nanmax(data)
    
    masked_at_interferometer = len(data[data==invalid]) > 50        
    
    if masked_at_interferometer:    
        data[data == invalid] = np.nan #remove invalid values
    
    data = data*(632.8/1000) #convert from waves to um
    
    scale = 255*(data - np.nanmin(data))/np.nanmax((data - np.nanmin(data)))    #
    scale[np.isnan(scale)] = 255                                                #Convert data array to color scale image of vals 1-255
    scale[scale==0] = 1                                                         #
    
    img = scale.astype('uint8') #convert data type to uint8 for Hough Gradient function
    img = cv.medianBlur(img,5)  #median blurring function to help with detection

    if masked_at_interferometer:        
        circles = cv.HoughCircles(img,cv.HOUGH_GRADIENT,1,10000,                            #Find mirror disc in data array
                                param1=20,param2=15,minRadius=100,maxRadius=800)        #Output in (x_center,y_center,radius)
    else:
        grad = np.gradient(img)[1].astype('uint8')
        img_grad = cv.medianBlur(grad,7)
        circles = cv.HoughCircles(img_grad,cv.HOUGH_GRADIENT,1,10000,param1=20,param2=15,minRadius=100,maxRadius=800)
    
    circles = np.uint16(np.around(circles))                                             #Round vals to nearest integer
    
    r = circles[0][0][2] - 5    #Trim edge to remove noisy data
    
    x1 = (circles[0][0][0] - r)/len(img)    #crop h5 data array using circle params from Hough Gradient function
    x2 = (circles[0][0][0] + r)/len(img)
    y1 = 1 - (circles[0][0][1] + r)/len(img)  #Flipped due to img/contour being mirrored across y-axis
    y2 = 1 - (circles[0][0][1] - r)/len(img)  #
    
    data_crop = data[int((1-y2)*len(data[0])):int((1-y1)*len(data[0])),int((x1)*len(data[0])):int((x2)*len(data[0]))]
    
    zs_cropped = np.flip(data_crop, axis = 0)#/2 #cropped image, perform parity flip
    zs_cropped_copy = zs_cropped.copy()
    zs_cropped_copy[np.isnan(zs_cropped_copy)] = 0

    #Don't you love random ass numbers 200 lines into a piece of code that you didn't write?
    #To my best guess, this is mirror half radius in um
    #The really annoying thing about it though is that this shouldn't be hard-coded - it changes with subtense
    #It'd be better for the user to just establish the mirror size
    #Comments from warrenbfoster, 10/18/2024. Profanity omitted.
    xs = np.linspace(-387500,387500,len(zs_cropped[0]))
    ys = np.linspace(-387500,387500,len(zs_cropped.transpose()[0]))
   
    Z_int = interpolate.RectBivariateSpline(ys,xs,zs_cropped_copy)
    
    xi = yi = np.linspace(-381000,381000,500)
    X,Y = np.meshgrid(xi,yi)
    
    zi = Z_int(Y,X,grid = False)  #truncate to clear aperture radius
    
    test = np.sqrt(X**2 + Y**2)                         #
    inds = np.where((test > pixel_OD) | (test < pixel_ID))   #
    coords = list(zip(inds[0],inds[1]))                 #remove data points outside of clear aperture
    for j,m in enumerate(coords):                       #
        zi[coords[j][0]][coords[j][1]] = np.nan         #
        if False: #plot intermediate steps to figure out wtf this step is doing
            if j % 1000 == 0:
                plt.imshow(zi)
                plt.show()
        
    M = zi.flatten(),zi
    
    C = Zernike_decomposition(Z, M, -1) #Zernike fit

    f.close()
    
    if normal_tip_tilt_power:
        Piston = (Z[1].transpose(2,0,1)[0])*C[2][0] #
        TiltY = (Z[1].transpose(2,0,1)[1])*C[2][1]  #remove piston, tip/tilt, and power
        TiltX = (Z[1].transpose(2,0,1)[2])*C[2][2]  #
        Power = (Z[1].transpose(2,0,1)[4])*C[2][4]  #
        
        Surf = M[1] - Piston - TiltX - TiltY - Power ##remove piston, tip/tilt, and power
    elif len(remove_coef)>0:
        Surf = remove_modes(M,C,Z,remove_coef)
    else:
        print('Strange things are afoot')
    return Surf.flatten(),Surf #return 1D flattened surface and 2D surface    

def import_cropped_4D_map(filename, Z, normal_tip_tilt_power=True, remove_coef=[]):
    #Revision of Nick's import_4D_map_auto, but using the assumption that the user has
    #set an analysis mask that crops out the mirror outside the clear aperture.
    #This only works for coated mirrors where this distinction is obvious.

    clear_aperture_radius = 15.2 * 25.4 * 1e3  # Mirror radius that is not covered by TEC
    pixel_OD = 14.95 * 25.4 * 1e3 # Coated mirror radius
    pixel_ID = 1.8 * 25.4 * 1e3 #Coated ID

    f = h5py.File(filename, 'r')
    data = np.array(list(f['measurement0']['genraw']['data']))

    invalid = np.nanmax(data)

    data[data == invalid] = np.nan  # remove invalid values
    data = data * (632.8 / 1000)  # convert from waves to um

    asymmetry = np.max(data.shape)-np.min(data.shape)
    index = np.argmax(data.shape)
    if index == 0:
        data = data[int(np.floor(asymmetry/2)):-int(np.floor(asymmetry/2)),:]
    else:
        data = data[:,int(np.floor(asymmetry / 2)):-int(np.ceil(asymmetry / 2))]

    scale = 255 * (data - np.nanmin(data)) / np.nanmax((data - np.nanmin(data)))  #
    scale[np.isnan(scale)] = 255  # Convert data array to color scale image of vals 1-255
    scale[scale == 0] = 1  #

    circle_holder = []
    for ksize in [61,81,101]:
        img = scale.astype('uint8')  # convert data type to uint8 for Hough Gradient function
        img = cv.medianBlur(img, ksize)  # median blurring function to help with detection
        fudge = 0
        circle = None
        while circle is None:
            circle = cv.HoughCircles(img, cv.HOUGH_GRADIENT, 1, 10000,  # Find mirror disc in data array
                                  param1=20, param2=15, minRadius=175-fudge,
                                  maxRadius=177+fudge)  # Output in (x_center,y_center,radius)
            fudge = fudge + 1
        circle_holder.append(circle[0][0])

    #Plot to see if the circle detection is working
    x = np.median(circle_holder,0)[0]
    y = np.median(circle_holder,0)[1]
    r = np.min(circle_holder,0)[2]-1  # Trim smaller edge to remove noisy data, because user has already done this

    if True:
        title = 'Coordinates ' + str(circle[0][0])
        fig, ax = plt.subplots()
        ax.imshow(data)
#        artist1 = plt.Circle((OD_circle[0], OD_circle[1]), OD_circle[2], fill=False)
        artist1 = plt.Circle((x, y), r, fill=False)
        ax.add_artist(artist1)
        fig.suptitle(title)
        ax.set_aspect('equal')
        plt.show()

    x1 = np.round(x-r)
    x2 = np.round(x+r)
    y1 = np.round(y-r)
    y2 = np.round(y+r)

    data_crop = data[int(y1):int(y2)+1, int(x1):int(x2)+1]

    zs_cropped = np.flip(data_crop, axis=0)  # /2 #cropped image, perform parity flip
    zs_cropped_copy = zs_cropped.copy()
    zs_cropped_copy[np.isnan(zs_cropped_copy)] = 0

    #Define grid that the measurement is using
    xs = np.linspace(-clear_aperture_radius, clear_aperture_radius, len(zs_cropped[0]))
    ys = np.linspace(-clear_aperture_radius, clear_aperture_radius, len(zs_cropped.transpose()[0]))

    Z_int = interpolate.RectBivariateSpline(ys, xs, zs_cropped_copy)

    #Interpolate measurement onto a 500x500 grid
    xi = yi = np.linspace(-clear_aperture_radius, clear_aperture_radius, 500)
    X, Y = np.meshgrid(xi, yi)

    zi = Z_int(Y, X, grid=False)  # truncate to clear aperture radius

    test = np.sqrt(X ** 2 + Y ** 2)  #
    inds = np.where((test > pixel_OD) | (test < pixel_ID))  #
    coords = list(zip(inds[0], inds[1]))  # remove data points outside of clear aperture
    for j, m in enumerate(coords):  #
        zi[coords[j][0]][coords[j][1]] = np.nan  #

    M = zi.flatten(), zi
    C = Zernike_decomposition(Z, M, -1)  # Zernike fit
    f.close()

    if normal_tip_tilt_power:
        Piston = (Z[1].transpose(2, 0, 1)[0]) * C[2][0]  #
        TiltY = (Z[1].transpose(2, 0, 1)[1]) * C[2][1]  # remove piston, tip/tilt, and power
        TiltX = (Z[1].transpose(2, 0, 1)[2]) * C[2][2]  #
        Power = (Z[1].transpose(2, 0, 1)[4]) * C[2][4]  #

        Surf = M[1] - Piston - TiltX - TiltY - Power  ##remove piston, tip/tilt, and power
    elif len(remove_coef) > 0:
        Surf = remove_modes(M, C, Z, remove_coef)
    else:
        print('Strange things are afoot')
    return Surf.flatten(), Surf  # return 1D flattened surface and 2D surface


def measure_h5_circle(filename, use_optimizer=False):
    #Fix the problems with different pupil definitions between measurement sets causing junk difference data during averaging
    #Only import the file and guess at the pupil coordinates
    #In another function, apply the average coordinates to every measurement

    f = h5py.File(filename, 'r')
    data = np.array(list(f['measurement0']['genraw']['data']))
    f.close()

    invalid = np.nanmax(data)

    data[data == invalid] = np.nan  # remove invalid values
    data = data * (632.8 / 1000)  # convert from waves to um

    #Crop image to a square aspect ratio
    asymmetry = np.max(data.shape)-np.min(data.shape)
    index = np.argmax(data.shape)
    if index == 0:
        data = data[int(np.floor(asymmetry/2)):-int(np.floor(asymmetry/2)),:]
    else:
        data = data[:,int(np.floor(asymmetry / 2)):-int(np.ceil(asymmetry / 2))]

    valid_coords = np.where(~np.isnan(data))
    com_x = np.mean(valid_coords[1], axis=0)
    com_y = np.mean(valid_coords[0], axis=0)
    cs_x = data[:,int(com_x)]
    cs_y = data[int(com_y),:]

    ID_xy = []
    for cs in [cs_x, cs_y]:
        cs_valid = np.where(~np.isnan(cs))[0]
        list_diff = np.diff(cs_valid)
        ID_xy.append(np.sort(list_diff)[::-1][0])

    OD_xy = [np.max(valid_coords[0])-np.min(valid_coords[0]),np.max(valid_coords[1])-np.min(valid_coords[1])]
    OD = np.mean(OD_xy)
    ID = np.mean(ID_xy)

    circle_holder = []

    if use_optimizer:
        xyr = define_pupil_using_optimization(data)
        circle_holder.append(xyr)
    else:
        scale = 255 * (data - np.nanmin(data)) / np.nanmax((data - np.nanmin(data)))  #
        scale[np.isnan(scale)] = 255  # Convert data array to color scale image of vals 1-255
        scale[scale == 0] = 1  #

        for ksize in [61,81,101]:
            img = scale.astype('uint8')  # convert data type to uint8 for Hough Gradient function
            img = cv.medianBlur(img, ksize)  # median blurring function to help with detection
            fudge = 1
            circle = None
            while circle is None:
                circle = cv.HoughCircles(img, cv.HOUGH_GRADIENT, 1, int(OD),# Find mirror disc in data array
                                      param1=20, param2=15, minRadius=int(np.floor(OD/2)-fudge),
                                      maxRadius=int(np.ceil(OD/2)+fudge))  # Output in (x_center,y_center,radius)
                fudge = fudge + 1
            if fudge < 10:
                circle_holder.append(circle[0][0])

    #Plot to see if the circle detection is working
    x = np.median(circle_holder,0)[0]
    y = np.median(circle_holder,0)[1]
    r = np.min(circle_holder,0)[2]-1  # Trim smaller edge to remove noisy data, because user has already done this
    circle_coord = [x,y,r]

    return data, circle_coord, ID

def continuous_pupil_merit_function(xyr, thresh_image, inside_pupil_weight=1, outside_pupil_weight = 1):
    negative_image = np.subtract(thresh_image.astype(float), np.max(thresh_image.astype(float)))*-1
    X,Y = np.meshgrid(np.arange(thresh_image.shape[0]),np.arange(thresh_image.shape[1]))
    proposed_pupil = np.sqrt(np.square(X-xyr[0]) + np.square(Y-xyr[1])) < xyr[2]
    spots_inside_pupil = np.sum(thresh_image[proposed_pupil]).astype(float)
    spots_outside_pupil = np.sum(thresh_image[~proposed_pupil]).astype(float)
    spaces_inside_pupil = np.sum(negative_image[proposed_pupil]).astype(float)
    spaces_outside_pupil = np.sum(negative_image[~proposed_pupil]).astype(float)

    good_pupil = spots_inside_pupil**inside_pupil_weight + spaces_outside_pupil
    bad_pupil = spots_outside_pupil**outside_pupil_weight + spaces_inside_pupil

    merit = (bad_pupil - good_pupil)/(np.sum(thresh_image) + np.sum(negative_image))

    if False and np.random.rand()<0.1:
        fig,ax = plt.subplots()
        ax.imshow(thresh_image)
        artist = mpatches.Circle(xyr[:2],xyr[-1],fill=False,color='r')
        ax.add_artist(artist)
        fig.suptitle(np.round(xyr[-1],3))
        plt.show()
    elif False:
        print(np.round(merit,3))

    return merit

def define_pupil_using_optimization(data_image):
    thresh_image = data_image.copy()
    thresh_image[~np.isnan(thresh_image)] = 1
    thresh_image[np.isnan(thresh_image)] = 0
    xyr = [int(thresh_image.shape[0]/2), int(thresh_image.shape[1]/2), int(np.max(thresh_image.shape)/4)]
    res = minimize(continuous_pupil_merit_function, xyr, args=thresh_image, method='Nelder-Mead')
    return res.x


def define_ID(data, circle_coord, ID_threshold=0.99):
    #Address inconsistent measurements near ID by cropping out the noisy region

    x = circle_coord[0]
    y = circle_coord[1]
    r = circle_coord[2]

    xi = np.arange(0, data.shape[1])
    yi = np.arange(0, data.shape[0])
    X, Y = np.meshgrid(xi, yi)
    distance_from_center = np.sqrt((X - x) ** 2 + (Y - y) ** 2)
    invalid_data = np.isnan(data)
    pix_within_aperture = distance_from_center < (r/2)
    invalid_ID = invalid_data * pix_within_aperture
    invalid_distances = distance_from_center * invalid_ID
    sorted_invalid_distances = np.sort(invalid_distances[np.nonzero(invalid_distances)].ravel())
    threshold_distance = sorted_invalid_distances[int(len(sorted_invalid_distances) * ID_threshold)]
    data_copy = data.copy()
    data_copy[distance_from_center < threshold_distance] = np.nan
    return data_copy

def format_data_from_avg_circle(data,circle_coord, clear_aperture_outer, clear_aperture_inner, Z, normal_tip_tilt_power=True, remove_coef=[]):
    #Apply averaged circle measurements from a measurement set to the data
    #This doesn't fix inconsistent user crops, but should clean up the difference data.

    #clear_aperture_inner = 0
    set_nans_to_zero = False

    clear_aperture_radius = clear_aperture_outer  # Mirror radius that is not covered by TEC
    pixel_OD = clear_aperture_outer # Coated mirror radius
    pixel_ID = clear_aperture_inner #Coated ID

    if clear_aperture_inner > 1e-6:
        data = define_ID(data, circle_coord)

    x = circle_coord[0]
    y = circle_coord[1]
    r = circle_coord[2]

    x1 = np.floor(x-r)
    x2 = np.ceil(x+r)
    y1 = np.floor(y-r)
    y2 = np.ceil(y+r)

    data_crop = data[int(y1):int(y2), int(x1):int(x2)]

    if data_crop.shape[0]<data_crop.shape[1]:
        data_crop = data_crop[:,1:]
    elif data_crop.shape[0]>data_crop.shape[1]:
        data_crop = data_crop[1:,:]

    if False:
        plt.imshow(data_crop)
        plt.show()

    zs_cropped = np.flip(data_crop, axis=0)  # /2 #cropped image, perform parity flip

    #Define grid that the measurement is using
    xs = np.linspace(-clear_aperture_radius, clear_aperture_radius, len(zs_cropped[0]))
    ys = np.linspace(-clear_aperture_radius, clear_aperture_radius, len(zs_cropped.transpose()[0]))

    #Interpolate measurement onto a 500x500 grid
    xi = yi = np.linspace(-clear_aperture_radius, clear_aperture_radius, 500)
    X, Y = np.meshgrid(xi, yi)


    zs_cropped_copy = zs_cropped.copy()

    if set_nans_to_zero:
        # Old method for interpolated set. Using a method that doesn't tolerate nans, so sets all nan values to 0. This creates fake splines and bad fits around the ID/OD.
        zs_cropped_copy[np.isnan(zs_cropped_copy)] = 0
    else:
        # New system: use fancy new interpolation that only interpolates over a defined set of nonnan pixels. Use this as interpolation set.
        coord = np.where(~np.isnan(data_crop))
        tck, fp, ier, msg = interpolate.bisplrep(xs[coord[1]], ys[coord[0]], data_crop[~np.isnan(data_crop)],
                                                 full_output=1)
        zs_filled = interpolate.bisplev(xs, ys, tck)
        zs_flip = np.flip(zs_filled, axis=0) #This interpolation is creating a parity change, apparently, so fix it
        zs_cropped_copy[np.isnan(zs_cropped_copy)] = zs_flip[np.isnan(zs_cropped_copy)]

    Z_int = interpolate.RectBivariateSpline(ys, xs, zs_cropped_copy)
    zi = Z_int(Y, X, grid=False)  # truncate to clear aperture radius

    test = np.sqrt(X ** 2 + Y ** 2)  #
    inds = np.where((test > pixel_OD) | (test < pixel_ID))  #
    coords = list(zip(inds[0], inds[1]))  # remove data points outside of clear aperture
    for j, m in enumerate(coords):  #
        zi[coords[j][0]][coords[j][1]] = np.nan  #

    M = zi.flatten(), zi
    C = Zernike_decomposition(Z, M, -1)  # Zernike fit

    if normal_tip_tilt_power:
        Piston = (Z[1].transpose(2, 0, 1)[0]) * C[2][0]  #
        TiltY = (Z[1].transpose(2, 0, 1)[1]) * C[2][1]  # remove piston, tip/tilt, and power
        TiltX = (Z[1].transpose(2, 0, 1)[2]) * C[2][2]  #
        Power = (Z[1].transpose(2, 0, 1)[4]) * C[2][4]  #

        Surf = M[1] - Piston - TiltX - TiltY - Power  ##remove piston, tip/tilt, and power
    elif len(remove_coef) > 0:
        Surf = remove_modes(M, C, Z, remove_coef)
    else:
        print('Strange things are afoot')
    return Surf.flatten(), Surf  # return 1D flattened surface and 2D surface

def initial_crop(img,ksize):
    #Obsolete - realized this was dumb. Could be used to simplify automated import
    img = cv.medianBlur(img, ksize)  # median blurring function to help with detection

    OD_circle = cv.HoughCircles(img, cv.HOUGH_GRADIENT, 1, 10000,  # Find mirror disc in data array
                              param1=20, param2=15, minRadius=100,
                              maxRadius=800)[0][0]  # Output in (x_center,y_center,radius)
    x_dist = np.arange(img.shape[0])
    y_dist = np.arange(img.shape[1])
    x,y = np.meshgrid(x_dist, y_dist)
    distance = np.sqrt(np.sum([np.power(x-OD_circle[0],2), np.power(y-OD_circle[1],2)],0))
    img[distance > OD_circle[2]] = np.max(img)
    return img

