from selenium.webdriver.chrome.options import Options


def pytest_setup_options():
    options = Options()
    options.add_argument('--no-sandbox')
    # options.add_argument('--disable-gpu')
    # options.binary_location = "/usr/bin/chromium-browser"
    return options