# Copyright (c) 2019, Anders Lervik.
# Distributed under the MIT License. See LICENSE for more info.
"""Common method for the package."""
import errno
import json
import os
import pathlib


FORECAST_DIR = pathlib.Path('forecast')
OBSERVATION_DIR = pathlib.Path('observations')
CHART_DIR = pathlib.Path('charts')
BUILD_DIR = pathlib.Path('build')
DIRECTORIES = (FORECAST_DIR, OBSERVATION_DIR, CHART_DIR, BUILD_DIR)

OBSERVATION_FILE = '{}-observation-{}.json'
FORECAST_FILE = 'forecast-{}.json'
CHART_FILE = 'chart-{}.json'
STATION_FILE = OBSERVATION_DIR.joinpath('stations-observations.json')
FROST_SOURCE = OBSERVATION_DIR.joinpath('sources-frost.json')
MAP_FILE = BUILD_DIR.joinpath('map.html')
TABLE_FILE = BUILD_DIR.joinpath('table.html')
UPDATE_FILE = pathlib.Path('last_update.txt')

CLIENT_ID = 'insert-frost-client-id-here'


TIME_FMT = '%Y-%m-%dT%H:%M:%SZ'
TIME_OUT_FMT = '%Y-%m-%d %H:%M:%S'


def write_text_to_file(text, filename):
    """Write the given text to the given file."""
    print('Writing file "{}"'.format(filename))
    with open(filename, 'w') as output:
        output.write(text)


def read_json_file(filename):
    """Read the given json file."""
    print('Loading file "{}"'.format(filename))
    data = {}
    with open(filename, 'r') as json_file:
        data = json.load(json_file)
    return data


def write_json_file(json_data, filename, pretty=True):
    """Write the given json data to the given file name.

    Parameters
    ----------
    json_data : object
        The object to write to the given file.
    filename : string
        The file to write to.
    pretty : boolean, optional
        If True, the output will be slightly more pretty than standard.

    """
    print('Writing file "{}"'.format(filename))
    with open(filename, 'w') as output:
        if pretty:
            json.dump(json_data, output, indent=4, sort_keys=True)
        else:
            json.dump(json_data, output)


def _make_dirs(dirname):
    """Create the given directory."""
    try:
        print('Creating directory "{}"'.format(dirname))
        os.makedirs(dirname)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise err
        if pathlib.Path(dirname).is_file():
            print('"{}" is a file. Will not create.'.format(dirname))
            raise err
        if pathlib.Path(dirname).is_dir():
            print('Directory "{}" exists. Will not create.'.format(dirname))


def set_up_directories():
    """Create directories we are going to assume are in place."""
    for dirname in DIRECTORIES:
        _make_dirs(dirname)
