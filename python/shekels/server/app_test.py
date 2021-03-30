import json
from pathlib import Path

import dash
import flask
import flask_caching
import lunchbox.tools as lbt

import shekels.server.api as api
import shekels.server.app as app
# ------------------------------------------------------------------------------


def write_config(root):
    config = dict(
        data_path='/foo/bar.baz',
        columns=['foo', 'bar'],
    )
    config_path = Path(root, 'config.json').as_posix()
    with open(config_path, 'w') as f:
        json.dump(config, f)
    return config_path


def test_get_app(dash_duo):
    result = app.get_app()
    dash_duo.start_server(result)
    assert isinstance(result, dash.Dash)
    assert result.api is api.API
    assert isinstance(result.client, flask.testing.FlaskClient)
    assert isinstance(result.cache, flask_caching.Cache)


def test_run():
    result = app.APP
    config_path = lbt.relative_path(
        __file__, '../../../resources/test_config.json'
    ).as_posix()
    app.run(result, config_path, debug=True, test=True)
    assert result.api.config_path == config_path
    assert isinstance(result.api.config, dict)
