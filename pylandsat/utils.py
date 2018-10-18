import gzip
import os
import hashlib
from datetime import datetime

import rasterio
import requests
from tqdm import tqdm


def bounds_from_transform(transform, width, height):
    """Calculate raster bounds from transform, width & height."""
    xres, yres = transform.a, transform.e
    left, top = transform.c, transform.f
    right = left + xres * width
    bottom = top + yres * height
    return rasterio.coords.BoundingBox(left, bottom, right, top)


def meta_from_pid(product_id):
    """Extract metadata contained in a Landsat Product Identifier."""
    meta = {}
    parts = product_id.split('_')
    meta['product_id'] = product_id
    meta['sensor'], meta['correction'] = parts[0], parts[1]
    meta['path'], meta['row'] = int(parts[2][:3]), int(parts[2][3:])
    meta['acquisition_date'] = datetime.strptime(parts[3], '%Y%m%d')
    meta['processing_date'] = datetime.strptime(parts[4], '%Y%m%d')
    meta['collection'], meta['tier'] = int(parts[5]), parts[6]
    return meta


def compute_md5(fpath):
    """Get hexadecimal MD5 hash of a file."""
    with open(fpath, 'rb') as f:
        h = hashlib.md5(f.read())
    return h.hexdigest()


def _size(headers):
    """Get size of a remote file in bytes by parsing the HTTP headers.
    Returns 0 if the information is not available.
    """
    if 'x-goog-stored-content-length' in headers:
        length = headers['x-goog-stored-content-length']
    elif 'Content-Length' in headers:
        length = headers['Content-Length']
    else:
        length = 0
    return int(length)


def download_file(url, outdir, progressbar=False, verify=False):
    """Download a file from an URL into a given directory.

    Parameters
    ----------
    url : str
        File to download.
    outdir : str
        Path to output directory.
    progressbar : bool, optional
        Display a progress bar.
    verify : bool, optional
        Check that remote and local MD5 haches are equal.
    
    Returns
    -------
    fpath : str
        Path to downloaded file.
    """
    fname = url.split('/')[-1]
    fpath = os.path.join(outdir, fname)
    r = requests.get(url, stream=True)
    remotesize = int(r.headers.get('Content-Length', 0))
    etag = r.headers.get('ETag', '').replace('"', '')

    if r.status_code != 200:
        raise requests.exceptions.HTTPError(str(r.status_code))

    if os.path.isfile(fpath) and os.path.getsize(fpath) == remotesize:
        return fpath
    if progressbar:
        progress = tqdm(total=remotesize, unit='B', unit_scale=True)
        progress.set_description(fname)
    with open(fpath, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024**2):
            if chunk:
                f.write(chunk)
                if progressbar:
                    progress.update(1024**2)

    r.close()
    if progressbar:
        progress.close()

    if verify:
        if not compute_md5(fpath) == etag:
            raise requests.exceptions.HTTPError('Download corrupted.')

    return fpath


def decompress(fpath, remove_archive=False):
    """Decompress a .gz archive. Returns path to decompressed file."""
    basedir, fname = os.path.dirname(fpath), os.path.basename(fpath)
    outpath = os.path.join(basedir, fname.replace('.gz', ''))
    with gzip.open(fpath, 'rb') as src, open(outpath, 'wb') as dst:
        for line in src:
            dst.write(line)
    if remove_archive:
        os.remove(fpath)
    return outpath
