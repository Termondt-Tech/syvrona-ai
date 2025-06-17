from flask import current_app


def is_feature_enabled(flag_name):
    return current_app.config["FEATURE_FLAGS"].get(flag_name, False)


def get_feature_config(flag_name, default=None):
    return current_app.config["FEATURE_FLAGS"].get(flag_name, default)
