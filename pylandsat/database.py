"""Download Landsat catalog from Google and WRS2 Path/Row shapefile from USGS
and export them to a Spatialite-enabled SQLite database.
"""

from collections import OrderedDict
import csv
from datetime import datetime
from dateutil.parser import isoparse
import os
import shutil
import sqlite3
import tempfile

import fiona
from appdirs import user_data_dir
from shapely import wkt
from shapely.geometry import shape
from tqdm import tqdm

from pylandsat import queries
from pylandsat import utils


def _flatten(params):
    """Flatten the list objects in a list of DB-API parameters,
    e.g. `[1, [2, 3]]` becomes `[1, 2, 3]`.
    """
    params_flat = []
    for param in params:
        if isinstance(param, list):
            for item in param:
                params_flat.append(item)
        else:
            params_flat.append(param)
    return params_flat


def _format_placeholders(query, params):
    """Replace a single '?' DB-API placeholder after each 'IN'
    statement by an array of placeholders, e.g. `IN ?` becomes
    `IN (?, ?, ?)`. Also flatten the given parameter list.
    (This is because lists are not supported as DB-API parameters.)
    """
    n_placeholders = [len(p) for p in params if isinstance(p, list)]
    for n in n_placeholders:
        placeholders = ','.join(list('?' * n))
        query = query.replace('IN ?', 'IN ({})'.format(placeholders), 1)
    return query, _flatten(params)


class LandsatDB:
    """Initialize and query a Spatialite-enabled SQLite database."""

    def __init__(self):
        os.makedirs(user_data_dir('pylandsat'), exist_ok=True)
        self.path = os.path.join(user_data_dir('pylandsat'), 'landsat.db')

    def connect(self):
        """Connect to the DB and enable Spatialite."""
        conn = sqlite3.connect(self.path)
        conn.enable_load_extension(True)
        conn.execute("SELECT load_extension('mod_spatialite');")
        return conn

    def query(self, query, params=None):
        """Perform an SQL query and returns the result as a dict."""
        conn = self.connect()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if params:
            query, params = _format_placeholders(query, params)
            c.execute(query, params)
        else:
            c.execute(query)
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]


def _parse_datestring(datestring):
    """Parse ISO-8601 date string from the index.csv file."""
    date = isoparse(datestring[:26])
    return int(date.timestamp())


def _parse_row(row):
    """Parse a row from the index.csv file."""
    INDEXES = [1, 0, 9, 10, 7, 11]
    product_id, scene_id, path, row, sensing_time, cloud_cover = (row[i] for i in INDEXES)
    path, row = int(path), int(row)
    cloud_cover = float(cloud_cover)
    sensing_time = _parse_datestring(sensing_time)
    return (product_id, scene_id, path, row, sensing_time, cloud_cover)


def sync_catalog():
    """Download Landsat catalog from Google and update the SQLite database
    accordingly.
    """
    CATALOG_URL = 'https://storage.googleapis.com/gcp-public-data-landsat/index.csv.gz'
    tmpdir = tempfile.mkdtemp(prefix='pylandsat_')
    fpath = utils.download_file(CATALOG_URL, tmpdir, progressbar=True)
    fpath = utils.decompress(fpath, remove_archive=True)

    # Create database and 'catalog' table
    db = LandsatDB()
    conn = db.connect()
    c = conn.cursor()
    c.execute(queries.CATALOG_CREATE)
    conn.commit()

    # Insert CSV rows into the SQLite database
    length = sum(1 for line in open(fpath))
    progress = tqdm(total=length, unit=' rows')
    with open(fpath) as src:
        reader = csv.reader(src)
        _ = reader.__next__()  # ignore header
        for row in reader:
            if row[1]:
                c.execute(queries.CATALOG_UPDATE, _parse_row(row))
            progress.update(1)
    progress.close()
    conn.commit()
    conn.close()
    shutil.rmtree(tmpdir)


def sync_wrs():
    """Download WRS2 descending shapefile from USGS and export it to a
    Spatialite-enabled SQLite table.
    """
    WRS_URL = 'https://landsat.usgs.gov/sites/default/files/documents/WRS2_descending.zip'
    tmpdir = tempfile.mkdtemp(prefix='pylandsat_')
    fpath = utils.download_file(WRS_URL, tmpdir)

    # Connect to the database, init spatial metadata and create the table
    db = LandsatDB()
    conn = db.connect()
    c = conn.cursor()
    c.executescript(queries.WRS_CREATE)
    conn.commit()

    def _to_wkt(feature):
        geom = shape(feature['geometry'])
        return wkt.dumps(geom, rounding_precision=8)

    # Insert values and create the spatial index
    collection = fiona.open('/WRS2_descending.shp', vfs='zip://' + fpath)
    values = ((f['properties']['PATH'], f['properties']['ROW'], _to_wkt(f))
              for f in collection)
    c.executemany(queries.WRS_UPDATE, values)
    c.execute(queries.WRS_INDEX)

    conn.commit()
    conn.close()
    shutil.rmtree(tmpdir)
