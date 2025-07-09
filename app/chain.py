from flask import Blueprint, render_template, redirect, request, session, url_for, flash
from flask_login import login_required, current_user

from app.decorators import require_active_subscription
from app.model_registry import DEFAULT_MODEL_KEY, MODEL_REGISTRY
from .models import PromptChain, Prompt, Tag, chain_prompts
from . import db

chain_bp = Blueprint("chain", __name__)


@chain_bp.route("/chains")
@login_required
@require_active_subscription
def chain_list():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    q = request.args.get("q", "").strip()

    query = PromptChain.query.filter_by(user_id=current_user.id)

    if q:
        query = query.filter(
            db.or_(
                PromptChain.title.ilike(f"%{q}%"),
                PromptChain.description.ilike(f"%{q}%"),
            )
        )

    chains = query.order_by(PromptChain.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template(
        "chain/list.html", chains=chains, search_query=q, active_tab="chains"
    )


@chain_bp.route("/chains/create", methods=["GET", "POST"])
@login_required
@require_active_subscription
def create_chain():
    user_prompts = (
        Prompt.query.filter_by(user_id=current_user.id)
        .order_by(Prompt.updated_at.desc())
        .all()
    )
    all_tags = Tag.query.order_by(Tag.name.asc()).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        is_public = bool(request.form.get("is_public"))
        prompt_ids = request.form.getlist("prompt_ids[]")  # List of prompt IDs in order
        tag_ids = request.form.getlist("tag_ids[]")  # List of tag IDs

        # Validate
        if not title or not prompt_ids:
            flash("Title and at least one prompt are required.", "danger")
            return render_template(
                "chain/create.html",
                title=title,
                description=description,
                user_prompts=user_prompts,
                all_tags=all_tags,
                selected_prompt_ids=prompt_ids,
                selected_tag_ids=tag_ids,
                active_tab="chains",
            )

        # Build and commit the chain
        chain = PromptChain(
            user_id=current_user.id,
            title=title,
            description=description,
            is_public=is_public,
        )
        db.session.add(chain)
        db.session.commit()  # Need chain.id

        # Insert prompt associations with explicit position
        for pos, prompt_id in enumerate(prompt_ids):
            db.session.execute(
                chain_prompts.insert().values(
                    chain_id=chain.id, prompt_id=int(prompt_id), position=pos
                )
            )
        db.session.commit()

        # Associate tags
        if tag_ids:
            tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
            chain.tags = tags
            db.session.commit()

        if request.form.get("submit") == "create_another":
            flash("Prompt chain created! You can add another below.", "success")
            return redirect(url_for("chain.create_chain"))
        else:
            flash("Prompt chain created!", "success")
            return redirect(url_for("chain.chain_list"))

    return render_template(
        "chain/create.html",
        user_prompts=user_prompts,
        all_tags=all_tags,
        selected_prompt_ids=[],
        selected_tag_ids=[],
        active_tab="chains",
    )


@chain_bp.route("/chains/<int:chain_id>/edit", methods=["GET", "POST"])
@login_required
@require_active_subscription
def edit_chain(chain_id):
    chain = PromptChain.query.filter_by(
        id=chain_id, user_id=current_user.id
    ).first_or_404()
    user_prompts = (
        Prompt.query.filter_by(user_id=current_user.id)
        .order_by(Prompt.updated_at.desc())
        .all()
    )
    all_tags = Tag.query.order_by(Tag.name.asc()).all()

    current_prompt_ids = [p.id for p in chain.prompts]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        is_public = bool(request.form.get("is_public"))
        prompt_ids = request.form.getlist("prompt_ids[]")
        tag_ids = request.form.getlist("tag_ids[]")

        if not title or not prompt_ids:
            flash("Title and at least one prompt are required.", "danger")
            return render_template(
                "chain/edit.html",
                chain=chain,
                user_prompts=user_prompts,
                all_tags=all_tags,
                selected_prompt_ids=prompt_ids,
                selected_tag_ids=tag_ids,
                active_tab="chains",
            )

        # Update basic fields
        chain.title = title
        chain.description = description
        chain.is_public = is_public

        # Remove all previous prompt associations
        db.session.execute(
            chain_prompts.delete().where(chain_prompts.c.chain_id == chain.id)
        )
        db.session.commit()

        # Insert the new prompt associations with position
        for pos, prompt_id in enumerate(prompt_ids):
            db.session.execute(
                chain_prompts.insert().values(
                    chain_id=chain.id, prompt_id=int(prompt_id), position=pos
                )
            )
        db.session.commit()

        # Update tags
        if tag_ids:
            tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
            chain.tags = tags
        else:
            chain.tags = []
        db.session.commit()

        flash("Prompt chain updated!", "success")
        return redirect(url_for("chain.chain_list"))

    return render_template(
        "chain/edit.html",
        chain=chain,
        user_prompts=user_prompts,
        all_tags=all_tags,
        selected_prompt_ids=current_prompt_ids,
        selected_tag_ids=[str(t.id) for t in chain.tags],
        active_tab="chains",
    )


@chain_bp.route("/chains/<int:chain_id>/delete", methods=["POST", "GET"])
@login_required
@require_active_subscription
def delete_chain(chain_id):
    chain = PromptChain.query.filter_by(
        id=chain_id, user_id=current_user.id
    ).first_or_404()
    if request.method == "POST":
        db.session.delete(chain)
        db.session.commit()
        flash("Prompt chain deleted.", "success")
        return redirect(url_for("chain.chain_list"))
    # Optional: show a confirm page or use JS modal
    return render_template(
        "chain/delete_confirm.html", chain=chain, active_tab="chains"
    )


@chain_bp.route("/chains/<int:chain_id>/run", methods=["GET", "POST"])
@login_required
@require_active_subscription
def run_chain(chain_id):
    chain = PromptChain.query.filter_by(
        id=chain_id, user_id=current_user.id
    ).first_or_404()

    # You might want to order or filter models here as needed
    available_models = [
        {"key": key, "provider": meta["provider"], "display_name": meta["display_name"]}
        for key, meta in MODEL_REGISTRY.items()
    ]

    # Sort or group by provider if you want
    available_models = sorted(available_models, key=lambda m: m["key"])

    if request.method == "POST":
        context = request.form.get("context", "").strip()
        model_key = request.form.get("model", DEFAULT_MODEL_KEY)
        prompt_bodies = [p.body for p in chain.prompts]
        # Combine all prompts, append context (if any)
        if context:
            prompt_bodies.append(context)
        # This could be a single string (joined), or just a list—depends how
        # your chat expects it
        session["prefilled_prompt"] = "\n\n".join(prompt_bodies)
        session["prefilled_model"] = model_key
        return redirect(url_for("chat.new_chat"))

    return render_template(
        "chain/run.html",
        chain=chain,
        active_tab="chains",
        available_models=available_models,
        default_model=DEFAULT_MODEL_KEY,
    )


@chain_bp.route("/chains/tags/<int:tag_id>")
@login_required
@require_active_subscription
def tagged_chains(tag_id):
    tag = Tag.query.filter_by(id=tag_id, user_id=current_user.id).first_or_404()
    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("q", "").strip()

    query = PromptChain.query.filter(
        PromptChain.user_id == current_user.id, PromptChain.tags.any(Tag.id == tag.id)
    )
    if search_query:
        query = query.filter(
            PromptChain.title.ilike(f"%{search_query}%")
            | PromptChain.description.ilike(f"%{search_query}%")
        )

    chains = query.order_by(PromptChain.updated_at.desc()).paginate(
        page=page, per_page=12
    )

    return render_template(
        "chain/tagged_chains.html",
        tag=tag,
        chains=chains,
        search_query=search_query,
        active_tab="chains",
    )
