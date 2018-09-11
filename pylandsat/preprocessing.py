"""Convert quantized and calibrated scaled Digital Numbers (DN) to
top-of-atmosphere (TOA) reflectance, radiance or brightness temperature.
"""

import numpy as np


def to_radiance(dn, gain, bias):
    """Convert DN to TOA spectral radiance.

    Parameters
    ----------
    dn : 2d array
        Input image, DN values.
    gain : float
        Band-specific multiplicative rescaling factor.
    bias : float
        Band-specific additive rescaling factor.
    
    Returns
    -------
    radiance : 2d array
        Output image, TOA spectral radiance.
    """
    return gain * dn + bias


def to_reflectance(dn, gain, bias, sun_elevation_angle=None):
    """Convert DN to TOA spectral reflectance with an optional correction
    for the sun angle.

    Parameters
    ----------
    dn : 2d array
        Input image, DN values.
    gain : float
        Band-specific multiplicative rescaling factor.
    bias : float
        Band-specific additive rescaling factor.
    sun_elevation_angle : float, optional
        Sun elevation angle in degrees.
    
    Returns
    -------
    reflectance : 2d array
        Output image, TOA planetary reflectance.
    """
    reflectance = gain * dn + bias
    if sun_elevation_angle:
        reflectance /= np.sin(np.radians(sun_elevation_angle))
    return reflectance


def to_brightness_temperature(radiance, k1, k2):
    """Convert TOA spectral radiance to TOA brightness temperature.

    Parameters
    ----------
    radiance : 2d array
        Input image, TOA spectral radiance.
    k1 : float
        Band-specific thermal conversion constant.
    k2 : float
        Band-specific thermal conversion constant.
    
    Returns
    -------
    bt : 2d array
        Output image, TOA brightness temperature.
    """
    return k2 / np.log(k1 / (radiance + 1))