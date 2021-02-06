"""Tests for utils module."""

from datetime import datetime
import os
from pkg_resources import resource_filename
from tempfile import TemporaryDirectory
import shutil

from rasterio import Affine

from pylandsat import utils


def test_bounds_from_transform():
    transform = Affine(300, 0, 101985, 0, -300, 2826915)
    width, height = 791, 718
    bounds = utils.bounds_from_transform(transform, width, height)
    assert bounds.left == 101985
    assert bounds.bottom == 2611515
    assert bounds.right == 339285
    assert bounds.top == 2826915


def test_meta_from_pid():
    meta = utils.meta_from_pid("LC08_L1GT_044034_20130330_20170310_01_T2")
    assert meta.get("product_id") == "LC08_L1GT_044034_20130330_20170310_01_T2"
    assert meta.get("sensor") == "LC08"
    assert meta.get("correction") == "L1GT"
    assert meta.get("path") == 44
    assert meta.get("row") == 34
    assert meta.get("acquisition_date") == datetime(2013, 3, 30)
    assert meta.get("processing_date") == datetime(2017, 3, 10)
    assert meta.get("collection") == 1
    assert meta.get("tier") == "T2"


def test_compute_md5():
    sample = resource_filename(__name__, "data/sample.txt")
    assert utils.compute_md5(sample) == "f5030b0630377ffd1d4cff3a0ee18b9d"


def test_decompress():
    sample = resource_filename(__name__, "data/sample.txt")
    archive = resource_filename(__name__, "data/sample.txt.gz")
    with TemporaryDirectory(prefix="pylandsat_") as tmp_dir:
        archive_tmp = os.path.join(tmp_dir, "sample.txt.gz")
        sample_tmp = os.path.join(tmp_dir, "sample.txt")
        shutil.copy(archive, archive_tmp)
        utils.decompress(archive_tmp)
        orig_hash = utils.compute_md5(sample)
        new_hash = utils.compute_md5(sample_tmp)
        assert orig_hash == new_hash
