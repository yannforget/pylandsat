"""Helper classes and methods to access and process Landsat Level-1 data.

Glossary of variables referring to a band with examples :

  * file name : 'LE07_L1TP_195049_20000422_20170212_01_T1_B4.TIF'
  * file suffix : 'B4'
  * band number : 4
  * band long name : 'Near Infrared (NIR)'
  * band short name : 'nir'
"""

from itertools import chain
from datetime import datetime
import json
import os
from pkg_resources import resource_string

import numpy as np
import rasterio
from rasterio.path import parse_path

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
        if band_name in (long_name, _band_shortname(long_name)):
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
    
    def __iter__(self):
        """Iterate over bands."""
        available = self.available_bands()
        for suffix, long_name in BANDS[self.sensor].items():
            short_name = _band_shortname(long_name)
            if short_name in available:
                yield Band(self, suffix)

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
        if 'SCENE_ID' in self.mtl['METADATA_FILE_INFO']:
            return self.mtl['METADATA_FILE_INFO']['SCENE_ID']
        else:
            return self.mtl['METADATA_FILE_INFO']['LANDSAT_SCENE_ID']

    @property
    def product_id(self):
        """Landsat product identifier."""
        if 'PRODUCT_ID' in self.mtl['METADATA_FILE_INFO']:
            return self.mtl['METADATA_FILE_INFO']['PRODUCT_ID']
        else:
            return self.mtl['METADATA_FILE_INFO']['LANDSAT_PRODUCT_ID']

    @property
    def spacecraft(self):
        """Spacecraft ID."""
        return self.mtl['PRODUCT_METADATA']['SPACECRAFT_ID']

    @property
    def sensor(self):
        """Sensor ID."""
        sensor = self.mtl['PRODUCT_METADATA']['SENSOR_ID']
        if sensor == 'MSS' and self.spacecraft in ('LANDSAT_4', 'LANDSAT_5'):
            sensor += '_'
        return sensor

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


class Band(rasterio.io.DatasetReader):

    def __init__(self, scene, suffix):
        self.scene = scene
        self.suffix = suffix
        self.fname = '{pid}_{suffix}.TIF'.format(
            pid=scene.product_id,
            suffix=suffix
        )
        self.fpath = os.path.join(scene.dir, self.fname)
        if suffix == 'BQA':
            self.long_name = 'Quality Band'
            self.bname = 'bqa'
            self.bnum = None
        else:
            self.long_name = BANDS[self.scene.sensor][suffix]
            self.bname = _band_shortname(self.long_name)
            self.bnum = _band_number(self.suffix)
        super().__init__(parse_path(self.fpath))

    def _gain_bias(self, unit='radiance'):
        """Get band-specific radiometric rescaling factor.
        Returns a (gain, bias) tuple. Unit can be radiance or
        reflectance.
        """
        if self.bnum == 61:
            bnum = '6_VCID_1'
        elif self.bnum == 62:
            bnum = '6_VCID_2'
        else:
            bnum = str(self.bnum)
        key_gain = unit.upper() + '_MULT_BAND_' + bnum
        key_bias = unit.upper() + '_ADD_BAND_' + bnum
        gain = self.scene.mtl['RADIOMETRIC_RESCALING'][key_gain]
        bias = self.scene.mtl['RADIOMETRIC_RESCALING'][key_bias]
        return gain, bias

    def _k1_k2(self):
        """Get band-specific thermal constants."""
        if self.bnum == 61:
            bnum = '6_VCID_1'
        elif self.bnum == 62:
            bnum = '6_VCID_2'
        else:
            bnum = str(self.bnum)
        k1_key = 'K1_CONSTANT_BAND_' + bnum
        k2_key = 'K2_CONSTANT_BAND_' + bnum
        if self.scene.spacecraft == 'LANDSAT_8':
            k1 = self.scene.mtl['TIRS_THERMAL_CONSTANTS'][k1_key]
            k2 = self.scene.mtl['TIRS_THERMAL_CONSTANTS'][k2_key]
        else:
            k1 = self.scene.mtl['THERMAL_CONSTANTS'][k1_key]
            k2 = self.scene.mtl['THERMAL_CONSTANTS'][k2_key]
        return k1, k2

    def to_radiance(self, custom_dn=None):
        """Convert DN values to TOA spectral radiance."""
        if isinstance(custom_dn, np.ndarray):
            dn = custom_dn
        else:
            dn = self.read(1)
        gain, bias = self._gain_bias(unit='radiance')
        return preprocessing.to_radiance(dn, gain, bias)

    def to_reflectance(self, custom_dn=None):
        """Convert DN values to TOA spectral reflectance."""
        if 'tir' in self.bname:
            raise ValueError('TIR bands cannot be converted to reflectance.')
        if isinstance(custom_dn, np.ndarray):
            dn = custom_dn
        else:
            dn = self.read(1)
        gain, bias = self._gain_bias(unit='reflectance')
        return preprocessing.to_reflectance(dn, gain, bias)

    def to_brightness_temperature(self, custom_dn=None):
        """Convert DN values to brightness temperature."""
        if not 'tir' in self.bname:
            raise ValueError('Only thermal bands can be converted '
                             'to brightness temperature.')
        if isinstance(custom_dn, np.ndarray):
            dn = custom_dn
        else:
            dn = self.read(1)
        radiance = self.to_radiance(custom_dn=dn)
        k1, k2 = self._k1_k2()
        return preprocessing.to_brightness_temperature(radiance, k1, k2)
