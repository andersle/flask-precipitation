#!/usr/bin/env python
"""A flask application for serving the map."""
import os
from flask import Flask
from create_web import create_web_site
from common import MAP_FILE, TABLE_FILE

app = Flask(__name__)


@app.route('/')
def index():
    """Create the web site."""
    html = create_web_site('places.json', os.environ['FROST_CLIENT_ID'])
    return html


@app.route('/map')
def get_map():
    """Get the map."""
    html = 'MAP NOT FOUND!'
    with open(MAP_FILE, 'r') as infile:
        html = infile.read()
    return html


@app.route('/table')
def get_table():
    """Get the table which is identical to the index for now."""
    html = 'TABLE NOT FOUND!'
    with open(TABLE_FILE, 'r') as infile:
        html = infile.read()
    return html


if __name__ == '__main__':
    app.run(debug=True)
