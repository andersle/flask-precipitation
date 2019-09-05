# Copyright (c) 2019, Anders Lervik.
# Distributed under the MIT License. See LICENSE for more info.
"""Get precipitation data, using the Frost API."""
import datetime
import pathlib
import requests
import numpy as np
from numpy.linalg import norm
import pyproj
from common import (
    read_json_file,
    write_json_file,
    OBSERVATION_FILE,
    OBSERVATION_DIR,
    STATION_FILE,
    FROST_SOURCE,
    set_up_directories,
    CLIENT_ID,
)


TARGET_RESOLUTION = 'P1D'
PREFERRED_OFFSET = 'PT6H'

ECEF = pyproj.Proj(proj='geocent', ellps='WGS84', datum='WGS84')
LLA = pyproj.Proj(proj='latlong', ellps='WGS84', datum='WGS84')


def _check_response(response):
    """Check a request response.

    Parameters
    ----------
    response : object like requests.models.Response
        The response to check.

    Returns
    -------
    out : boolean
        True if everything seems fine. False otherwise.

    """
    if response.status_code == 200:
        print('Frost return status: {}'.format(response.status_code))
        return True
    ret = response.json()
    print('Could not get Frost data: {}'.format(response.status_code))
    print('Message: {}'.format(ret['error']['message']))
    print('Reason: {}'.format(ret['error']['reason']))
    return False


def get_frost_sources(client_id):
    """Download a list of all sources from Frost.

    Parameters
    ----------
    client_id : string
        The client id to use for the request.

    Returns
    -------
    sources : dict
        A dict containing the json representation of the sources.

    """
    sources = {}
    if not pathlib.Path(FROST_SOURCE).is_file():
        print('Source "{}" not found --- downloading!'.format(FROST_SOURCE))
        url = 'https://frost.met.no/sources/v0.jsonld'
        response = requests.get(url, {}, auth=(client_id, ''))
        if _check_response(response):
            sources = response.json()['data']
            print('Storing sources.')
            write_json_file(sources, FROST_SOURCE)
    else:
        print('Reading sources from file "{}".'.format(FROST_SOURCE))
        sources = read_json_file(FROST_SOURCE)
    return sources


def get_frost_observation(client_id, sources, reference_time):
    """Download precipitation observation from Frost.

    Parameters
    ----------
    client_id : string
        The client id to use for the request to Frost.
    sources : string
        The sources to download information for.
    reference_time : string
        The time to get observations for.

    Returns
    -------
    out : dict
        The json representation of the downloaded observation(s).

    """
    url = 'https://frost.met.no/observations/v0.jsonld'
    parameters = {
        'sources': sources,
        'elements': 'sum(precipitation_amount {})'.format(TARGET_RESOLUTION),
        'referencetime': reference_time,
    }
    response = requests.get(url, parameters, auth=(client_id, ''))
    if _check_response(response):
        data = response.json()['data']
        return data
    return {}


def get_source_data(sources):
    """Extract the information we need about the sources.

    Parameters
    ----------
    sources : dict
        The json representation of the sources.

    Returns
    -------
    source_id : list of dicts
        The extracted source information, represented as a dict.
    coordinates : numpy.array
        The locations (lon, lat) for the different sources.
    pos_sources : numpy.array
        The position of the sources in ECEF coordinates.

    """
    coordinates = []
    source_id = []
    for source in sources:
        # Pick out the data we need from the source:
        if 'geometry' not in source:
            continue
        lon = float(source['geometry']['coordinates'][0])
        lat = float(source['geometry']['coordinates'][1])
        if 'masl' in source:
            masl = float(source['masl'])
        else:
            masl = 0
        source_id.append(
            {
                'id': source['id'],
                'name': source['name'],
                'lon': lon,
                'lat': lat,
                'masl': masl,
            }
        )
        coordinates.append([lon, lat, masl])
    coordinates = np.array(coordinates)

    xpos, ypos, zpos = pyproj.transform(
        LLA,
        ECEF,
        coordinates[:, 0],
        coordinates[:, 1],
        coordinates[:, 2],
    )
    pos_sources = np.column_stack((xpos, ypos, zpos))
    return source_id, coordinates, pos_sources


def get_closest_sources(point, pos_sources, number=3):
    """Get the N closest sources to the given position.

    Parameters
    ----------
    point : dict
        The point (lon, lat, altitude) we are considering.
    pos_sources : numpy.array
        The positions of all stations we are considering.
    number : int
        The number of closest sources to obtain.

    Returns
    -------
    out[1] : numpy.array of integers
        The indices for the N closest stations.
    out[1] : numpy.array
        The distances for the N closest stations

    """
    xpos, ypos, zpos = pyproj.transform(
        LLA, ECEF, point['lon'], point['lat'], point.get('masl', 0.0),
    )
    pos = np.array([xpos, ypos, zpos])
    dist_vec = pos_sources - pos
    dist = norm(dist_vec, axis=-1)
    idx = np.argsort(dist)[:number]
    return idx, dist[idx]


def find_closest_stations(places_file, client_id, number=3):
    """Find n closest stations for given places.

    Parameters
    ----------
    places_file : string
        A file to read place locations for. These are the places we
        will locate the closest stations for.
    client_id : string
        The client id to use for requests to Frost.
    number : integer
        The number of closest stations to find.

    Returns
    -------
    places : dict
        The places read from the given file with places. The station
        information is now included in this dictionary.

    """
    print('\nGetting places.')
    places = read_json_file(places_file)
    print('\nGetting stations.')
    sources = get_frost_sources(client_id)
    stations, _, pos_sources = get_source_data(sources)

    for place in places:
        idx, dist = get_closest_sources(place, pos_sources, number=number)
        place['stations'] = []
        for i, disti in zip(idx, dist):
            place['stations'].append(
                {
                    'id': stations[i]['id'],
                    'name': stations[i]['name'],
                    'lon': stations[i]['lon'],
                    'lat': stations[i]['lat'],
                    'distance': disti,
                }
            )
        print('\nStations found for: "{}"'.format(place['name']))
        for station in place['stations']:
            print('  * {id} - "{name}": {distance}'.format(**station))
    print('\nStoring places & stations.')
    write_json_file(places, places_file)
    return places


def extract_observations(raw_data):
    """Extract observation data from the given json raw data."""
    observations = {}
    for item in raw_data:
        source, idx = item['sourceId'].split(':')
        if int(idx) != 0:
            continue
        observations[source] = {
            'offset': [],
            'value': [],
        }
        for i in item['observations']:
            if i['timeResolution'] != TARGET_RESOLUTION:
                continue
            if 'precipitation' not in i['elementId']:
                continue
            observations[source]['offset'].append(i['timeOffset'])
            observations[source]['value'].append(i['value'])
    return observations


def find_closest_valid(observations, stations, number=3):
    """Find the N closest stations with valid observations.

    Parameters
    ----------
    observations : dict
        A dict with the current observations.
    stations : list of dicts
        A list of the stations to consider.
    number : int
        The maximum number of valid observations to consider.

    Returns
    -------
    closest : list of strings
        The identifiers for the N closest stations with valid
        observations.

    """
    closest = []
    for station in stations:
        if station['id'] not in observations:
            continue
        if observations[station['id']]['value']:
            closest.append(station['id'])
        if len(closest) >= number:
            break
    return closest


def get_raw_observation_data(observation_file, client_id, sources,
                             reference_time):
    """Get the raw observation data from Frost.

    Parameters
    ----------
    observation_file : string
        A file containing observation data. If this file is not present,
        observation data will be downloaded from Frost. Such downloaded
        data will then be written to this file.
    client_id : string
        The client id to use for a request to Frost.
    sources : string
        The stations to download observations for.
    reference_time : string
        The target time to get observations for.

    Returns
    -------
    raw_data : dict
        The json representation of the observation(s).

    """
    if not pathlib.Path(observation_file).is_file():
        print('Getting observation(s) from Frost.')
        raw_data = get_frost_observation(
            client_id, sources, reference_time
        )
        write_json_file(raw_data, observation_file)
    else:
        print('Using local observation file.')
        raw_data = read_json_file(observation_file)
    return raw_data


def get_precipitation_data_time(place, now, days, client_id):
    """Get precipitation data for a given number of days ago.

    Parameters
    ----------
    place : dict
        The place we are getting observations for.
    now : object like datetime.datetime
        The current time.
    days : int
        The number of days ago we will get observation data for.
    client_id : string
        The client id to use for a request to Frost.

    Returns
    -------
    ref_time : string
        The reference time we are getting data for.
    data : list of dicts
        The precipitation data we got observations for.

    """
    stations = {station['id']: station for station in place['stations']}
    sources = ','.join([station['id'] for station in place['stations']])

    ref_time = datetime.datetime.strftime(
        now - datetime.timedelta(days=days), '%Y-%m-%d'
    )
    raw_data = get_raw_observation_data(
        OBSERVATION_DIR.joinpath(
            OBSERVATION_FILE.format(place['name'], ref_time)
        ),
        client_id,
        sources,
        ref_time
    )
    observations = extract_observations(raw_data)
    closest = find_closest_valid(observations, place['stations'], number=3)
    data = extract_precipitation_data(observations, closest, stations)
    return ref_time, data


def get_precipitation_observations(places_json_file, client_id, now,
                                   number=15):
    """Get precipitation data for a set of places.

    Parameters
    ----------
    places_json_file : string
        A file to read locations for which we will get precipitation data.
    client_id : string
        A client id to use for requests to Frost.
    now : object like datetime.datetime
        The current time.
    number : integer
        The maximum number of stations to consider.

    Returns
    -------
    None, but will write the observation data downloaded to the file
    STATION_FILE.

    """
    places = find_closest_stations(places_json_file, client_id, number=number)
    all_place_data = []
    for place in places:
        print('\nGetting observations for: "{}"'.format(place['name']))
        place_data = {
            'name': place['name'],
            'observations': [],
            'reference_time': [],
        }
        for days in (1, 2, 3):
            reference_time, precipitation_data = get_precipitation_data_time(
                place,
                now,
                days,
                client_id,
            )
            place_data['observations'].append(precipitation_data)
            place_data['reference_time'].append(reference_time)
        all_place_data.append(place_data)
    group_data_on_stations(all_place_data, STATION_FILE)


def extract_precipitation_data(observations, closest, stations):
    """Extract the precipitation data from the given observations.

    Parameters
    ----------
    observations : dict
        A dict containing the observations to extract information from.
    closest : list of strings
        A list containing the stations we are interested in.
    stations : dict
        A dict containing information about all stations we are
        considering.

    Returns
    -------
    precipitation_data : list of dicts
        The extracted precipitation data.

    """
    precipitation_data = []
    for station in closest:
        offsets = observations[station]['offset']
        if PREFERRED_OFFSET not in offsets:
            idx = 0
            offset = offsets[idx]
        else:
            idx = offsets.index(PREFERRED_OFFSET)
            offset = offsets[idx]
        value = observations[station]['value'][idx]
        precipitation_data.append(
            {
                'station': stations[station],
                'offset': offset,
                'value': value,
            }
        )
    return precipitation_data


def group_data_on_stations(place_data, outfile=None):
    """Organize the precipitation data on stations.

    Parameters
    ----------
    place_data : list of dicts
        The precipitation data, grouped on places.
    outfile : string, optional
        A file to write the grouped data to.

    Returns
    -------
    stations : dict
        The precipitation data, grouped on stations.

    """
    stations = {}
    for data in place_data:
        name = data['name']
        for i, ref_time in enumerate(data['reference_time']):
            observations = data['observations'][i]
            for observation in observations:
                station_data = observation['station']
                station_id = station_data['id']
                if station_id not in stations:
                    stations[station_id] = {
                        'name': station_data['name'],
                        'lat': station_data['lat'],
                        'lon': station_data['lon'],
                        'values': {},
                        'distance': {},
                        'offsets': {}
                    }
                station = stations[station_id]
                if name not in station['distance']:
                    station['distance'][name] = station_data['distance']
                if ref_time not in station['values']:
                    station['values'][ref_time] = observation['value']
                if ref_time not in station['offsets']:
                    station['offsets'][ref_time] = observation['offset']
    if outfile is not None:
        print('\nStoring observations for stations.')
        write_json_file(stations, outfile)
    return stations


def main(client_id):
    """Download precipitation data."""
    set_up_directories()
    now = datetime.datetime(2019, 9, 4, 12, 22, 59, 855905)
    get_precipitation_observations('places.json', client_id, now, number=15)


if __name__ == '__main__':
    main(CLIENT_ID)
