"""Downloading Landsat products from Google public dataset."""

import json
import os
from pkg_resources import resource_string

from pylandsat.utils import download_file, meta_from_pid

BASE_URL = ('https://storage.googleapis.com/gcp-public-data-landsat/'
            '{sensor}/{collection:02}/{path:03}/{row:03}/{product_id}/')


class Product:
    """Landsat product to download."""
    def __init__(self, product_id):
        """Initialize a product download.

        Attributes
        ----------
        product_id : str
            Landsat product identifier.
        out_dir : str
            Path to output directory.
        """
        self.product_id = product_id
        self.meta = meta_from_pid(product_id)
        self.baseurl = BASE_URL.format(**self.meta)

    @property
    def available(self):
        """List all available files."""
        resource = resource_string(__name__, 'files.json')
        labels = json.loads(resource)
        return labels[self.meta['sensor']]

    def _url(self, label):
        """Get download URL of a given file according to its label."""
        if 'README' in label:
            basename = label
        else:
            basename = self.product_id + '_' + label
        return self.baseurl + basename

    def download(self, out_dir, progressbar=True, files=None):
        """Download a Landsat product.

        Parameters
        ----------
        out_dir : str
            Path to output directory. A subdirectory named after the
            product ID will automatically be created.
        progressbar : bool, optional
            Show a progress bar.
        files : list of str, optional
            Specify the files to download manually. By default, all available
            files will be downloaded.
        """
        dst_dir = os.path.join(out_dir, self.product_id)
        os.makedirs(dst_dir, exist_ok=True)
        if not files:
            files = self.available
        else:
            files = [f for f in files if f in self.available]

        for label in files:
            if '.tif' in label:
                label = label.replace('.tif', '.TIF')
            url = self._url(label)
            download_file(url, dst_dir, progressbar=progressbar, verify=True)
