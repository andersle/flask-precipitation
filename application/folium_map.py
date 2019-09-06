# Copyright (c) 2019, Anders Lervik.
# Distributed under the MIT License. See LICENSE for more info.
"""Create a map using folium."""
import folium
from attribution import Attribution
from easybutton import EasyButton
from common import (
    read_json_file,
    STATION_FILE,
    CHART_DIR,
    CHART_FILE,
    FORECAST_DIR,
    FORECAST_FILE,
    write_text_to_file,
)


MET_URL = (
    'https://www.met.no/en/free-meteorological-data/Licensing-and-crediting'
)

MET_ATTRIBUTION = """'<a href="{}">Weather information</a> updated at: {}'"""


TILES = [
    {
        'name': 'topo4',
        'url': (
            'http://opencache.statkart.no/gatekeeper/gk/gk.open_gmaps?'
            'layers=topo4&zoom={z}&x={x}&y={y}'
        ),
        'attr': (
            '<a href="http://www.kartverket.no/">Kartverket</a>',
        ),
    },
    {
        'name': 'topo4graatone',
        'url': (
            'http://opencache.statkart.no/gatekeeper/gk/gk.open_gmaps?'
            'layers=topo4graatone&zoom={z}&x={x}&y={y}'
        ),
        'attr': (
            '<a href="http://www.kartverket.no/">Kartverket</a>',
        ),
    }
]


JS_PARAMS = """
var params = {};
    window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi, function(m, key, value) {
    params[key] = value;
});
"""


def monkey_patch_html(the_map):
    """Modify the html code to parse url parameters."""
    location = [i for i in the_map.location]
    the_map.location = ['LOCATION_LAT', 'LOCATION_LON']
    zoom = the_map.options['zoom']
    the_map.options['zoom'] = 'THE_ZOOM_LEVEL'
    root = the_map.get_root()
    html = root.render()
    patched = []
    for lines in html.split('\n'):
        the_line = lines
        if lines.find('var map_') != -1 and lines.find('= L.map(') != -1:
            patched.append(JS_PARAMS)
        if lines.find('LOCATION_LAT') != -1:
            the_line = the_line.replace(
                '"LOCATION_LAT"', 'params.lat || {}'.format(location[0])
            )
        if lines.find('LOCATION_LON') != -1:
            the_line = the_line.replace(
                '"LOCATION_LON"', 'params.lon || {}'.format(location[1])
            )
        if lines.find('THE_ZOOM_LEVEL') != -1:
            the_line = the_line.replace(
                '"THE_ZOOM_LEVEL"', 'params.zoom || {}'.format(zoom)
            )
        patched.append(the_line)
    the_map.location = location
    the_map.options['zoom'] = zoom
    return '\n'.join(patched)


def create_folium_map():
    """Create a folium map.

    Returns
    -------
    the_map : object like folium.folium.Map
        The map created here.

    """
    the_map = folium.Map(
        location=['63.446827', 10.421906],
        tiles=None,
        zoom_start=11,
        control_scale = True,
    )
    for tile in TILES:
        folium.TileLayer(
            tile['url'], attr=tile['attr'], name=tile['name']
        ).add_to(the_map)
    folium.TileLayer('openstreetmap').add_to(the_map)
    folium.TileLayer('stamenterrain').add_to(the_map)
    folium.LayerControl().add_to(the_map)
    return the_map


def add_places(the_map, places):
    """Add the given places to the given map."""
    markers = []
    for place in places:
        chart = read_json_file(
            CHART_DIR.joinpath(
                CHART_FILE.format(place['name'])
            )
        )
        info = read_json_file(
            FORECAST_DIR.joinpath(
                FORECAST_FILE.format(place['name'])
            )
        )
        color = 'red' if info['will-it-rain'] else 'green'
        popup = folium.Popup(max_width=500).add_child(
            folium.VegaLite(chart, width=500, height=250),
        )
        marker = folium.Marker(
            location=[place['lat'], place['lon']],
            popup=popup,
            icon=folium.Icon(icon='cloud', color=color)
        )
        marker.add_to(the_map)
        markers.append(marker)
    return markers


def load_station_information(filename='stations-observations.json'):
    """Load observations & other info for stations."""
    rain_fmt = '<li><font color="red">{}: <b>{:4.2f} mm</font></b></li>'
    no_rain_fmt = '<li>{}: <b>{:4.2f} mm</b></li>'
    stations = read_json_file(filename)
    for station in stations:
        text = [stations[station]['name']]
        text.append('<ul>')
        for time in sorted(stations[station]['values'], reverse=True):
            value = stations[station]['values'][time]
            if value > 0:
                text.append(rain_fmt.format(time, value))
            else:
                text.append(no_rain_fmt.format(time, value))
        text.append('</ul>Distance:<ul>')
        for distance_to, value in stations[station]['distance'].items():
            text.append(
                '<li>{}: {:4.2f} km</li>'.format(
                    distance_to,
                    value / 1000.,
                )
            )
        text.append('</ul>')
        stations[station]['text'] = ''.join(text)
    return stations


def add_stations(the_map, stations):
    """Add information about stations to the map."""
    markers = []
    for station in stations:
        marker = folium.Marker(
            location=[stations[station]['lat'], stations[station]['lon']],
            popup=folium.Popup(stations[station]['text'], max_width=250),
            icon=folium.Icon(icon='stats', color='gray')
        )
        marker.add_to(the_map)
        markers.append(marker)
    return markers


def create_the_map(places_file, output=None, now=None):
    """Create the map and write it to a file."""
    the_map = create_folium_map()
    places = read_json_file(places_file)
    add_places(the_map, places)
    stations = load_station_information(filename=STATION_FILE)
    add_stations(the_map, stations)
    if now is not None:
        the_map.add_child(
            Attribution(MET_ATTRIBUTION.format(MET_URL, now))
        )
    the_map.add_child(EasyButton('glyphicon glyphicon-list-alt', '/'))
    html = monkey_patch_html(the_map)
    if output is not None:
        write_text_to_file(html, output)
        the_map.save('{}.bak'.format(output))
    return the_map


def main():
    """Read input files and create the map."""
    create_the_map('places.json', output='map.html')


if __name__ == '__main__':
    main()
