from sys import stderr
from os import environ
from urlparse import urlparse
from StringIO import StringIO
from zipfile import ZipFile
from time import time

from flask import Flask
from flask import request
from flask import Response
from flask import render_template
from osgeo import ogr

from geo import get_intersecting_features
from util import json_encode, bool
from census import census_url

app = Flask(__name__)

def is_census_datasource(environ):
    '''
    '''
    return environ.get('GEO_DATASOURCE', None) == census_url

def get_datasource(environ):
    '''
    '''
    if is_census_datasource(environ):
        #
        # Use the value of the environment variable directly,
        # get_intersecting_features() knows about census_url.
        #
        datasource = environ['GEO_DATASOURCE']
    
    else:
        # Or just open datasource.shp with OGR.
        datasource = ogr.Open('datasource.shp')
    
    return datasource

@app.route('/')
def hello():
    host_port = urlparse(request.base_url).netloc.encode('utf-8')
    is_downloadable = not is_census_datasource(environ)
    
    return render_template('index.html', **locals())

@app.route('/.well-known/status')
def status():
    datasource = get_datasource(environ)
    
    status = {
        'status': 'ok' if bool(datasource) else 'Bad datasource: %s' % repr(datasource),
        'updated': int(time()),
        'dependencies': [],
        'resources': {}
        }

    body = json_encode(status)

    return Response(body, headers={'Content-type': 'application/json',
                                   'Access-Control-Allow-Origin': '*'})

@app.route("/areas")
def areas():
    lat = float(request.args['lat'])
    lon = float(request.args['lon'])

    include_geom = bool(request.args.get('include_geom', True))
    json_callback = request.args.get('callback', None)
    
    # This. Is. Python.
    ogr.UseExceptions()
    
    datasource = get_datasource(environ)
    point = ogr.Geometry(wkt='POINT(%f %f)' % (lon, lat))
    features = get_intersecting_features(datasource, point, include_geom)

    geojson = dict(type='FeatureCollection', features=features)
    body, mime = json_encode(geojson), 'application/json'
    
    if json_callback:
        body = '%s(%s);\n' % (json_callback, body)
        mime = 'text/javascript'
    
    return Response(body, headers={'Content-type': mime, 'Access-Control-Allow-Origin': '*'})

@app.errorhandler(404)
def error_404(error):
    return render_template('error.html', error=str(error))

@app.route('/datasource.zip')
def download_zip():
    if is_census_datasource(environ):
        error = "Can't download all of " + census_url
        return Response(render_template('error.html', error=error), status=404)
    
    buffer = StringIO()
    archive = ZipFile(buffer, 'w')
    archive.write('datasource.shp')
    archive.write('datasource.shx')
    archive.write('datasource.dbf')
    archive.write('datasource.prj')
    archive.close()
    
    return Response(buffer.getvalue(), headers={'Content-Type': 'application/zip'})
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)