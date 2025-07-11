import logging


from flask import Blueprint, render_template
from flask_login import login_required
from app.decorators import require_active_subscription
from app.model_registry import DEFAULT_MODEL_KEY, MODEL_REGISTRY

knowledge_bp = Blueprint("knowledge_base", __name__, url_prefix="/knowledge_base")

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_ARTICLES = [
    {
        "slug": "models",
        "title": "Supported AI Models",
        "description": "Comparison of all AI models available in Syvrona, with context "
        "length, best uses, and provider details.",
        "url": "/knowledge_base/models",
    },
    {
        "slug": "prompt_builder",
        "title": "Prompt Builder (Chains & Prompts)",
        "description": "Build reusable AI prompts and multi-step chains for automation",
        "url": "/knowledge_base/prompt_builder",
    },
    {
        "slug": "tags",
        "title": "Tags & Tagging",
        "description": "Organize chats, prompts, and chains with powerful tags.",
        "url": "/knowledge_base/tags",
    },
    {
        "slug": "conversations",
        "title": "Managing Conversations",
        "description": "Resume, tag, search, and archive your AI conversations.",
        "url": "/knowledge_base/conversations",
    },
]


@knowledge_bp.route("/")
@login_required
@require_active_subscription
def index():
    """
    Knowledge Base Index Page
    """
    return render_template(
        "knowledge_base/index.html", articles=KNOWLEDGE_BASE_ARTICLES
    )


@knowledge_bp.route("/models")
@login_required
@require_active_subscription
def models():
    models = list(MODEL_REGISTRY.values())
    default_model = MODEL_REGISTRY[DEFAULT_MODEL_KEY]
    return render_template(
        "knowledge_base/models.html", models=models, default_model=default_model
    )


@knowledge_bp.route("/prompt_builder")
@login_required
@require_active_subscription
def prompt_builder():
    return render_template("knowledge_base/prompt_builder.html")


@knowledge_bp.route("/tags")
@login_required
@require_active_subscription
def tags():
    return render_template("knowledge_base/tags.html")


@knowledge_bp.route("/conversations")
@login_required
@require_active_subscription
def conversations():
    return render_template("knowledge_base/conversations.html")
