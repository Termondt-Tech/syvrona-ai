import logging
from flask import (
    Blueprint,
    render_template,
)

from app.feature_flags import get_feature_config, is_feature_enabled

# Create a Blueprint named 'main'
main = Blueprint("main", __name__)

logger = logging.getLogger(__name__)

# Define the index route


@main.route("/", methods=["GET"])
def index():
    free_trial_enabled = is_feature_enabled("FREE_TRIAL_ENABLED")
    free_trial_days = get_feature_config("FREE_TRIAL_DAYS", 7)
    return render_template(
        "index.html",
        free_trial_enabled=free_trial_enabled,
        free_trial_days=free_trial_days
    )


@main.route("/privacy", methods=["GET"])
def privacy():
    return render_template("privacy.html")


@main.route("/terms", methods=["GET"])
def terms():
    return render_template("terms.html")
