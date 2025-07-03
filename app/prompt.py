from flask import (
    Blueprint,
    abort,
    render_template,
    redirect,
    request,
    session,
    url_for,
    flash,
)
from flask_login import login_required, current_user

from app.decorators import require_active_subscription
from app.model_registry import DEFAULT_MODEL_KEY, MODEL_REGISTRY
from .models import Prompt
from . import db

prompt_bp = Blueprint("prompt", __name__)


@prompt_bp.route("/prompts")
@login_required
@require_active_subscription
def prompt_list():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    q = request.args.get("q", "").strip()

    query = Prompt.query.filter_by(user_id=current_user.id)

    if q:
        # Search title and description, case-insensitive
        query = query.filter(
            db.or_(Prompt.title.ilike(f"%{q}%"), Prompt.description.ilike(f"%{q}%"))
        )

    prompts = query.order_by(Prompt.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template("prompt/list.html", prompts=prompts, search_query=q)


@prompt_bp.route("/prompts/create", methods=["GET", "POST"])
@login_required
@require_active_subscription
def create_prompt():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        body = request.form.get("body", "").strip()

        if not title or not body:
            flash("Title and Prompt Body are required.", "danger")
            return render_template(
                "prompt/create.html", title=title, description=description, body=body
            )

        # You can extend this with tag support later!
        prompt = Prompt(
            user_id=current_user.id,
            title=title,
            description=description,
            body=body,
        )
        db.session.add(prompt)
        db.session.commit()
        flash("Prompt created successfully!", "success")
        return redirect(url_for("prompt.prompt_list"))

    return render_template("prompt/create.html")


@prompt_bp.route("/prompts/<int:prompt_id>/edit", methods=["GET", "POST"])
@login_required
@require_active_subscription
def edit_prompt(prompt_id):
    # Fetch the prompt
    prompt = Prompt.query.filter_by(
        id=prompt_id, user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        body = request.form.get("body", "").strip()

        if not title or not body:
            flash("Title and Prompt Body are required.", "danger")
            return render_template("prompt/edit.html", prompt=prompt)

        prompt.title = title
        prompt.description = description
        prompt.body = body
        db.session.commit()
        flash("Prompt updated successfully!", "success")
        return redirect(url_for("prompt.prompt_list"))

    return render_template("prompt/edit.html", prompt=prompt)


@prompt_bp.route("/prompts/<int:prompt_id>/delete", methods=["POST", "GET"])
@login_required
@require_active_subscription
def delete_prompt(prompt_id):
    prompt = Prompt.query.filter_by(
        id=prompt_id, user_id=current_user.id
    ).first_or_404()
    if request.method == "POST":
        db.session.delete(prompt)
        db.session.commit()
        flash("Prompt deleted.", "success")
        return redirect(url_for("prompt.prompt_list"))
    # For GET, show a confirmation page (optional; can also use JS confirm)
    return render_template("prompt/delete_confirm.html", prompt=prompt)


@prompt_bp.route("/prompts/<int:prompt_id>/use", methods=["GET", "POST"])
@login_required
@require_active_subscription
def use_prompt(prompt_id):
    prompt = Prompt.query.get_or_404(prompt_id)
    if prompt.user_id != current_user.id:
        abort(404)

    # You might want to order or filter models here as needed
    available_models = [
        {"key": key, "provider": meta["provider"], "display_name": meta["display_name"]}
        for key, meta in MODEL_REGISTRY.items()
    ]
    # Sort or group by provider if you want
    available_models = sorted(available_models, key=lambda m: m["key"])
    if request.method == "POST":
        prompt_body = request.form["body"]
        model_key = request.form.get("model", DEFAULT_MODEL_KEY)
        session["prefilled_prompt"] = prompt_body
        session["prefilled_model"] = model_key
        return redirect(url_for("chat.new_chat"))
    return render_template(
        "prompt/use.html",
        prompt=prompt,
        available_models=available_models,
        default_model=DEFAULT_MODEL_KEY,
    )
