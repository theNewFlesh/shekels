from typing import Any

from json import JSONDecodeError
import json

from pandasql import PandaSQLException
from schematics.exceptions import DataError
import flasgger as swg
import flask

from shekels.core.database import Database
import shekels.server.server_tools as svt
# ------------------------------------------------------------------------------


'''
Shekels REST API.
'''


API = flask.Blueprint('api', __name__, url_prefix='')
# TODO: Find a way to share database and config inside Flask instance without globals.
DATABASE = None
CONFIG = None


@API.route('/api')
def api():
    # type: () -> Any
    '''
    Route to Shekels API documentation.

    Returns:
        html: Flassger generated API page.
    '''
    # TODO: Test this with selenium.
    return flask.redirect(flask.url_for('flasgger.apidocs'))


@API.route('/api/initialize', methods=['POST'])
@swg.swag_from(dict(
    parameters=[
        dict(
            name='config',
            type='string',
            description='Database configuration as JSON string.',
            required=True,
            default='',
        )
    ],
    responses={
        200: dict(
            description='Shekels database successfully initialized.',
            content='application/json',
        ),
        400: dict(
            description='Invalid configuration.',
            example=dict(
                error='''
DataError(
    {'data_path': ValidationError([ErrorMessage("/foo.bar is not in a valid CSV file.", None)])}
)'''[1:],
                success=False,
            )
        )
    }
))
def initialize():
    # type: () -> flask.Response
    '''
    Initialize database with given config.

    Raises:
        RuntimeError: If config is invalid.

    Returns:
        Response: Flask Response instance.
    '''
    global DATABASE
    global CONFIG

    config = flask.request.get_json()
    msg = 'Please supply a config dictionary.'
    if config is None:
        raise RuntimeError(msg)

    config = json.loads(config)
    if not isinstance(config, dict):
        raise RuntimeError(msg)

    DATABASE = Database(config)
    CONFIG = DATABASE.config

    return flask.Response(
        response=json.dumps(dict(
            message='Database initialized.',
            config=CONFIG,
        )),
        mimetype='application/json'
    )


@API.route('/api/update', methods=['POST'])
@swg.swag_from(dict(
    parameters=[],
    responses={
        200: dict(
            description='Shekels database successfully updated.',
            content='application/json',
        ),
        500: dict(
            description='Internal server error.',
        )
    }
))
def update():
    # type: () -> flask.Response
    '''
    Update database.

    Raise:
        RuntimeError: If database has not been initialized.

    Returns:
        Response: Flask Response instance.
    '''
    global DATABASE
    global CONFIG

    if DATABASE is None:
        msg = 'Database not initialized. Please call initialize.'
        raise RuntimeError(msg)

    DATABASE.update()
    return flask.Response(
        response=json.dumps(dict(
            message='Database updated.',
            config=CONFIG,
        )),
        mimetype='application/json'
    )


@API.route('/api/read', methods=['GET', 'POST'])
@swg.swag_from(dict(
    responses={
        200: dict(
            description='Read all data from database.',
            content='application/json',
        ),
        500: dict(
            description='Internal server error.',
        )
    }
))
def read():
    # type: () -> flask.Response
    '''
    Read database.

    Raises:
        RuntimeError: If database has not been initilaized.
        RuntimeError: If database has not been updated.

    Returns:
        Response: Flask Response instance.
    '''
    global DATABASE
    global CONFIG

    if DATABASE is None:
        msg = 'Database not initialized. Please call initialize.'
        raise RuntimeError(msg)

    response = {}  # type: Any
    try:
        response = DATABASE.read()
    except Exception as error:
        if isinstance(error, RuntimeError):
            msg = 'Database not updated. Please call update.'
            raise RuntimeError(msg)
        return svt.error_to_response(error)

    response = {'response': response}
    return flask.Response(
        response=json.dumps(response),
        mimetype='application/json'
    )


@API.route('/api/search', methods=['POST'])
@swg.swag_from(dict(
    parameters=[
        dict(
            name='query',
            type='string',
            description='SQL query for searching database. Make sure to use "FROM data" in query.',
            required=True,
        )
    ],
    responses={
        200: dict(
            description='Returns a list of JSON compatible dictionaries, one per row.',
            content='application/json',
        ),
        500: dict(
            description='Internal server error.',
        )
    }
))
def search():
    # type: () -> flask.Response
    '''
    Search database with a given SQL query.

    Returns:
        Response: Flask Response instance.
    '''
    global DATABASE
    global CONFIG

    params = flask.request.get_json()
    params = json.loads(params)
    try:
        query = params['query']
    except KeyError:
        msg = 'Please supply valid search params in the form '
        msg += '{"query": SQL query}.'
        raise RuntimeError(msg)

    if DATABASE is None:
        msg = 'Database not initialized. Please call initialize.'
        raise RuntimeError(msg)

    if DATABASE.data is None:
        msg = 'Database not updated. Please call update.'
        raise RuntimeError(msg)

    response = DATABASE.search(query)  # type: Any
    response = {'response': response}
    return flask.Response(
        response=json.dumps(response),
        mimetype='application/json'
    )


# ERROR-HANDLERS----------------------------------------------------------------
@API.errorhandler(DataError)
def handle_data_error(error):
    # type: (DataError) -> flask.Response
    '''
    Handles errors raise by config validation.

    Args:
        error (DataError): Config validation error.

    Returns:
        Response: DataError response.
    '''
    return svt.error_to_response(error)


@API.errorhandler(RuntimeError)
def handle_runtime_error(error):
    # type: (RuntimeError) -> flask.Response
    '''
    Handles runtime errors.

    Args:
        error (RuntimeError): Runtime error.

    Returns:
        Response: RuntimeError response.
    '''
    return svt.error_to_response(error)


@API.errorhandler(JSONDecodeError)
def handle_json_decode_error(error):
    # type: (JSONDecodeError) -> flask.Response
    '''
    Handles JSON decode errors.

    Args:
        error (JSONDecodeError): JSON decode error.

    Returns:
        Response: JSONDecodeError response.
    '''
    return svt.error_to_response(error)


@API.errorhandler(PandaSQLException)
def handle_sql_error(error):
    # type: (PandaSQLException) -> flask.Response
    '''
    Handles SQL errors.

    Args:
        error (PandaSQLException): SQL error.

    Returns:
        Response: PandaSQLException response.
    '''
    return svt.error_to_response(error)
# ------------------------------------------------------------------------------


API.register_error_handler(500, handle_data_error)
