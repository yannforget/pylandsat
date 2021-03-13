import os
import requests
from tempfile import TemporaryDirectory

from pylandsat.download import Product


def test_download_lc05(monkeypatch):
    PID = "LT05_L1TP_195051_19950807_20170107_01_T1"
    product = Product(PID)

    def mockreturn(self, chunk_size):
        return [b"", b"", b""]

    monkeypatch.setattr(requests.Response, "iter_content", mockreturn)

    with TemporaryDirectory() as tmpdir:
        product.download(tmpdir, progressbar=False, verify=False)
        scene_dir = os.path.join(tmpdir, PID)
        assert os.path.isdir(scene_dir)
        contents = os.listdir(scene_dir)
        assert f"{PID}_B1.TIF" in contents
        assert f"{PID}_MTL.txt" in contents


def test_download_le07(monkeypatch):
    PID = "LE07_L1TP_205050_19991104_20170216_01_T1"
    product = Product(PID)

    def mockreturn(self, chunk_size):
        return [b"", b"", b""]

    monkeypatch.setattr(requests.Response, "iter_content", mockreturn)

    with TemporaryDirectory() as tmpdir:
        product.download(tmpdir, progressbar=False, verify=False)
        scene_dir = os.path.join(tmpdir, PID)
        assert os.path.isdir(scene_dir)
        contents = os.listdir(scene_dir)
        assert f"{PID}_B1.TIF" in contents
        assert f"{PID}_B6_VCID_1.TIF" in contents
        assert f"{PID}_MTL.txt" in contents


def test_download_lc08(monkeypatch):
    PID = "LC08_L1TP_193027_20200712_20200722_01_T1"
    product = Product(PID)

    def mockreturn(self, chunk_size):
        return [b"", b"", b""]

    monkeypatch.setattr(requests.Response, "iter_content", mockreturn)

    with TemporaryDirectory() as tmpdir:
        product.download(tmpdir, progressbar=False, verify=False)
        scene_dir = os.path.join(tmpdir, PID)
        assert os.path.isdir(scene_dir)
        contents = os.listdir(scene_dir)
        assert f"{PID}_B1.TIF" in contents
        assert f"{PID}_BQA.TIF" in contents
        assert f"{PID}_MTL.txt" in contents
