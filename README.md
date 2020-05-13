# Description

**pylandsat** is a Python package that allows you to search and download
Landsat scenes from the public dataset hosted on
[Google Cloud](https://cloud.google.com/storage/docs/public-datasets/landsat).
Additionally, it includes a set of classes and methods to access and
preprocess the downloaded scenes.

Only Landsat [Collection 1](https://landsat.usgs.gov/landsat-collections) is supported, i.e. level-1 data products from the following sensors and satellite missions:

* Landsat 8 OLI/TIRS
* Landsat 7 ETM+
* Landsat 4-5 TM
* Landsat 1-5 MSS

# Installation

`pip install pylandsat`

# Command-line interface

## Download one or multiple scenes

### Usage

```bash
Usage: pylandsat download [OPTIONS] [PRODUCTS]...

  Download a Landsat product according to its identifier.

Options:
  -d, --output-dir PATH  Output directory.
  -f, --files TEXT       Comma-separated list of files to download.
  --help                 Show this message and exit.
```

### Examples

```bash
# Download an entire product in the current directory
pylandsat download LE07_L1TP_205050_19991104_20170216_01_T1

# Download multiple products
pylandsat download \
    LE07_L1TP_205050_19991104_20170216_01_T1 \
    LE07_L1TP_206050_19991111_20170216_01_T1

# Download only the blue, green and red bands
pylandsat download --files B1.TIF,B2.TIF,B3.TIF \
    LE07_L1TP_205050_19991104_20170216_01_T1

# Download only quality band
pylandsat download --files BQA.TIF \
    LE07_L1TP_205050_19991104_20170216_01_T1
```

## Search for scenes

To allow large and fast queries, **pylandsat** works with a local dump of the Landsat catalog hosted on Google Cloud. As such, an initial sync is required :

```bash
# Sync local Landsat catalog
pylandsat sync-database

# Force update
pylandsat -f sync-database
```

The database is stored in a local directory that can be displayed using the following command :

```bash
pylandsat print-datadir
```

Once the database has been created, the local catalog can be queried.

### Usage

```bash
Usage: pylandsat search [OPTIONS]

  Search for scenes in the Google Landsat Public Dataset catalog.

Options:
  -b, --begin TEXT       Begin search date (YYYY-MM-DD).
  -e, --end TEXT         End search date (YYYY-MM-DD).
  -g, --geojson PATH     Area of interest (GeoJSON file).
  -l, --latlon FLOAT...  Point of interest (decimal lat/lon).
  -p, --path INTEGER     WRS2 path.
  -r, --row INTEGER      WRS2 row.
  -c, --clouds FLOAT     Max. cloud cover percentage.
  -s, --sensors TEXT     Comma-separated list of possible sensors.
  -t, --tiers TEXT       Comma-separated list of possible collection tiers.
  --slcoff               Include SLC-off LE7 scenes.
  -o, --output PATH      Output CSV file.
  --help                 Show this message and exit.
```

At least three options must be provided: `--begin` and `--end` (i.e. the period of interest), and a geographic extent (`--path` and `--row`, `--latlon`, `--address` or `--geojson`). By default, **pylandsat** lists all the product IDs matching the query. The full response can be exported to a CSV file using the `--output` option. Note that is the spatial extent is provided as a GeoJSON file, only the first feature will be considered.

### Examples

```bash
# If only the year is provided, date is set to January 1st
pylandsat search \
    --begin 1999 --end 2000 \
    --path 206 --row 50 \
    --clouds 0

# Using latitude and longitude
pylandsat search \
    --begin 2000 --end 2010 \
    --latlon 50.85 4.34

# Using a polygon in a GeoJSON file
pylandsat search \
    --begin 2000 --end 2010 \
    --geojson brussels.geojson

# Using an address that will be geocoded
pylandsat search \
    --begin 2000 --end 2010 \
    --address 'Brussels, Belgium'

# Limit to TM and ETM sensors
pylandsat search \
    --begin 1990 --end 2010 \
    --address 'Brussels, Belgium' \
    --sensors LT04,LT05,LE07

# Export results into a CSV file
pylandsat search \
    --begin 1990 --end 2010 \
    --address 'Brussels, Belgium' \
    --sensors LT04,LT05,LE07 \
    --output scenes.csv
```

```bash
# List available sensors, i.e. possible values
# for the `--sensors` option
pylandsat list-sensors

# List available files for a given sensor
pylandsat list-available-files LT05
```

# Python API

## Search the catalog

``` python
from datetime import datetime

from shapely.geometry import Point
from pylandsat import Catalog, Product

catalog = Catalog()

begin = datetime(2000, 1, 1)
end = datetime(2010, 1, 1)
geom = Point(4.34, 50.85)

# Results are returned as a list
scenes = catalog.search(
    begin=begin,
    end=end,
    geom=geom,
    sensors=['ETM', 'LC08']
)

# Get the product ID of the scene with the lowest cloud cover
scenes = scenes.sort_values(by='cloud_cover', ascending=True)
product_id = scenes.index[0]

# Download the scene
product = Product(product_id)
product.download(out_dir='data')
```

## Load and preprocess data

``` python
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from pylandsat import Scene

# Access data
scene = Scene('data/LE07_L1TP_205050_19991104_20170216_01_T1')
print(scene.available_bands())
print(scene.product_id)
print(scene.sensor)
print(scene.date)

# Access MTL metadata
print(scene.mtl['IMAGE_ATTRIBUTES']['CLOUD_COVER_LAND'])

# Quality band
plt.imshow(scene.quality.read())

# Access band data
nir = scene.nir.read(1)
red = scene.red.read(1)
ndvi = (nir + red) / (nir - red)

# Access band metadata
print(scene.nir.bname)
print(scene.nir.fname)
print(scene.nir.profile)
print(scene.nir.width, scene.nir.height)
print(scene.nir.crs)

# Use reflectance values instead of DN
nir = scene.nir.to_reflectance()

# ..or brightness temperature
tirs = scene.tirs.to_brightness_temperature()

# Save file to disk
with rasterio.open('temperature.tif', 'w', **scene.tirs.profile) as dst:
    dst.write(tirs, 1)
```
