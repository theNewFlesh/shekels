from typing import Any, Dict

from pprint import pformat
import base64
import json
import os
import traceback

from dash.exceptions import PreventUpdate
import flask
import jinja2
import jsoncomment as jsonc
import lunchbox.tools as lbt
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


def render_template(filename, parameters):
    # type: (str, Dict[str, Any]) -> bytes
    '''
    Renders a jinja2 template given by filename with given parameters.

    Args:
        filename (str): Filename of template.
        parameters (dict): Dictionary of template parameters.

    Returns:
        bytes: HTML.
    '''
    # path to templates inside pip package
    tempdir = lbt.relative_path(__file__, '../templates').as_posix()

    # path to templates inside repo
    if 'REPO_ENV' in os.environ.keys():
        tempdir = lbt.relative_path(__file__, '../../../templates').as_posix()

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
