import numpy as np
import re
import os
from scipy.ndimage.filters import convolve

def disk_r(r,r_in = 0):
    """ Generate disks for computing halos of forest loss.
    """
    y,x = np.ogrid[-r: r+1, -r: r+1]
    disk = x**2+y**2 <= r**2
    mid = int((disk.shape[0]-1)/2)
    disk[mid, mid] = 0
    
    if r_in > 0:
        disk[x**2+y**2 <= r_in**2] = 0
    disk = disk.astype(float)/np.sum(disk)
    
    return disk


def predict_temp(img_data, pixel_width, pixel_height, deforestation_amount, deforestation_type):
    """Predict warming due to local and nonlocal forest loss. 

    Args:
        img_data (Array): Numpy array of forest cover.
        pixel_width (float): Pixel width dimension. Approx. 1000 m (0.016 degrees).
        pixel_height (float): Pixel height dimension. Approx. 1000 m (0.016 degrees).
        deforestation_amount (float): Deforestation (loss) fraction in %
        deforestation_type (str): Indicator of whether the deforestation is clear felling or fragmented loss. 
    """

    # percentage forest loss
    img_frac = img_data * (deforestation_amount / 100)

    r =1
    disk_1 = disk_r(1)
    disk_2 = disk_r(2, 1)
    disk_4 = disk_r(4, 2)
    disk_6 = disk_r(6, 4)
    disk_8 = disk_r(8, 6)

    loss_1km = convolve(img_frac, disk_1).astype(float)
    loss_1km[img_frac > 0] = 0

    loss_2km = convolve(img_frac, disk_2).astype(float)
    loss_2km[img_frac > 0] = 0
    loss_2km[loss_1km > 0] = 0

    loss_4km = convolve(img_frac, disk_4).astype(float)
    loss_4km[img_frac > 0] = 0
    loss_4km[loss_1km > 0] = 0
    loss_4km[loss_2km > 0] = 0

    loss_6km = convolve(img_frac, disk_6).astype(float)
    loss_6km[img_frac > 0] = 0
    loss_6km[loss_1km > 0] = 0
    loss_6km[loss_2km > 0] = 0
    loss_6km[loss_4km > 0] = 0

    loss_8km = convolve(img_frac, disk_8).astype(float)
    loss_8km[img_frac > 0] = 0
    loss_8km[loss_1km > 0] = 0
    loss_8km[loss_2km > 0] = 0
    loss_8km[loss_4km > 0] = 0
    loss_8km[loss_6km > 0] = 0

    # nonlocal effects regression coefficients
    m1 = 3.08
    m2 = 1.18
    m4 = 0.72
    m6 = 0.62
    m8 = 0.44

    nonlocal_warm = loss_1km*m1 + loss_2km*m2 + loss_4km*m4 + loss_6km*m6+ loss_8km*m6

    # local loss
    # choose slope based on area 
    unit = pixel_height*pixel_width
    area = np.sum(img_frac[img_frac > 0])*unit

    # area thresholds
    L_area = 1
    L_2_area = 2*np.pi # should this be four or 2?
    L_4_area = 4*np.pi
    L_6_area = 6*np.pi
    L_8_area = 8*np.pi

    # determine slope and spatial averaging scale based on areal extent:
    if area < L_area:
        m = 1.93
        disk = disk_r(1)            
    elif area < L_2_area:
        m = 3.94
        disk = disk_r(2)                
    elif area < L_4_area:
        m = 4.23
        disk = disk_r(4)                       
    elif area < L_6_area:
        m = 4.97
        disk = disk_r(6)                    
    else:
        m = 5.1
        disk = disk_r(8) 

    local_warm = convolve(img_frac, disk)*m
    local_warm[img_frac == 0] = 0

    warming = local_warm + nonlocal_warm

    if deforestation_type == 'frag':
        warming = warming * 0.5

    return warming