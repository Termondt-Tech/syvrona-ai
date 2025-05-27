# admin_routes.py
from flask import Blueprint, render_template, redirect, url_for, flash
from app.models import User
from app.auth import admin_required
from flask_login import login_required, current_user
from app import db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@login_required
@admin_required
def user_list():
    users = User.query.all()
    return render_template("admin/user_list.html", users=users)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You can't deactivate your own account.", "error")
        return redirect(url_for("admin.user_list"))

    user.is_active = not user.is_active
    db.session.commit()

    flash(
        f"User {user.email} is now {'active' if user.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.user_list"))
