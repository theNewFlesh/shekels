from typing import Any, Dict

from pathlib import Path
from pprint import pformat
import base64
import json
import os
import re
import traceback

from dash.exceptions import PreventUpdate
import dash
import flask
import jinja2
import jsoncomment as jsonc
import lunchbox.tools as lbt

import shekels.core.data_tools as sdt
import shekels.server.components as svc
# ------------------------------------------------------------------------------


def error_to_response(error):
    # type: (Exception) -> flask.Response
    '''
    Convenience function for formatting a given exception as a Flask Response.

    Args:
        error (Exception): Error to be formatted.

    Returns:
        flask.Response: Flask response.
    '''
    args = []  # type: Any
    for arg in error.args:
        if hasattr(arg, 'items'):
            for key, val in arg.items():
                args.append(pformat({key: pformat(val)}))
        else:
            args.append(str(arg))
    args = ['    ' + x for x in args]
    args = '\n'.join(args)
    klass = error.__class__.__name__
    msg = f'{klass}(\n{args}\n)'
    return flask.Response(
        response=json.dumps(dict(
            error=error.__class__.__name__,
            args=list(map(str, error.args)),
            message=msg,
            code=500,
            traceback=traceback.format_exc(),
        )),
        mimetype='application/json',
        status=500,
    )


def render_template(filename, parameters, directory='../../../templates'):
    # type: (str, Dict[str, Any], str) -> bytes
    '''
    Renders a jinja2 template given by filename with given parameters.

    Args:
        filename (str): Filename of template.
        parameters (dict): Dictionary of template parameters.
        directory (str or Path, optional): Templates directory.
            Default: '../../../templates'.

    Returns:
        bytes: HTML.
    '''
    directory = Path(directory).as_posix()

    # path to templates inside pip package
    tempdir = lbt.relative_path(__file__, '../templates').as_posix()

    # path to templates inside repo
    if 'REPO_ENV' in os.environ.keys():
        tempdir = lbt.relative_path(__file__, directory).as_posix()

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(tempdir),
        keep_trailing_newline=True
    )
    output = env.get_template(filename).render(parameters).encode('utf-8')
    return output


def parse_json_file_content(raw_content):
    # type: (bytes) -> Dict
    '''
    Parses JSON file content as supplied by HTML request.

    Args:
        raw_content (bytes): Raw JSON file content.

    Raises:
        ValueError: If header is invalid.
        JSONDecodeError: If JSON is invalid.

    Returns:
        dict: JSON content or reponse dict with error.
    '''
    header, content = raw_content.split(',')  # type: ignore
    temp = header.split('/')[-1].split(';')[0]  # type: ignore
    if temp != 'json':
        msg = f'File header is not JSON. Header: {header}.'  # type: ignore
        raise ValueError(msg)

    output = base64.b64decode(content).decode('utf-8')
    return jsonc.JsonComment().loads(output)


def update_store(client, store, endpoint, data=None):
    # type (FlaskClient, dict, str, Optional(dict)) -> None
    '''
    Updates store with data from given endpoint.
    Makes a post call to endpoint with client.

    Args:
        client (FlaskClient): Flask client instance.
        store (dict): Dash store.
        endpoint (str): API endpoint.
        data (dict, optional): Data to be provided to endpoint request.
    '''
    if data is not None:
        store[endpoint] = client.post(endpoint, json=json.dumps(data)).json
    else:
        store[endpoint] = client.post(endpoint).json


def store_key_is_valid(store, key):
    # type: (dict, str) -> bool
    '''
    Determines if given key is in store and does not have an error.

    Args:
        store (dict): Dash store.
        key (str): Store key.

    Raises:
        PreventUpdate: If key is not in store.

    Returns:
        bool: True if key exists and does not have an error key.
    '''
    if key not in store:
        raise PreventUpdate
    value = store[key]
    if isinstance(value, dict) and 'error' in value:
        return False
    return True


def solve_component_state(store, config=False):
    # type (dict) -> Optional(html.Div)
    '''
    Solves what component to return given the state of the given store.

    Returns a key value card component embedded with a relevant message or error
    if a required key is not found in the store, or it contain a dictionary with
    am "error" key in it. Those required keys are as follows:

        * /config
        * /api/initialize
        * /api/update
        * /api/search

    Args:
        store (dict): Dash store.
        config (bool, optional): Whether the component is for the config tab.
            Default: False.

    Returns:
        Div: Key value card if store values are not present or have errors,
            otherwise, none.
    '''
    states = [
        ['/config', None],
        ['/api/initialize', 'Please call init or update.'],
        ['/api/update', 'Please call update.'],
        ['/api/search', None],
    ]
    if config:
        states = states[:2]
        states[1][1] = None
    for key, message in states:
        value = store.get(key)
        if message is not None and value is None:
            return svc.get_key_value_table(
                {'action': message},
                id_='status',
                header='status',
            )
        elif isinstance(value, dict) and 'error' in value:
            return svc.get_key_value_table(
                value,
                id_='error',
                header='error',
                key_order=['error', 'message', 'code', 'traceback'],
            )
    return None


# EVENTS------------------------------------------------------------------------
def config_query_event(value, store, app):
    # type: (str, dict, dash.Dash) -> dict
    '''
    Updates given store given a config query.

    Args:
        value (str): SQL query.
        store (dict): Dash store.
        app (dash.Dash): Dash app.

    Returns:
        dict: Modified store.
    '''
    value = value or 'select * from config'
    value = re.sub('from config', 'from data', value, flags=re.I)
    key = '/config/query/count'
    store[key] = store.get(key, 0)
    # needed to block input which is called twice on page load
    if store[key] < 1:
        store[key] += 1
    else:
        try:
            store['/config'] = sdt.query_dict(app.api.config, value)
        except Exception as e:
            store['/config'] = error_to_response(e).json
    return store


def data_query_event(value, store, app):
    # type: (str, dict, dash.Dash) -> dict
    '''
    Updates given store given a data query.

    Args:
        value (str): SQL query.
        store (dict): Dash store.
        app (dash.Dash): Dash app.

    Returns:
        dict: Modified store.
    '''
    # needed to block input which is called twice on page load
    key = '/api/search/query/count'
    store[key] = store.get(key, 0)
    if store[key] < 1:
        store[key] += 1
    else:
        update_store(app.client, store, '/api/search', data={'query': value})
        store['/api/search/query'] = value
    return store


def init_event(value, store, app):
    # type: (str, dict, dash.Dash) -> dict
    '''
    Initializes app database.

    Args:
        value (str): Ignored.
        store (dict): Dash store.
        app (dash.Dash): Dash app.

    Returns:
        dict: Modified store.
    '''
    update_store(app.client, store, '/api/initialize', data=app.api.config)
    if 'error' in store['/api/initialize']:
        store['/config'] = store['/api/initialize']
    return store


def update_event(value, store, app):
    # type: (str, dict, dash.Dash) -> dict
    '''
    Update app database.

    Args:
        value (str): Ignored.
        store (dict): Dash store.
        app (dash.Dash): Dash app.

    Returns:
        dict: Modified store.
    '''
    update_store(app.client, store, '/api/update')
    update_store(
        app.client,
        store,
        '/api/search',
        data={'query': app.api.config['default_query']}
    )
    return store
