# flask-precipitation

This is a small flask application that generates a web-site with
precipitation information for some selected places.

The precipitation information includes forecasted data and previous
observations.

## Set up

In order to use the application, you will need to obtain a
client id for accessing the [Frost API](https://frost.met.no/auth/requestCredentials.html).

This client id will then have to be exportet to the environment,
for instance

```bash
export FROST_CLIENT_ID=your-client-id-for-frost
```

The places to obtain information for are listed in the file
[places.json](https://raw.githubusercontent.com/andersle/flask-precipitation/master/application/places.json).

The application itself is executed in the usual fashion:

```bash
./app.py
```

## Example: Screenshots of generated html

![Data table](/examples/table.png)
![map1](/examples/map1.png)
![map2](/examples/map2.png)
