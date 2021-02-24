from typing import Any, Dict

import base64
import json
import os
import traceback

import flask
import jinja2
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
    args = ['    ' + str(x) for x in error.args]  # type: Any
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
    return json.loads(output)
