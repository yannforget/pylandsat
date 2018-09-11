"""Helper classes and methods to access and process Landsat Level-1 data.

Glossary of variables referring to a band with examples :

  * file name : 'LE07_L1TP_195049_20000422_20170212_01_T1_B4.TIF'
  * file suffix : 'B4'
  * band number : 4
  * band long name : 'Near Infrared (NIR)'
  * band short name : 'nir'
"""

from datetime import datetime
import json
import os
from pkg_resources import resource_string

import rasterio

from pylandsat import preprocessing


BANDS = json.loads(resource_string(__name__, 'bands.json'))

    
def _to_numeric(value):
    """Try to convert a string to an integer or a float.
    If not possible, returns the initial string.
    """
    try:
        value  = int(value)
    except:
        try:
            value = float(value)
        except:
            pass
    return value


def _suffix_from_fname(file_name):
    """Get file suffix from file name."""
    if os.path.sep in file_name:
        file_name = os.path.basename(file_name)
    return file_name[41:].split('.')[0]


def _suffix_from_bnum(band_number):
    """Get file suffix from band number."""
    if band_number in (61, 62):
        return 'B' + str(band_number)[0] + '_VCID_' + str(band_number)[1]
    return 'B' + str(band_number)

    
def _suffix_from_name(band_name, sensor):
    """Get file suffix from band name (either long or short)."""
    if sensor not in BANDS:
        raise ValueError('Sensor %s not found.' % sensor)
    for suffix, long_name in BANDS[sensor].items():
        if band_name == long_name or band_name == _band_shortname(band_name):
            return suffix
    raise ValueError('Band %s not found.' % band_name)


def _is_band(suffix):
    """Determine if a file suffix refers to a band."""
    return suffix[0] == 'B' and suffix[1].isnumeric()


def _band_number(suffix):
    """Get band number from file suffix."""
    if _is_band(suffix):
        bnum_str = suffix[1:]
        # B6_VCID_1 = 61 & B6_VCID_2 = 62
        if 'VCID' in bnum_str:
            bnum = int(bnum_str[0] + bnum_str[-1])
        else:
            bnum = int(bnum_str)
    else:
        raise ValueError('The provided suffix does not refer to a band.')
    return bnum


def _band_shortname(long_name):
    """Get short band name, e.g. `Near Infrared (NIR)` becomes `nir` and
    `Red` becomes `red`.
    """
    if '(' in long_name:
        start = long_name.find('(') + 1
        end = long_name.find(')')
        short_name = long_name[start:end]
    else:
        short_name = long_name.replace(' ', '_').replace('-', '_')
    return short_name.lower()


class Scene:
    def __init__(self, scene_dir):
        """Landsat Level-1 scene."""
        self.dir = os.path.abspath(scene_dir)
        self.mtl = self._parse_mtl()

    def __getattr__(self, name):
        """Returns a Band object if possible."""
        if name in self.available_bands():
            return Band(self, _suffix_from_name(name, self.sensor))
        raise AttributeError()

    def _available_files(self):
        """List available files in the scene directory."""
        return [f for f in os.listdir(self.dir)
                if f.endswith('.TIF') or f.endswith('.txt')]

    def available_bands(self):
        """List short names of available bands."""
        bands = []
        for fname in self._available_files():
            suffix = _suffix_from_fname(fname)
            if _is_band(suffix):
                long_name = BANDS[self.sensor][suffix]
                bands.append(_band_shortname(long_name))
        return bands

    def file_path(self, suffix):
        """Find file path according to a given file suffix."""
        for fname in self._available_files():
            if suffix == _suffix_from_fname(fname):
                return os.path.join(self.dir, fname)
        raise ValueError('Suffix %s not available.' % suffix)

    def _parse_mtl(self):
        """Parse MTL metadata file.

        Returns
        -------
        mtl : dict
            MTL metadata in a dictionnary.
        """
        mtl = {}
        fpath = self.file_path('MTL')
        f = open(fpath)
        for line in f.readlines():
            if line.startswith('GROUP = L1_METADATA_FILE'):
                pass  # ignore main group
            elif line.strip().startswith('END'):
                pass  # ignore end statements
            elif line.strip().startswith('GROUP'):
                group = line.split('=')[-1].strip()
                mtl[group] = {}
            else:
                param, value = [s.strip() for s in line.split('=')]
                value = value.replace('"', '')
                value = _to_numeric(value)
                mtl[group][param] = value
        return mtl

    @property
    def scene_id(self):
        """Landsat scene identifier."""
        return self.mtl['METADATA_FILE_INFO']['SCENE_ID']

    @property
    def product_id(self):
        """Landsat product identifier."""
        return self.mtl['METADATA_FILE_INFO']['PRODUCT_ID']

    @property
    def spacecraft(self):
        """Spacecraft ID."""
        return self.mtl['PRODUCT_METADATA']['SPACECRAFT_ID']

    @property
    def sensor(self):
        """Sensor ID."""
        return self.mtl['PRODUCT_METADATA']['SENSOR_ID']

    @property
    def date(self):
        """Acquisition date."""
        date_acquired = self.mtl['PRODUCT_METADATA']['DATE_ACQUIRED']
        return datetime.strptime(date_acquired, '%Y-%m-%d')

    @property
    def wrs_path(self):
        """WRS2 Path."""
        return self.mtl['PRODUCT_METADATA']['WRS_PATH']

    @property
    def wrs_row(self):
        """WRS2 Row."""
        return self.mtl['PRODUCT_METADATA']['WRS_ROW']
    
    @property
    def quality(self):
        """Quality band."""
        return Band(self, 'BQA')


class Band:
    def __init__(self, scene, suffix):
        """A Landsat Band."""
        self.scene = scene
        self.suffix = suffix
        self.path = self.scene.file_path(suffix)
        self.long_name = BANDS[self.scene.sensor][suffix]
        self.name = _band_shortname(self.long_name)
        self.bnum = _band_number(self.suffix)

    def read(self):
        """Read band data as a numpy 2d array."""
        with rasterio.open(self.path) as src:
            return src.read(1)

    @property
    def profile(self):
        """Rasterio profile."""
        with rasterio.open(self.path) as src:
            return src.profile

    @property
    def crs(self):
        """Raster CRS."""
        with rasterio.open(self.path) as src:
            return src.crs

    @property
    def transform(self):
        """Raster affine transform."""
        with rasterio.open(self.path) as src:
            return src.transform

    @property
    def width(self):
        """Raster width."""
        with rasterio.open(self.path) as src:
            return src.width

    @property
    def height(self):
        """Raster height."""
        with rasterio.open(self.path) as src:
            return src.height

    def _gain_bias(self, unit='radiance'):
        """Get band-specific radiometric rescaling factor.
        Returns a (gain, bias) tuple. Unit can be radiance or
        reflectance.
        """
        key_gain = unit.upper() + '_MULT_BAND_' + self.bnum
        key_bias = unit.upper() + '_ADD_BAND_' + self.bnum
        gain = self.scene.mtl['RADIOMETRIC_RESCALING'][key_gain]
        bias = self.scene.mtl['RADIOMETRIC_RESCALING'][key_bias]
        return gain, bias

    def _k1_k2(self):
        """Get band-specific thermal constants."""
        k1_key = 'K1_CONSTANT_BAND_' + self.bnum
        k2_key = 'K2_CONSTANT_BAND_' + self.bnum
        k1 = self.scene.mtl['THERMAL_CONSTANTS'][k1_key]
        k2 = self.scene.mtl['THERMAL_CONSTANTS'][k2_key]
        return k1, k2

    def to_radiance(self):
        """Convert DN values to TOA spectral radiance."""
        gain, bias = self._gain_bias(unit='radiance')
        return preprocessing.to_radiance(self.read(), gain, bias)

    def to_reflectance(self):
        """Convert DN values to TOA spectral reflectance."""
        gain, bias = self._gain_bias(unit='reflectance')
        return preprocessing.to_reflectance(self.read(), gain, bias)

    def to_brightness_temperature(self):
        """Convert DN values to brightness temperature."""
        radiance = self.to_radiance()
        k1, k2 = self._k1_k2()
        return preprocessing.to_brightness_temperature(radiance, k1, k2)
