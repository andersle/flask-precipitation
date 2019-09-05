# Copyright (c) 2019, Anders Lervik.
# Distributed under the MIT License. See LICENSE for more info.
"""Parse and interpret some XML data from the MET Norway Weather API."""
import datetime
import json
from lxml import etree
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.cm import get_cmap
from matplotlib.gridspec import GridSpec
import altair as alt
import pandas as pd
from common import TIME_FMT, TIME_OUT_FMT

plt.style.use('seaborn-talk')


DEBUG = False


def _parse_time_string(time_str):
    """Parse a string into a date time object."""
    return datetime.datetime.strptime(time_str, TIME_FMT)


def parse_tag_attribute(tag, attribute, raw_value):
    """Parse an attribute of a given tag.

    Parameters
    ----------
    tag : string
        The tag to parse for.
    attribute : string
        The attribute to parse.
    raw_value : string
        The raw value to parse.

    Returns
    -------
    out : float, int, string or other object
        The parsed value.

    """
    parsers = {
        'location': {
            'altitude': float,
            'latitude': float,
            'longitude': float,
        },
        'temperature': {
            'value': float,
        },
        'windDirection': {
            'deg': float,
        },
        'windSpeed': {
            'mps': float,
            'beaufort': int,
        },
        'humidity': {
            'value': float,
        },
        'pressure': {
            'value': float,
        },
        'cloudiness': {
            'percent': float,
        },
        'lowClouds': {
            'percent': float,
        },
        'mediumClouds': {
            'percent': float,
        },
        'highClouds': {
            'percent': float,
        },
        'temperatureProbability': {
            'value': int,
        },
        'windProbability': {
            'value': int,
        },
        'dewpointTemperature': {
            'value': float,
        },
        'precipitation': {
            'value': float,
            'minvalue': float,
            'maxvalue': float,
        },
        'minTemperature': {
            'value': float,
        },
        'maxTemperature': {
            'value': float,
        },
        'symbol': {
            'number': int,
        },
        'symbolProbability': {
            'value': int,
        },
        'time': {
            'from': _parse_time_string,
            'to': _parse_time_string,
        },
        'model': {
            'termin': _parse_time_string,
            'runended': _parse_time_string,
            'nextrun': _parse_time_string,
            'from': _parse_time_string,
            'to': _parse_time_string,
        },
    }
    parser = parsers.get(tag, {}).get(attribute, str)
    return parser(raw_value)


def get_attributes(node):
    """Read all attributes from the given node.

    Parameters
    ----------
    node : object like lxml.etree._Element
        The node to read attributes for.

    Returns
    -------
    attribs : dict
        The read attributes.

    """
    attribs = {}
    for attr in node.attrib:
        attribs[attr] = parse_tag_attribute(node.tag, attr, node.attrib[attr])
    return attribs


def parse_xml(raw_xml):
    """Parse the given xml data.

    Parameters
    ----------
    raw_xml : string
        The raw xml data we are going to read.

    Returns
    -------
    models : list of dicts
        The model information found in the raw xml data.
    points : list of dicts
        The forecast points found in the raw xml data.

    """
    xml = etree.fromstring(raw_xml)
    models = []
    for node in xml.xpath('/weatherdata/meta/model'):
        model = get_attributes(node)
        models.append(model)
    points = []
    for node in xml.xpath('/weatherdata/product/time'):
        point = {}
        point[node.tag] = get_attributes(node)
        for i in node:
            point[i.tag] = get_attributes(i)
            for j in i:
                point[j.tag] = get_attributes(j)
        points.append(point)
    return models, points


def get_temperature_forecast(points):
    """Get temperature information from forecast data.

    Parameters
    ----------
    points : list of dicts
        The forecast raw data.

    Returns
    -------
    temperature_forecast : dict of lists of dicts
        The temperature forecast grouped by the time resolution.

    """
    temperature = [i for i in points if 'temperature' in i]
    # The temperature data will have different resolution, we will
    # use the time difference to the previous point in order to
    # group the forecast into different resolutions:
    temperature_forecast = {}
    prev = None
    for i, forecast in enumerate(temperature):
        if i == 0:
            # We don't know yet about this point. It will be assumed to be in
            # the same group as the next point.
            prev = forecast
        else:
            timei = forecast['time']['from']
            timediff = int((timei - prev['time']['from']).total_seconds())
            if timediff not in temperature_forecast:
                temperature_forecast[timediff] = []
            if i == 1:
                temperature_forecast[timediff].append(prev)
            temperature_forecast[timediff].append(forecast)
        prev = forecast
    return temperature_forecast


def get_precipitation_forecast(points):
    """Get the precipitation forecast from forecast data.

    Parameters
    ----------
    points : list of dicts
        The forecast raw data.

    Returns
    -------
    precipitation_forecast : dict of list of dicts
        The precipitation forecast grouped by time resolution.

    """
    precipitation = [i for i in points if 'precipitation' in i]
    # The precipitation forecast have a time resolution based given
    # by its to and from values. We will first group by this.
    precipitation_forecast = {}
    for point in precipitation:
        timediff = int(
            (point['time']['to'] - point['time']['from']).total_seconds()
        )
        if timediff not in precipitation_forecast:
            precipitation_forecast[timediff] = []
        precipitation_forecast[timediff].append(point)
    return precipitation_forecast


def get_hourly(points, now, max_hours):
    """Get a hourly forecast from the given data points.

    Parameters
    ----------
    points : list of dicts
        The data points to consider.
    now : object like datetime.datetime
        The current time.
    max_hours : int
        The max length in the future we are looking for.

    """
    maxtime = datetime.timedelta(hours=max_hours)
    selected = []
    for point in points:
        if (point['time']['from'] - now) > maxtime:
            continue
        selected.append(point)
    return selected


def get_start_time(points, time_zero):
    """Get the first forecast given a time for the first observation.

    Parameters
    ----------
    points : list of dicts
        The data points to consider.
    time_zero : object like datetime.datetime
        The current time.

    Returns
    -------
    start : object like datetime.datetime
        The time for the first forecast point.

    """
    start = None
    prev = None
    for point in points:
        if prev is None:
            prev = point
            continue
        if prev['time']['from'] <= time_zero <= point['time']['from']:
            start = prev['time']['from']
            break
        prev = point
    return start


def get_data(points, start, selection):
    """Extract data from points given a starting time."""
    data = {
        'time': {'to': [], 'from': [], 'relative-seconds': []},
    }
    for point in points:
        rel_time = (point['time']['from'] - start).total_seconds()
        if rel_time < 0:
            continue
        data['time']['to'].append(point['time']['to'])
        data['time']['from'].append(point['time']['from'])
        data['time']['relative-seconds'].append(rel_time)
        for key, sub_keys in selection.items():
            if key not in point:
                continue
            if key not in data:
                data[key] = {}
            for sub_key in sub_keys:
                if sub_key not in point[key]:
                    continue
                if sub_key not in data[key]:
                    data[key][sub_key] = []
                data[key][sub_key].append(point[key][sub_key])
    return data


def add_precipitation_meta(data, place):
    """Add some interpretations of the precipitation data."""
    meta = {
        'name': place['name'],
        'lat': place['lat'],
        'lon': place['lon'],
    }
    values = np.array(data['precipitation']['value'])
    # When does it rain?
    meta['rain'] = [int(i) for i in np.where(values > 0.0)[0]]
    # How much will it rain?
    meta['amount'] = sum(values)
    # Will it rain at all:
    meta['will-it-rain'] = len(meta['rain']) > 0
    # When does it start/stop?
    start, stop = None, None
    if meta['will-it-rain']:
        start = data['time']['from'][meta['rain'][0]].strftime(TIME_OUT_FMT)
        stop = data['time']['to'][meta['rain'][-1]].strftime(TIME_OUT_FMT)
    meta['rain-starts'] = start
    meta['rain-stops'] = stop
    data['meta'] = meta


def read_xml_forecast(xml_file, now, place):
    """Parse a forecast from a xml file.

    Parameters
    ----------
    xml_file : string
        The xml file to read the forecast from.
    now : object like datetime.datetime
        The current time, will be used as a zero point for time info.
    name : dict
        Information about the location the forecast is for.

    """
    raw_xml = None
    with open(xml_file, 'r') as inputfile:
        raw_xml = inputfile.read()
    if raw_xml is None:
        pass
    _, points = parse_xml(raw_xml)
    temperature = get_temperature_forecast(points)
    precipitation = get_precipitation_forecast(points)

    # Get hourly forecast from now up to a time in the future:
    temperature_hour = get_hourly(temperature[3600], now, max_hours=25)
    start = get_start_time(temperature_hour, now)
    selection = {
        'temperature': {'units', 'value'},
    }

    precipitation_hour = get_hourly(precipitation[3600], now, max_hours=25)

    start = get_start_time(precipitation_hour, now)
    selection = {
        'precipitation': {'unit', 'value', 'minvalue', 'maxvalue'},
        'symbol': {'number'}
    }
    precipitation_data = get_data(precipitation_hour, start, selection)
    # Add precipitation meta data:
    add_precipitation_meta(precipitation_data, place)

    chart = plot_hourly_altair(
        temperature_hour,
        precipitation_hour,
        now,
        place['name']
    )

    if DEBUG:
        plot_temperature_forecast(temperature, now)
        plot_precipitation_forecast(precipitation, now)
        plot_hourly(temperature_hour, precipitation_hour, now)
        plt.show()
    return precipitation_data, chart


def get_times_and_values(points, key, time_zero):
    """Extract values from a key from the given data as function of time.

    Parameters
    ----------
    points : list of dicts
        The data points to consider.
    key : string
        The key to extract values from.
    time_zero : object like datetime.datetime
        The zero point for the time.

    Returns
    -------
    times : numpy.array of floats
        The times (in seconds) relative to the given zero point for the
        time.
    width : numpy.array of floats
        The width of the time intervals in the given data points.
    values : numpy.array of floats
        The values found in the given data points.

    """
    times = []
    width = []
    values = []
    times_from = []
    for point in points:
        times.append(
            (point['time']['from'] - time_zero).total_seconds()
        )
        width.append(
            (point['time']['to'] - point['time']['from']).total_seconds()
        )
        values.append(point[key]['value'])
        times_from.append(point['time']['from'])
    times = np.array(times)
    start = np.where(times >= 0)[0][0]
    return times, times_from, np.array(width), np.array(values), start


def plot_temperature_forecast(temperature, time_zero):
    """Make a simple plot of the temperature forecast."""
    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    for resolution, forecast in temperature.items():
        times, _, _, values, _ = get_times_and_values(
            forecast, 'temperature', time_zero
        )
        ax1.plot(times / 3600., values, marker='o',
                 label='Resolution: {}'.format(resolution))
    ax1.legend()


def plot_precipitation_forecast(precipitation, time_zero):
    """Make a simple plot of the precipitation forecast."""
    colors = get_cmap(name='tab10')(np.linspace(0, 1, 10))
    fig = plt.figure()
    ncol = 1 if len(precipitation) < 3 else 2
    nrow = len(precipitation) // 2
    grid = GridSpec(nrow, ncol)
    for i, (resolution, forecast) in enumerate(precipitation.items()):
        row, col = divmod(i, ncol)
        axi = fig.add_subplot(grid[row, col])
        times, _, width, values, _ = get_times_and_values(
            forecast, 'precipitation', time_zero
        )
        axi.bar(times / 3600, values, width=width/3600, align='edge',
                alpha=0.5, color=colors[i], edgecolor='#262626', linewidth=1,
                label='Resolution: {}'.format(resolution))
        axi.legend()


def plot_hourly(temperature, precipitation, time_zero):
    """Make a plot of hourly temperature and precipitation data."""
    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    times, _, _, values, _ = get_times_and_values(
        temperature, 'temperature', time_zero
    )
    ax1.plot(times / 3600, values)
    ax2 = ax1.twinx()
    times, _, width, values, _ = get_times_and_values(
        precipitation, 'precipitation', time_zero
    )
    ax2.bar(times / 3600, values, width=width/3600, align='edge',
            alpha=0.5, edgecolor='#262626', linewidth=1)


def plot_hourly_altair(temperature, precipitation, time_zero, name):
    """Make a plot of hourly temperature and precipitation data."""
    _, times_t, _, values_t, start = get_times_and_values(
        temperature, 'temperature', time_zero
    )
    source_t = pd.DataFrame(
        {
            'hours': times_t[start:],
            'temperature': values_t[start:],
        }
    )
    _, times_p, _, values_p, start = get_times_and_values(
        precipitation, 'precipitation', time_zero
    )
    source_p = pd.DataFrame(
        {
            'hours': times_p[start:],
            'rain': values_p[start:],
        }
    )
    line_t = alt.Chart(source_t).mark_line(size=3).encode(
        x=alt.X('hours:T'),
        y=alt.Y('temperature', title='Temperature (°C)'),
        color=alt.value("#FFAA00"),
    )
    bar_p = alt.Chart(source_p).mark_bar(size=15).encode(
        x=alt.X('hours:T', title='Time'),
        y=alt.Y('rain', title='Precipitation (mm)'),
    )
    chart = alt.layer(
        bar_p,
        line_t,
    ).resolve_scale(y='independent')
    chart.title = name
    return chart


def main():
    """Do some example things."""
    with open('places.json', 'r') as json_file:
        places = json.load(json_file)
    now = datetime.datetime(2019, 9, 4, 12, 22, 59, 855905)
    for place in places:
        xml_file = '{}.xml'.format(place['name'])
        print(xml_file)
        read_xml_forecast(xml_file, now, place)


if __name__ == '__main__':
    main()
