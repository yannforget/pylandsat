"""Search for scenes in the Landsat catalog."""

from datetime import datetime

from shapely import wkt

from pylandsat import queries
from pylandsat.database import LandsatDB


SENSORS = ['LC08', 'LE07', 'LT05', 'LT04', 'LM05',
           'LM04', 'LM03', 'LM02', 'LM01']
TIERS = ['T1', 'T2', 'RT']


def _to_list(value):
    """Convert string parameter value to a list with a single element."""
    if not value:
        return None
    elif isinstance(value, list):
        return value
    elif isinstance(value, tuple):
        return list(value)
    else:
        return [value]


class Catalog():
    """Perform queries on the Landsat catalog."""

    def __init__(self):
        self.db = LandsatDB()

    def search(self, begin, end, path=None, row=None, geom=None,
               maxcloud=None, sensors=None, tiers=None, slc=True):
        """Search for scenes in the Landsat catalog.

        Parameters
        ----------
        begin : datetime
            Begin search period as a Python datetime or
            as a string (YYYY-MM-DD).
        end : datetime
            End search period as Python datetime or as
            a string (YYYY-MM-DD).
        path : int, optional
            WRS2 paths as an int or a list of int.
        row : int, optional
            WRS2 rows as an int or a list of int.
        geom : geometry, optional
            Area or point of interest as a shapely geometry.
        maxcloud : float, optional
            Max. cloud cover percentage.
        sensors : str, optional
            Sensors of interest as a str or a list of str.
        tiers : str, optional
            Collection tiers of interest as a str or a list of str.
        slc : bool, optional
            If true, exclude Landsat 7 products acquired after
            the SLC failure.

        Returns
        -------
        scenes : dataframe
            Search results as a pandas dataframe.
        """
        # Convert strings to list if necessary
        path, row = _to_list(path), _to_list(row)
        sensors, tiers = _to_list(sensors), _to_list(tiers)
        # Convert str to datetimes and to integer timestamps
        if isinstance(begin, str):
            begin = datetime.strptime(begin, '%Y-%m-%d')
        if isinstance(end, str):
            end = datetime.strptime(end, '%Y-%m-%d')
        begin = int(begin.timestamp())
        end = int(end.timestamp())
        # Convert geometry to WKT
        if geom:
            geom = wkt.dumps(geom, rounding_precision=8)
        # Default values
        if not maxcloud:
            maxcloud = 100.
        if not sensors:
            sensors = SENSORS
        if not tiers:
            tiers = TIERS
        # Spatial filter with WRS paths and rows
        if path and row:
            scenes = self.db.query(
                sql=queries.CATALOG_SEARCH_PATHROW,
                params=(path, row, begin, end, maxcloud, sensors, tiers),
                parse_dates=['sensing_time'], index_col='product_id')
        elif geom:
            scenes = self.db.query(
                sql=queries.CATALOG_SEARCH_GEOM,
                params=(geom, begin, end, maxcloud, sensors, tiers, geom),
                parse_dates=['sensing_time'], index_col='product_id')
        else:
            raise ValueError('Path/Row or Geom must be provided.')

        def _slc(row):
            FAILURE = datetime(2003, 5, 31)
            if row.index[3] != '7':
                return True
            elif row.sensing_time >= FAILURE:
                return False
            else:
                return True

        if slc:
            slc_on = scenes.apply(_slc, axis=1)
            scenes = scenes[slc_on]

        return scenes

    def wrs(self, geom):
        """Find WRS2 paths and rows that intersect a given geometry.
        Also returns the geometry of each footprint and their coverage
        of the geometry of interest if it is not a polygon.
        """
        geom_wkt = wkt.dumps(geom, rounding_precision=8)
        pathrows = self.db.query(
            queries.WRS_SEARCH, params=(geom_wkt, geom_wkt))
        if 'POLYGON' in geom_wkt:
            pathrows['coverage'] = pathrows.geom.apply(
                lambda x: geom.intersection(wkt.loads(x)).area / geom.area)
        return pathrows
