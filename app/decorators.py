from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("You must be logged in to access this page.", "error")
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash("Admin access required.", "error")
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def require_active_subscription(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("You need to be logged in to access this feature.", "error")
            return redirect(url_for('auth.login'))
        # Allow admins full access regardless of subscription status
        if current_user.is_admin:
            return f(*args, **kwargs)
        if current_user.subscription_status != 'active':
            flash("You need an active subscription to access this feature.", "error")
            return redirect(url_for('main.profile'))
        return f(*args, **kwargs)
    return decorated_function
