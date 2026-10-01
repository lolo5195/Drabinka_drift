# NiceGUI's simulated-user fixture `user`: it runs main.py (the default
# `main_file`) without a browser. `nicegui.testing.plugin` is not used because
# it also loads the Selenium-based `screen` fixture, and Selenium is not installed.
pytest_plugins = ["nicegui.testing.user_plugin"]
