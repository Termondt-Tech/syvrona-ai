# admin_routes.py
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models import User
from app.decorators import admin_required
from flask_login import login_required, current_user
from app import db

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route("/users")
@login_required
@admin_required
def user_list():
    users = User.query.all()
    return render_template("admin/user_list.html", users=users)


@admin.route("/users/<int:user_id>/toggle-active", methods=["POST"])
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
        f"User {user.email} is now {'active' if user.is_active else 'inactive'}.",
        "success",
    )
    return redirect(url_for("admin.user_list"))


# --- New: User Detail Route ---
@admin.route("/user/<int:user_id>", methods=["GET", "POST"])
def user_detail(user_id):

    PRICE_LABELS = {
        os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY"): "Pro Monthly ($9.99/mo)",
        os.getenv("STRIPE_PRICE_ID_PRO_YEARLY"): "Pro Yearly ($99/year)",
    }

    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        if "deactivate" in request.form:
            if user.id == current_user.id:
                flash("You can't deactivate your own account.", "error")
            else:
                user.is_active = not user.is_active
                db.session.commit()
                flash(
                    f"User {'deactivated' if not user.is_active else 'activated'} successfully.",
                    "success",
                )
        elif "delete" in request.form:
            if user.id == current_user.id:
                flash("You can't delete your own account.", "error")
            else:
                db.session.delete(user)
                db.session.commit()
                flash("User deleted successfully.", "success")
                return redirect(url_for("admin.user_list"))

    return render_template("admin/user_view.html", user=user, price_labels=PRICE_LABELS)
