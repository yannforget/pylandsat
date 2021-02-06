"""Tests for scene module."""

from datetime import datetime
from pkg_resources import resource_filename

import pytest

from pylandsat import scene


def test__to_numeric():
    assert scene._to_numeric("6") == 6
    assert scene._to_numeric("6.1") == 6.1
    assert scene._to_numeric("6%") == "6%"


def test__suffix_from_fname():
    FNAME = "LC08_L1GT_044034_20130330_20170310_01_T2_B4.TIF"
    assert scene._suffix_from_fname(FNAME) == "B4"


def test__suffix_from_name():
    assert scene._suffix_from_name("red", "TM") == "B3"
    assert scene._suffix_from_name("cirrus", "OLI_TIRS") == "B9"


def test__is_band():
    assert scene._is_band("B1")
    assert scene._is_band("B6_VCID_1")
    assert not scene._is_band("C1")


def test__band_number():
    assert scene._band_number("B1") == 1
    assert scene._band_number("B6_VCID_2") == 62


def test__band_shortname():
    assert scene._band_shortname("Near Infrared (NIR)") == "nir"


@pytest.fixture
def sample_scene():
    scene_dir = resource_filename(__name__, "data/LT05_01_030_025_LT05_L1GS_030025_19860927_20161003_01_T2")
    return scene.Scene(scene_dir)    

def test_scene_init(sample_scene):
    assert sample_scene.dir


def test_scene__available_files(sample_scene):
    assert len(sample_scene._available_files()) == 1
    assert sample_scene._available_files()[0].endswith("MTL.txt")


def test_scene_file_path(sample_scene):
    assert sample_scene.file_path("MTL")


def test_scene__parse_mtl(sample_scene):
    mtl = sample_scene._parse_mtl()
    assert "PRODUCT_METADATA" in mtl


def test_scene_scene_id(sample_scene):
    assert sample_scene.scene_id == "LT50300251986270XXX01"


def test_scene_product_id(sample_scene):
    assert sample_scene.product_id == "LT05_L1GS_030025_19860927_20161003_01_T2"


def test_scene_spacecraft(sample_scene):
    assert sample_scene.spacecraft == "LANDSAT_5"


def test_scene_sensor(sample_scene):
    assert sample_scene.sensor == "TM"


def test_scene_date(sample_scene):
    assert sample_scene.date == datetime(1986, 9, 27)


def test_scene_wrs(sample_scene):
    assert sample_scene.wrs_path == 30
    assert sample_scene.wrs_row == 25
