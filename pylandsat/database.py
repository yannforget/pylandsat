"""Download Landsat catalog from Google and WRS2 Path/Row shapefile from USGS
and export them to a Spatialite-enabled SQLite database.
"""

from datetime import datetime
import os
import shutil
import sqlite3
import tempfile

import fiona
import pandas as pd
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

    def query(self, sql, **kwargs):
        """Perform an SQL query and returns the result as a Pandas dataframe."""
        if 'params' in kwargs:
            sql, kwargs['params'] = _format_placeholders(sql, kwargs['params'])
        conn = self.connect()
        df = pd.read_sql(sql, conn, **kwargs)
        conn.close()
        return df


def sync_catalog():
    """Download Landsat catalog from Google and update the SQLite dabase
    accordingly.
    """
    CATALOG_URL = 'https://storage.googleapis.com/gcp-public-data-landsat/index.csv.gz'
    tmpdir = tempfile.mkdtemp(prefix='pylandsat_')
    fpath = utils.download_file(CATALOG_URL, tmpdir, progressbar=True)
    fpath = utils.decompress(fpath, remove_archive=True)

    db = LandsatDB()
    conn = db.connect()
    c = conn.cursor()

    DTYPES = {
        'PRODUCT_ID': str,
        'SCENE_ID': str,
        'SENSING_TIME': str,
        'CLOUD_COVER': float,
        'WRS_PATH': int,
        'WRS_ROW': int
    }

    # Create the table
    c.execute(queries.CATALOG_CREATE)
    conn.commit()

    # Insert values by reading and preprocessing CSV catalog in chunks
    length = sum(1 for line in open(fpath))
    progress = tqdm(total=length, unit_scale=True, unit=' rows')
    CHUNKSIZE = 10**6
    for chunk in pd.read_csv(
            fpath, usecols=DTYPES.keys(), dtype=DTYPES,
            parse_dates=['SENSING_TIME'], chunksize=CHUNKSIZE):
        nrows = len(chunk)
        chunk = chunk.dropna(axis=0)
        if chunk.empty:
            progress.update(nrows)
            continue
        chunk.SENSING_TIME = chunk.SENSING_TIME.apply(datetime.timestamp)
        chunk.SENSING_TIME = chunk.SENSING_TIME.apply(int)
        values = zip(
            chunk.PRODUCT_ID, chunk.SCENE_ID, chunk.WRS_PATH, chunk.WRS_ROW,
            chunk.SENSING_TIME, chunk.CLOUD_COVER)
        c.executemany(queries.CATALOG_UPDATE, values)
        progress.update(nrows)

    c.execute(queries.CATALOG_INDEX)
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
