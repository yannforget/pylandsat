"""Command-line interface."""

import json
import os
from pkg_resources import resource_string

from appdirs import user_data_dir
import click
from geopy import Nominatim
from shapely.geometry import shape, Point

from pylandsat.catalog import Catalog
from pylandsat.database import sync_catalog, sync_wrs
from pylandsat.download import Product


@click.group()
def cli():
    pass


@click.command(name='print-datadir')
def print_datadir():
    """Print user data directory where database is stored."""
    click.echo(user_data_dir(appname='pylandsat'))


@click.command(name='list-sensors')
def list_sensors():
    """Print supported sensors."""
    res = resource_string(__name__, 'files.json')
    files = json.loads(res)
    click.echo(', '.join(files.keys()))


@click.command(name='list-available-files')
@click.argument('sensor', type=click.STRING)
def list_available_files(sensor):
    res = resource_string(__name__, 'files.json')
    files = json.loads(res)
    if sensor not in files:
        click.exceptions.BadArgumentUsage('Sensor not supported.')
    click.echo(', '.join(files[sensor]))


@click.command(name='sync-database')
@click.option('-f', '--force', default=False, help='Overwrite existing files.')
def syncdb(force):
    """Download Landsat Catalog and WRS2 shapefile and export the data to a
    local SQLite database.
    """
    data_dir = user_data_dir(appname='pylandsat')
    dbpath = os.path.join(data_dir, 'landsat.db')
    if os.path.isfile(dbpath) and not force:
        click.echo('Database already exists.')
    else:
        click.echo('Syncing catalog...')
        sync_catalog()
        click.echo('Syncing WRS2 paths/rows...')
        sync_wrs()


def _geom_from_geojson(fpath):
    """Get shapely geometry from a GeoJSON file. If multiple features
    are available, only the first one is used.
    """
    with open(fpath) as f:
        geojson = json.load(f)
    if geojson['type'] == 'Feature':
        geom = shape(geojson['geometry'])
    elif geojson['type'] == 'FeatureCollection':
        geom = shape(geojson['features'][0]['geometry'])
    else:
        raise click.exceptions.BadOptionUsage('No GeoJSON feature found.')
    return geom


@click.command(name='search')
@click.option('-b', '--begin', type=click.STRING,
              help='Begin search date (YYYY-MM-DD).')
@click.option('-e', '--end', type=click.STRING,
              help='End search date (YYYY-MM-DD).')
@click.option('-g', '--geojson', type=click.Path(exists=True), default=None,
              help='Area of interest (GeoJSON file).')
@click.option('-l', '--latlon', nargs=2, type=click.FLOAT, default=None,
              help='Point of interest (decimal lat/lon).')
@click.option('-a', '--address', type=click.STRING, default=None,
              help='Address of interest.')
@click.option('-p', '--path', type=click.INT, default=None,
              help='WRS2 path.')
@click.option('-r', '--row', type=click.INT, default=None,
              help='WRS2 row.')
@click.option('-c', '--clouds', type=click.FLOAT, default=None,
              help='Max. cloud cover percentage.')
@click.option('-s', '--sensors', type=click.STRING, default=None,
              help='Comma-separated list of possible sensors.')
@click.option('-t', '--tiers', type=click.STRING, default=None,
              help='Comma-separated list of possible collection tiers.')
@click.option('--slcoff', is_flag=True,
              help='Include SLC-off LE7 scenes.')
@click.option('-o', '--output', default=None,
              type=click.Path(file_okay=True, writable=True),
              help='Output CSV file.')
def search(begin, end, geojson, latlon, address, path, row, clouds, sensors,
           tiers, slcoff, output):
    """Search for scenes in the Google Landsat Public Dataset catalog."""
    if geojson:
        geom = _geom_from_geojson(geojson)
    elif latlon:
        y, x = latlon
        geom = Point(x, y)
    elif address:
        geoloc = Nominatim(user_agent='pylandsat')
        loc = geoloc.geocode(address)
        x, y = loc.longitude, loc.latitude
        geom = Point(x, y)
    else:
        geom = None
    
    # If only year provided, set default month and day
    if len(begin) == 4:
        begin += '-01-01'
    if len(end) == 4:
        end += '-01-01'

    if sensors:
        sensors = [s.strip() for s in sensors.split(',')]
    if tiers:
        tiers = [t.trip() for t in tiers.split(',')]

    catalog = Catalog()
    scenes = catalog.search(begin, end, path, row, geom, clouds, sensors,
                            tiers, slc=not slcoff)

    if output:
        scenes.to_csv(output)
    else:
        for product_id in scenes.index:
            click.echo(product_id)


@click.command(name='download')
@click.argument('products', type=click.STRING, nargs=-1)
@click.option('-d', '--output-dir', type=click.Path(dir_okay=True), default='.',
              help='Output directory.')
@click.option('-f', '--files', type=click.STRING, default=None,
              help='Comma-separated list of files to download.')
def download(products, output_dir, files):
    """Download a Landsat product according to its identifier."""
    if files:
        files = [f.strip() for f in files.split(',')]
    for i, pid in enumerate(products):
        click.echo('Downloading {} ({}/{}).'.format(pid, i+1, len(products)))
        product = Product(pid)
        product.download(output_dir, files)


cli.add_command(search)
cli.add_command(download)
cli.add_command(syncdb)
cli.add_command(print_datadir)
cli.add_command(list_sensors)
cli.add_command(list_available_files)


if __name__ == '__main__':
    cli()
