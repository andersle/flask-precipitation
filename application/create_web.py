"""Create a website with the folium map and precipitation info."""
import datetime
import os
import pathlib
import jinja2
from normetapi import location_forecast
from frostapi import get_precipitation_observations
from read_xml import read_xml_forecast
from folium_map import create_the_map
from common import (
    read_json_file,
    write_json_file,
    FORECAST_DIR,
    FORECAST_FILE,
    CHART_DIR,
    CHART_FILE,
    set_up_directories,
    TIME_OUT_FMT,
    BUILD_DIR,
    write_text_to_file,
    MAP_FILE,
    TABLE_FILE,
    UPDATE_FILE
)


def create_table(forecast_files):
    """Gather data for rendering a table."""
    table_row = []
    for filei in forecast_files:
        data = read_json_file(filei)
        start = data['rain-starts']
        if start is None:
            start = ''
        row = {
            'name': data['name'],
            'amount': '{:4.2f}'.format(data['amount']),
            'rain_starts': start,
            'hours_with_rain': len(data['rain']),
            'lat': data['lat'],
            'lon': data['lon'],
            'url': '{}?lat={}&lon={}&zoom=14'.format(
                'map',
                data['lat'],
                data['lon'],
            ),
        }
        table_row.append(row)
    headers = (
        'Location',
        'Precipitation (mm)',
        'Start of rain',
        'Hours with rain'
    )
    table = {
        'headers': headers,
        'rows': table_row,
    }
    return table


def create_web(forecast_files, now):
    """Render the webpage."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('templates')
    )
    table = create_table(forecast_files)
    table['caption'] = 'Precipitation next 24 hours (updated: {}).'.format(
        now.strftime(TIME_OUT_FMT)
    )
    data = {
        'table': table,
        'update_time': now.strftime(TIME_OUT_FMT),
        'map_url': 'map',
    }
    render = env.get_template('table.html').render(data)
    write_text_to_file(render, TABLE_FILE)
    return render


def download_forecasts(places, now, update):
    """Download forecasts for the given places."""
    forecast_files = []
    for place in places:
        print('\nGetting forecast for "{}"'.format(place['name']))
        xml_file = FORECAST_DIR.joinpath('{}.xml'.format(place['name']))
        if update:
            print('Downloading updated forecast')
            data = location_forecast(place['lat'], place['lon'])
            write_text_to_file(data, xml_file)
        else:
            print('Using already downloaded forecast')
        print('Reading xml forecast from "{}"'.format(xml_file))
        precipitation_data, chart = read_xml_forecast(
            xml_file, now, place
        )

        json_forecast = FORECAST_DIR.joinpath(
            FORECAST_FILE.format(place['name'])
        )
        write_json_file(
            precipitation_data['meta'], json_forecast, pretty=False
        )

        chart_file = CHART_DIR.joinpath(
            CHART_FILE.format(place['name'])
        )
        write_json_file(chart.to_json(), chart_file, pretty=False)
        forecast_files.append(json_forecast)
    return forecast_files


def _check_time_for_update():
    """Check if we are to download new forecasts."""
    now = datetime.datetime.now()
    print('Current time: {}'.format(now.strftime(TIME_OUT_FMT)))
    if UPDATE_FILE.is_file():
        with open(UPDATE_FILE, 'r') as infile:
            last = datetime.datetime.strptime(infile.read(), TIME_OUT_FMT)
        print('Last update: {}'.format(last.strftime(TIME_OUT_FMT)))
        if (now - last).total_seconds() >= 3600:
            # More than 1 hour ago:
            return now, True
        if now.hour != last.hour:
            # We are in a different hour:
            return now, True
        return last, False
    return now, True


def create_web_site(places_file, client_id):
    """Download forecasts and create web-site."""
    set_up_directories()
    now, update = _check_time_for_update()
    print('Using update time: {}'.format(now.strftime(TIME_OUT_FMT)))
    print('Update forecasts is: {}'.format(update))
    if update:
        write_text_to_file(now.strftime(TIME_OUT_FMT), UPDATE_FILE)
    # Check if we need to update or not:
    exist = [i.is_file() for i in (TABLE_FILE, MAP_FILE)]
    if not update and all(exist):
        print('Update is not triggered and all files exist.')
        print('-> Reusing old files!')
        html = 'REUSING OLD TABLE'
        with open(TABLE_FILE, 'r') as infile:
            html = infile.read()
        return html
    # Download observations:
    print('\nGetting observations.')
    print('=====================')
    get_precipitation_observations(places_file, client_id, now, number=15)

    places = read_json_file(places_file)
    # Download forecasts:
    print('\nGetting forecasts.')
    print('==================')
    forecast_files = download_forecasts(places, now, update)
    print('\nCreating map.')
    print('=============')
    create_the_map(
        places_file,
        output=str(MAP_FILE),
        now=now.strftime(TIME_OUT_FMT)
    )
    print()
    print('\nCreating table.')
    print('===============')
    html = create_web(forecast_files, now)
    return html


if __name__ == '__main__':
    create_web_site('places.json', os.environ['FROST_CLIENT_ID'])
