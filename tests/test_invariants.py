"""Pinned invariants: rules that hold everywhere under app/, checked by parsing it.

Each rule is a test that walks every module under app/ with `ast` and fails if the
forbidden shape appears anywhere, naming the file, line and offender. Each rule is
mapped to the defect it would have caught: §4 and §8 of the change record,
docs/syvrona-modernization-change-record-2026-11-06.md. Each checker also has a
self-test on a small snippet, so a checker that quietly stops matching anything fails.

The module imports nothing from the app, so it runs against any commit's tree: copy
it into that checkout's tests/ and run `python -m pytest --noconftest
tests/test_invariants.py` there. That is how §8's table of failing commits was made.
"""

import ast
import functools
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


@functools.cache
def _app_modules():
    """(repo-relative path, parsed tree) for every module under app/."""
    return tuple(
        (
            path.relative_to(ROOT).as_posix(),
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
        )
        for path in sorted(APP.rglob("*.py"))
    )


def _scan(check, skip=()):
    """Run `check` over app/, minus paths starting with `skip`; one line per hit."""
    return [
        f"{path}:{line} {what}"
        for rel, tree in _app_modules()
        if not rel.startswith(skip)
        for path, line, what in check(tree, rel)
    ]


def _callee(call):
    """The called name: `f` for `f(...)` and `x.y.f(...)`; None otherwise."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _is_none(node):
    return isinstance(node, ast.Constant) and node.value is None


# (a) Conversation ownership (D13, D1) ------------------------------------------------

OWNERSHIP_HELPER = "get_user_conversation"
ROUTE_DECORATORS = {"route", "get", "post", "put", "patch", "delete"}
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
SIGNED_SESSION = {"session", "flask.session"}


def _is_route(fn):
    return any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr in ROUTE_DECORATORS
        for d in fn.decorator_list
    )


def _is_conversation_id_key(node):
    return isinstance(node, ast.Constant) and node.value == "conversation_id"


def _takes_conversation_id(fn):
    """A `conversation_id` URL parameter, or that key read from anything but the
    signed session: `request.form["conversation_id"]`, `data.get("conversation_id")`."""
    args = fn.args
    if any(
        a.arg == "conversation_id"
        for a in args.posonlyargs + args.args + args.kwonlyargs
    ):
        return True
    for node in ast.walk(fn):
        holder = None
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            if _is_conversation_id_key(node.slice):
                holder = node.value
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"get", "getlist"}
            and node.args
            and _is_conversation_id_key(node.args[0])
        ):
            holder = node.func.value
        if holder is not None and ast.unparse(holder) not in SIGNED_SESSION:
            return True
    return False


def _checks_owner(fn):
    """Calls the helper with the logged-in user: `(..., current_user.id)`."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and _callee(node) == OWNERSHIP_HELPER:
            if len(node.args) > 1:
                user = node.args[1]
            else:
                user = next(
                    (k.value for k in node.keywords if k.arg == "user_id"), None
                )
            if user is not None and ast.unparse(user) == "current_user.id":
                return True
    return False


def _conversation_routes(tree, rel):
    for node in ast.walk(tree):
        if isinstance(node, FUNCTIONS) and _is_route(node):
            if _takes_conversation_id(node):
                yield rel, node.lineno, node.name, _checks_owner(node)


def _unchecked_conversation_routes(tree, rel):
    return [
        (path, line, name)
        for path, line, name, checked in _conversation_routes(tree, rel)
        if not checked
    ]


def test_every_route_that_takes_a_conversation_id_checks_its_owner():
    """D13 and D1. Commit 6d1e103 (2025-07-23) moved `/answer`'s conversation id
    from the signed session into the client's JSON and deleted the route that had
    checked its owner. Nothing replaced the check: until 2026-11-06 the code let any
    subscriber append to another user's conversation and have the model read its
    history back (D13). Every route that takes a conversation id, from its URL
    or from request data, calls `get_user_conversation(..., current_user.id)`: one
    helper, so not found and not yours are the same 404 (D1), and the check is a
    call this scan can see. Reads from `session` are out of scope: Flask signs it,
    and a route that copied a request value into it would be in scope itself."""
    assert _scan(_unchecked_conversation_routes) == []


def test_the_ownership_scan_still_sees_answer():
    """The rule above is only as good as its idea of "takes a conversation id". If
    `/answer` (D13's route) ever stops matching, the rule has gone blind to the one
    route that shipped without the check, and this fails."""
    names = {
        name
        for rel, tree in _app_modules()
        for _, _, name, _ in _conversation_routes(tree, rel)
    }
    assert "answer" in names


# (b) The model boundary --------------------------------------------------------------

SDK_MODULES = ("openai", "anthropic", "google.genai", "google.generativeai")


def _is_sdk(module):
    return any(module == m or module.startswith(m + ".") for m in SDK_MODULES)


def _sdk_imports(tree, rel):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            # `from google import genai` imports the module google.genai.
            modules = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        elif (
            isinstance(node, ast.Call)
            and _callee(node) in {"import_module", "__import__"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            modules = [node.args[0].value]
        else:
            continue
        hits = [m for m in modules if _is_sdk(m)]
        if hits:
            found.append((rel, node.lineno, hits[0]))
    return found


def test_no_provider_sdk_is_imported_outside_app_providers():
    """The model boundary (assessment §4.2; `CLAUDE.md`, "nothing else may call an
    SDK"). Every model call goes through `AIStreamer.chat` to an adapter in
    app/providers/, which is where history trimming (D5), the fallback chain (D21)
    and the single save-and-charge commit (D4) live. A route or service that
    imports an SDK can call a model around all three. app/handler/ kept its own
    OpenAI client, unused by then, until a1dd4da (2025-07-17)."""
    assert _scan(_sdk_imports, skip="app/providers/") == []


# (c) Outbound HTTP has a timeout (D11) -----------------------------------------------

HTTP_VERBS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}


def _untimed_requests(tree, rel):
    module_names, verb_names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module_names |= {
                a.asname or a.name for a in node.names if a.name == "requests"
            }
        elif isinstance(node, ast.ImportFrom) and node.module == "requests":
            verb_names |= {
                a.asname or a.name for a in node.names if a.name in HTTP_VERBS
            }
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_http = (
            isinstance(func, ast.Attribute)
            and func.attr in HTTP_VERBS
            and isinstance(func.value, ast.Name)
            and func.value.id in module_names
        ) or (isinstance(func, ast.Name) and func.id in verb_names)
        timed = any(k.arg == "timeout" and not _is_none(k.value) for k in node.keywords)
        if is_http and not timed:
            found.append((rel, node.lineno, ast.unparse(func)))
    return found


def test_every_requests_call_passes_a_timeout():
    """D11. `send_mailgun_message` called `requests.post` with no timeout, and
    `requests` sets none by default, so a Mailgun that accepted the connection and
    never answered held the signup request, and its gunicorn thread, with no limit.
    Every `requests.<verb>(...)` passes `timeout=`, and not `timeout=None`."""
    assert _scan(_untimed_requests) == []


# (d) No naive clock reads (D8) -------------------------------------------------------

#   method -> index of the positional `tz` argument; None means it takes no tz at all.
CLOCK_READS = {
    "now": 0,
    "fromtimestamp": 1,
    "utcnow": None,
    "utcfromtimestamp": None,
    "today": None,
}


def _naive_clock_reads(tree, rel):
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in CLOCK_READS:
            continue
        tz_at = CLOCK_READS[node.func.attr]
        if tz_at is None:
            tz = None
        elif len(node.args) > tz_at:
            tz = node.args[tz_at]
        else:
            tz = next((k.value for k in node.keywords if k.arg == "tz"), None)
        if tz is None or _is_none(tz):
            found.append((rel, node.lineno, ast.unparse(node)))
    return found


def test_no_naive_clock_reads():
    """D8. Signup and the Stripe webhook stored `datetime.now()` and
    `datetime.fromtimestamp(ts)`: the host's local wall time, in columns every other
    writer fills with UTC, so on any host not set to UTC those dates were off by its
    offset. Every clock read passes a tz. `utcnow`, `utcfromtimestamp` and `today` take
    none, so they are out entirely."""
    assert _scan(_naive_clock_reads) == []


# The checkers themselves -------------------------------------------------------------

SNIPPETS = {
    "ownership": (
        _unchecked_conversation_routes,
        """
@bp.route("/c/<int:conversation_id>")
def view_unchecked(conversation_id):  # flagged
    return get_conversation(conversation_id)

@bp.route("/answer", methods=["POST"])
def answer_d13():  # flagged
    data = request.get_json()
    return data.get("conversation_id")

@bp.post("/resume")
def resume_from_form():  # flagged
    return request.form["conversation_id"]

@bp.route("/c/<int:conversation_id>")
def checked_against_the_wrong_user(conversation_id):  # flagged
    return get_user_conversation(conversation_id, request.args["user"])

@bp.route("/c/<int:conversation_id>")
def checked(conversation_id):
    return get_user_conversation(conversation_id, current_user.id)

@bp.route("/answer", methods=["POST"])
def answer_fixed():
    cid = request.get_json()["conversation_id"]
    return get_user_conversation(cid, user_id=current_user.id)

@bp.route("/answer-2025-07")
def reads_only_the_session():
    return session.get("conversation_id")

def not_a_route(conversation_id):
    return conversation_id
""",
    ),
    "sdk": (
        _sdk_imports,
        """
import openai  # flagged
from anthropic import Anthropic  # flagged
from google import genai  # flagged
import google.genai.types as genai_types  # flagged
from google.generativeai import GenerativeModel  # flagged
client = importlib.import_module("openai")  # flagged
from app.providers.openai_provider import OpenAIProvider
from .providers import base_provider
import google.auth
import openapi_spec
""",
    ),
    "timeout": (
        _untimed_requests,
        """
import requests
import requests as http
from requests import get as fetch
requests.post(url, data=payload)  # flagged
http.get(url, timeout=None)  # flagged
fetch(url)  # flagged
requests.request("GET", url, **kwargs)  # flagged
requests.post(url, data=payload, timeout=(5, 15))
fetch(url, timeout=3)
session.get(url)
requests.RequestException
""",
    ),
    "clock": (
        _naive_clock_reads,
        """
datetime.now()  # flagged
datetime.fromtimestamp(ts)  # flagged
datetime.now(tz=None)  # flagged
datetime.utcnow()  # flagged
date.today()  # flagged
datetime.datetime.fromtimestamp(ts, None)  # flagged
datetime.now(tz=UTC)
datetime.now(timezone.utc)
datetime.fromtimestamp(ts, tz=UTC)
datetime.fromtimestamp(ts, UTC)
datetime.fromisoformat(value)
""",
    ),
}


@pytest.mark.parametrize("rule", SNIPPETS)
def test_each_checker_flags_exactly_the_marked_lines(rule):
    """A checker that matches nothing passes every scan above. Each one runs on a
    snippet holding the forbidden shapes, marked `# flagged`, and the allowed
    shapes next to them; it must report the marked lines and no others."""
    check, source = SNIPPETS[rule]
    marked = [
        number
        for number, text in enumerate(source.splitlines(), start=1)
        if text.endswith("# flagged")
    ]
    assert marked, "a snippet with nothing marked proves nothing"
    found = [line for _, line, *_ in check(ast.parse(source), "snippet.py")]
    assert sorted(found) == marked
