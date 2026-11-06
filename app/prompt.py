from flask import (
    Blueprint,
    abort,
    render_template,
    redirect,
    request,
    url_for,
    flash,
)
from flask_login import login_required, current_user

from app.decorators import require_active_subscription
from app.model_registry import DEFAULT_MODEL_KEY, MODEL_REGISTRY
from .models import Prompt, Tag
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
    return render_template(
        "prompt/list.html", prompts=prompts, search_query=q, active_tab="prompts"
    )


@prompt_bp.route("/prompts/create", methods=["GET", "POST"])
@login_required
@require_active_subscription
def create_prompt():
    all_tags = Tag.query.order_by(Tag.name.asc()).all()
    selected_tag_ids = []

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        body = request.form.get("body", "").strip()
        tag_ids = request.form.getlist("tag_ids[]")
        selected_tag_ids = tag_ids  # For redisplay if error

        if not title or not body:
            flash("Title and Prompt Body are required.", "danger")
            return render_template(
                "prompt/create.html",
                title=title,
                description=description,
                body=body,
                all_tags=all_tags,
                selected_tag_ids=selected_tag_ids,
            )

        prompt = Prompt(
            user_id=current_user.id,
            title=title,
            description=description,
            body=body,
        )

        # Add selected tags
        if tag_ids:
            tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
            prompt.tags = tags

        db.session.add(prompt)
        db.session.commit()
        if request.form.get("submit") == "create_another":
            flash("Prompt created successfully! You can add another below.", "success")
            return redirect(url_for("prompt.create_prompt"))
        else:
            flash("Prompt created successfully!", "success")
            return redirect(url_for("prompt.prompt_list"))

    return render_template(
        "prompt/create.html",
        all_tags=all_tags,
        selected_tag_ids=selected_tag_ids,
        active_tab="prompts",
    )


@prompt_bp.route("/prompts/<int:prompt_id>/edit", methods=["GET", "POST"])
@login_required
@require_active_subscription
def edit_prompt(prompt_id):
    prompt = Prompt.query.filter_by(
        id=prompt_id, user_id=current_user.id
    ).first_or_404()
    all_tags = Tag.query.order_by(Tag.name.asc()).all()
    current_tag_ids = [str(t.id) for t in prompt.tags]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        body = request.form.get("body", "").strip()
        tag_ids = request.form.getlist("tag_ids[]")

        if not title or not body:
            flash("Title and Prompt Body are required.", "danger")
            return render_template(
                "prompt/edit.html",
                prompt=prompt,
                all_tags=all_tags,
                selected_tag_ids=tag_ids,
            )

        prompt.title = title
        prompt.description = description
        prompt.body = body

        # Update tags
        if tag_ids:
            tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
            prompt.tags = tags
        else:
            prompt.tags = []
        db.session.commit()

        flash("Prompt updated successfully!", "success")
        return redirect(url_for("prompt.prompt_list"))

    return render_template(
        "prompt/edit.html",
        prompt=prompt,
        all_tags=all_tags,
        selected_tag_ids=current_tag_ids,
        active_tab="prompts",
    )


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


@prompt_bp.route("/prompts/<int:prompt_id>/use", methods=["GET"])
@login_required
@require_active_subscription
def use_prompt(prompt_id):
    prompt = db.get_or_404(Prompt, prompt_id)
    if prompt.user_id != current_user.id:
        abort(404)

    # You might want to order or filter models here as needed
    available_models = [
        {"key": key, "provider": meta["provider"], "display_name": meta["display_name"]}
        for key, meta in MODEL_REGISTRY.items()
    ]
    # Sort or group by provider if you want
    available_models = sorted(available_models, key=lambda m: m["key"])
    return render_template(
        "prompt/use.html",
        prompt=prompt,
        available_models=available_models,
        default_model=DEFAULT_MODEL_KEY,
        active_tab="prompts",
    )


@prompt_bp.route("/prompts/tags/<int:tag_id>")
@login_required
@require_active_subscription
def tagged_prompts(tag_id):
    tag = Tag.query.filter_by(id=tag_id, user_id=current_user.id).first_or_404()
    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("q", "").strip()

    query = Prompt.query.filter(
        Prompt.user_id == current_user.id, Prompt.tags.any(Tag.id == tag.id)
    )
    if search_query:
        query = query.filter(
            Prompt.title.ilike(f"%{search_query}%")
            | Prompt.description.ilike(f"%{search_query}%")
        )

    prompts = query.order_by(Prompt.updated_at.desc()).paginate(page=page, per_page=12)

    return render_template(
        "prompt/tagged_prompts.html",
        tag=tag,
        prompts=prompts,
        search_query=search_query,
        active_tab="prompts",
    )
