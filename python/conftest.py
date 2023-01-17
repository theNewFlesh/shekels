import logging

from selenium.webdriver.chrome.options import Options
import lunchbox.tools as lbt
import pytest

import shekels.server.app as app
# ------------------------------------------------------------------------------


def pytest_setup_options():
    '''
    Configures Chrome webdriver.
    '''
    options = Options()
    options.add_argument('--no-sandbox')
    return options


@pytest.fixture(scope='function')
def run_app():
    '''
    Pytest fixture used to run shekels Dash app.
    Sets config_path to resources/test_config.json.
    '''
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    config = lbt \
        .relative_path(__file__, '../resources/test_config.json').as_posix()
    app.run(app.APP, config, debug=False, test=True)
    yield app.APP, app.APP.client
