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
        if not maxcloud and not isinstance(maxcloud, float):
            maxcloud = 100.
        if not sensors:
            sensors = SENSORS
        if not tiers:
            tiers = TIERS

        # Spatial filter with WRS paths and rows
        if path and row:
            scenes = self.db.query(
                query=queries.CATALOG_SEARCH_PATHROW,
                params=(path, row, begin, end, maxcloud, sensors, tiers))
        elif geom:
            scenes = self.db.query(
                query=queries.CATALOG_SEARCH_GEOM,
                params=(geom, begin, end, maxcloud, sensors, tiers, geom))
        else:
            raise ValueError('No spatial information provided.')
        
        for scene in scenes:
            scene.update(
                sensing_time=datetime.fromtimestamp(scene['sensing_time']))

        def _slc_on(scene):
            FAILURE = datetime(2003, 5, 31)
            sat = scene['product_id'][3]
            if sat != '7':
                return True
            elif scene['sensing_time'] >= FAILURE:
                return False
            else:
                return True
        
        if slc:
            scenes_ = scenes.copy()
            scenes = [scene for scene in scenes_ if _slc_on(scene)]

        return scenes

    def wrs(self, geom):
        """Find WRS2 paths and rows that intersect a given geometry.
        Also returns the geometry of each footprint and their coverage
        of the geometry of interest if it is not a polygon.
        """
        geom_wkt = wkt.dumps(geom, rounding_precision=8)
        path_row = self.db.query(
            queries.WRS_SEARCH, params=(geom_wkt, geom_wkt))

        if 'POLYGON' in geom_wkt:
            for pr in path_row:
                footprint = wkt.loads(pr['geom'])
                cover = geom.intersection(footprint).area / geom.area
                pr.update(cover=cover)

        return path_row

    def metadata(self, product_id):
        """Get available metadata for a given scene identified
        by its Product Identifier.
        """
        response = self.db.query(
            queries.CATALOG_SEARCH_PRODUCT, params=(product_id, ))
        return response[0]
