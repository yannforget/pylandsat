"""Pre-made SQL queries."""

# Create catalog table
CATALOG_CREATE = """
CREATE TABLE IF NOT EXISTS catalog (
    product_id TEXT PRIMARY KEY NOT NULL,
    scene_id TEXT,
    path INTEGER,
    row INTEGER,
    sensing_time INTEGER,
    cloud_cover FLOAT
);"""

# Insert values into catalog table
CATALOG_UPDATE = """
INSERT OR IGNORE INTO catalog (product_id, scene_id, path, row,
  sensing_time, cloud_cover)
  VALUES (?, ?, ?, ?, ?, ?);"""

# Create index on path/row
CATALOG_INDEX = "CREATE INDEX idx_catalog_pathrow ON catalog (path, row);"

# Create the WRS table
WRS_CREATE = """
SELECT InitSpatialMetadata(1);
CREATE TABLE IF NOT EXISTS wrs (
    path INTEGER,
    row INTEGER,
    PRIMARY KEY (path, row)
);
SELECT AddGeometryColumn('wrs', 'geom', 4326, 'GEOMETRY', 'XY');
"""

# Insert values into the wrs table
WRS_UPDATE = """
INSERT OR IGNORE INTO wrs (path, row, geom)
  VALUES (?, ?, GeomFromText(?, 4326));
"""

# Create a spatial index on the wrs table
WRS_INDEX = "SELECT CreateSpatialIndex('wrs', 'geom');"

# Find path/row that intersect an input geometry
WRS_SEARCH = """
SELECT path, row, AsText(geom) AS geom FROM wrs
WHERE Intersects(geom, GeomFromText(?, 4326))
  AND wrs.ROWID IN (
    SELECT ROWID FROM SpatialIndex
    WHERE f_table_name = 'wrs'
    AND search_frame = GeomFromText(?, 4326)
  );
"""

# Search the catalog using path and row as spatial filtering
CATALOG_SEARCH_PATHROW = """
SELECT catalog.product_id, catalog.scene_id, catalog.path, catalog.row,
  catalog.sensing_time, catalog.cloud_cover, AsText(wrs.geom) AS geom
FROM catalog
INNER JOIN wrs ON wrs.path = catalog.path AND wrs.row = catalog.row
WHERE catalog.path IN ? AND catalog.row IN ?
  AND catalog.sensing_time BETWEEN ? AND ?
  AND catalog.cloud_cover <= ?
  AND SUBSTR(catalog.product_id, 1, 4) IN ?
  AND SUBSTR(catalog.product_id, -2, 2) IN ?
"""

# Search the catalog using an user-provided geometry as spatial filtering
# Tuple to provide: (geom, begin date, end date, max cloud cover, list of
# sensor ids, list of tiers, geom)
CATALOG_SEARCH_GEOM = """
SELECT catalog.product_id, catalog.scene_id, catalog.path, catalog.row,
  catalog.sensing_time, catalog.cloud_cover, AsText(wrs.geom) AS geom
FROM catalog
INNER JOIN wrs ON wrs.path = catalog.path AND wrs.row = catalog.row
WHERE Intersects(wrs.geom, GeomFromText(?, 4326))
  AND catalog.sensing_time BETWEEN ? AND ?
  AND catalog.cloud_cover <= ?
  AND SUBSTR(catalog.product_id, 1, 4) IN ?
  AND SUBSTR(catalog.product_id, -2, 2) IN ?
  AND wrs.ROWID IN (
    SELECT ROWID FROM SpatialIndex
    WHERE f_table_name = 'wrs'
    AND search_frame = GeomFromText(?, 4326)
  );
"""

# Get metadata for a given product ID
CATALOG_SEARCH_PRODUCT = """
SELECT catalog.product_id, catalog.scene_id, catalog.path, catalog.row,
  date(catalog.sensing_time, 'unixepoch') AS sensing_time,
  catalog.cloud_cover, AsText(wrs.geom) AS geom
FROM catalog
INNER JOIN wrs ON catalog.path = wrs.path
  AND catalog.row = wrs.row
WHERE
  product_id = ?
"""

# Count rows in a given table
COUNT = "SELECT COUNT(*) FROM ?"

# List all tables in the database
LIST_TABLES = "SELECT name FROM sqlite_master WHERE type='table'"
