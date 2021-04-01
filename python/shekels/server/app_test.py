from pathlib import Path
import json
import time

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


def test_stylesheet(dash_duo, run_app):
    test_app, client = run_app
    dash_duo.start_server(test_app)
    result = client.get('/stylesheet/style.css').data.decode('utf-8')
    assert 'static/style.css' in result


# TABS-NO-INIT------------------------------------------------------------------
def test_on_get_tab_data_no_init(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'plots-content'

    dash_duo.find_elements('#tabs .tab')[2].click()
    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'table-content'

    result = dash_duo.find_element('#table-content div')
    assert result.get_property('id') == 'error'


def test_on_get_tab_plots_no_init(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'plots-content'

    dash_duo.find_elements('#tabs .tab')[2].click()
    dash_duo.find_elements('#tabs .tab')[1].click()
    time.sleep(0.04)
    result = dash_duo.find_element('#plots-content > div')
    assert result.get_property('id') == 'error'


def test_on_get_tab_config_no_init(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'plots-content'

    dash_duo.find_elements('#tabs .tab')[3].click()
    dash_duo.wait_for_element('#config-content > div')
    # dash_duo.take_snapshot('test_on_get_tab_config_no_init-before')
    result = dash_duo.find_element('#config-content > div')
    assert result.get_property('id') == 'key-value-table-container'
