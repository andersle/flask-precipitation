# flask-precipitation

This is a small flask application that generates a web-site with
precipitation information for some selected places.

The precipitation information includes forecasted data and previous
observations which are displayed in table form and 
in a [folium](https://python-visualization.github.io/folium/) generated map.

Forecasted data is obtained using the
[MET Norway Weather API](https://api.met.no/) and observations are obtained
using the [Frost API](https://frost.met.no/index.html).

## Set up

In order to use the application, you will need to obtain a
client id for accessing the [Frost API](https://frost.met.no/auth/requestCredentials.html).

This client id will then have to be exported to the environment,
for instance,

```bash
export FROST_CLIENT_ID=your-client-id-for-frost
```

The places which information is obtained for are listed in the file
[places.json](https://raw.githubusercontent.com/andersle/flask-precipitation/master/application/places.json).

The application itself is executed in the usual fashion:

```bash
./app.py
```

## Example: Screenshots of generated html

![Data table](/examples/table.png)
![map1](/examples/map1.png)
![map2](/examples/map2.png)
