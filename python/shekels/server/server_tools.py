from typing import Any, Dict, Optional

from copy import deepcopy
from pprint import pformat
import base64
import json
import os
import re
import traceback

from dash.exceptions import PreventUpdate
from schematics.exceptions import DataError
import dash
import flask
import jinja2
import jsoncomment as jsonc
import lunchbox.tools as lbt
import rolling_pin.blob_etl as rpb

import shekels.core.config as cfg
import shekels.core.data_tools as sdt
import shekels.server.components as svc
# ------------------------------------------------------------------------------


TEMPLATE_DIR = lbt.relative_path(__file__, '../templates').as_posix()
if 'REPO_ENV' in os.environ.keys():
    TEMPLATE_DIR = lbt.relative_path(__file__, '../../../templates').as_posix()


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


def render_template(filename, parameters, directory=None):
    # type: (str, Dict[str, Any], Optional[str]) -> bytes
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
    tempdir = TEMPLATE_DIR
    if directory is not None:
        tempdir = lbt.relative_path(__file__, directory).as_posix()

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(tempdir),
        keep_trailing_newline=True
    )
    output = env.get_template(filename).render(parameters).encode('utf-8')
    return output


def parse_json_file_content(raw_content):
    # type: (str) -> Dict
    '''
    Parses JSON file content as supplied by HTML request.

    Args:
        raw_content (str): Raw JSON file content.

    Raises:
        ValueError: If header is invalid.
        JSONDecodeError: If JSON is invalid.

    Returns:
        dict: JSON content or reponse dict with error.
    '''
    header, content = raw_content.split(',')
    temp = header.split('/')[-1].split(';')[0]  # type: str
    if temp != 'json':
        msg = f'File header is not JSON. Header: {header}.'
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

    Returns a key value table component embedded with a relevant message or error
    if a required key is not found in the store, or it contain a dictionary with
    am "error" key in it. Those required keys are as follows:

        * /config
        * /config/search
        * /api/initialize
        * /api/update
        * /api/search

    Args:
        store (dict): Dash store.
        config (bool, optional): Whether the component is for the config tab.
            Default: False.

    Returns:
        Div: Key value table if store values are not present or have errors,
            otherwise, none.
    '''
    states = [
        ['/config', None],
        ['/config/search', None],
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
    try:
        store['/config/search'] = sdt.query_dict(app.api.config, value)
    except Exception as e:
        store['/config/search'] = error_to_response(e).json
    return store


def config_edit_event(value, store, app):
    # type: (dict, dict, dash.Dash) -> dict
    '''
    Saves given edits to store.

    Args:
        value (dict): Config table.
        store (dict): Dash store.
        app (dash.Dash): Dash app.

    Returns:
        dict: Modified store.
    '''
    new = value['new']
    old_key = value['old']['key']
    config = store.get('/config', deepcopy(app.api.config))
    items = [
        ('/config', config),
        ('/config/search', store.get('/config/search', config)),
    ]
    for key, val in items:
        item = rpb.BlobETL(val).to_flat_dict()
        if old_key in item:
            del item[old_key]
            item[new['key']] = new['value']
        store[key] = rpb.BlobETL(item).to_dict()
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
    update_store(app.client, store, '/api/search', data={'query': value})
    store['/api/search/query'] = value
    return store


def init_event(value, store, app):
    # type: (None, dict, dash.Dash) -> dict
    '''
    Initializes app database.

    Args:
        value (None): Ignored.
        store (dict): Dash store.
        app (dash.Dash): Dash app.

    Returns:
        dict: Modified store.
    '''
    update_store(app.client, store, '/api/initialize', data=app.api.config)
    if 'error' in store['/api/initialize']:
        store['/config'] = store['/api/initialize']
    else:
        store['/config'] = deepcopy(app.api.config)
    return store


def update_event(value, store, app):
    # type: (None, dict, dash.Dash) -> dict
    '''
    Update app database.

    Args:
        value (None): Ignored.
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


def upload_event(value, store, app):
    # type: (str, dict, dash.Dash) -> dict
    '''
    Uploads config to app store.

    Args:
        value (str): Config.
        store (dict): Dash store.
        app (dash.Dash): Dash app.

    Returns:
        dict: Modified store.
    '''
    try:
        config = parse_json_file_content(value)
        config = cfg.Config(config)
        config.validate()
        store['/config'] = config.to_primitive()
        store['/config/search'] = deepcopy(store['/config'])
    except Exception as error:
        store['/config/search'] = error_to_response(error).json
    return store


def save_event(value, store, app):
    # type: (None, dict, dash.Dash) -> dict
    '''
    Save store config to app.api.config path.

    Args:
        value (None): Ignore me.
        store (dict): Dash store.
        app (dash.Dash): Dash app.

    Returns:
        dict: Modified store.
    '''
    try:
        config = store.get('/config', app.api.config)
        cfg.Config(config).validate()
        with open(app.api.config_path, 'w') as f:
            json.dump(config, f, indent=4, sort_keys=True)
    except (Exception, DataError) as error:
        store['/config'] = deepcopy(app.api.config)
        store['/config/search'] = error_to_response(error).json
    return store
