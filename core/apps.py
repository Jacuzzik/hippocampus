"""Connected apps: a catalogue of outside services, each read with the user's own key into a dashboard.

Every app is one entry of data: its address, how the key is sent, and a short list of numbers to read.
All requests are GET, over https, with a time limit and a size limit, and a redirect is never followed
(so a key cannot be carried to another host). Keys live in the system keychain; the few plain settings
an app needs (a shop address, a site name) live in apps.json in the app's storage.

The entries are written from each service's public API documents. An entry is only known to be right
once a real account has been connected to it.
"""

import base64
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from core import safe_write

SECONDS = 15
MAX_BYTES = 2_000_000
HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
Fetch = Callable[[str, dict[str, str]], tuple[int, bytes]]
Post = Callable[[str, dict[str, str]], tuple[int, bytes]]  # url, form fields -> status, body


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    example: str
    kind: str = "slug"  # "host": a domain name; "slug": a name or id
    optional: bool = False  # may be left empty


@dataclass(frozen=True)
class Metric:
    label: str
    path: str  # after the base address; may hold {field} names
    kind: (
        str  # "count": items in a list; "value": a number or word; "sum": a field added up; "cents"
    )
    pointer: str = ""  # where in the answer, as dotted keys and list positions
    field: str = ""  # for "sum": the key added up in each item


@dataclass(frozen=True)
class App:
    id: str
    name: str
    what: str
    base: str  # may hold {field} names
    auth: str  # "bearer", "header:<Name>", "prefix:<Word>", "raw", "query:<name>", "path", "basic"
    metrics: tuple[Metric, ...]
    fields: tuple[Field, ...] = ()
    key_help: str = "An API key or access token with read access."


def _m(label: str, path: str, kind: str, pointer: str = "", field: str = "") -> Metric:
    return Metric(label, path, kind, pointer, field)


SHOP = Field("shop", "Shop address", "my-shop.myshopify.com", "host")
APPS: tuple[App, ...] = (
    App(
        "shopify",
        "Shopify",
        "Orders, products and customers of your shop.",
        "https://{shop}/admin/api/2024-10",
        "header:X-Shopify-Access-Token",
        (
            _m("Orders", "/orders/count.json?status=any", "value", "count"),
            _m("Products", "/products/count.json", "value", "count"),
            _m("Customers", "/customers/count.json", "value", "count"),
        ),
        (
            SHOP,
            Field("client", "Client ID (Dev Dashboard app only)", "a1b2c3d4e5f6", optional=True),
        ),
        "For an app made in Shopify's Dev Dashboard: fill in its Client ID and paste its client"
        " secret as the key; Hippocampus asks Shopify for a 24-hour token when it reads. For an"
        " older custom app: leave Client ID empty and paste its Admin API access token (shpat_).",
    ),
    App(
        "builtbybit",
        "BuiltByBit",
        "Your resources and unread alerts.",
        "https://api.builtbybit.com/v1",
        "prefix:Private",
        (
            _m("Your resources", "/resources/owned", "count", "data"),
            _m("Unread alerts", "/alerts", "count", "data"),
            _m("Unread conversations", "/conversations", "count", "data"),
        ),
        (),
        "A private API token from your account's API settings.",
    ),
    App(
        "stripe",
        "Stripe",
        "Balance, charges and customers.",
        "https://api.stripe.com/v1",
        "bearer",
        (
            _m("Available balance", "/balance", "cents", "available.0.amount"),
            _m("Balance currency", "/balance", "value", "available.0.currency"),
            _m("Charges (newest 100)", "/charges?limit=100", "count", "data"),
            _m("Customers (newest 100)", "/customers?limit=100", "count", "data"),
        ),
        (),
        "A restricted key with read access. Never the secret key with write access.",
    ),
    App(
        "github",
        "GitHub account",
        "Repositories, followers and unread notifications.",
        "https://api.github.com",
        "bearer",
        (
            _m("Public repositories", "/user", "value", "public_repos"),
            _m("Followers", "/user", "value", "followers"),
            _m("Unread notifications", "/notifications?per_page=100", "count"),
        ),
        (),
        "A fine-grained personal access token with read access.",
    ),
    App(
        "gitlab",
        "GitLab",
        "Projects, merge requests assigned to you and to-do items.",
        "https://gitlab.com/api/v4",
        "header:PRIVATE-TOKEN",
        (
            _m("Your projects", "/projects?membership=true&per_page=100", "count"),
            _m(
                "Open merge requests for you",
                "/merge_requests?state=opened&scope=assigned_to_me&per_page=100",
                "count",
            ),
            _m("To-do items", "/todos?per_page=100", "count"),
        ),
        (),
        "A personal access token with the read_api scope.",
    ),
    App(
        "vercel",
        "Vercel",
        "Projects and recent deployments.",
        "https://api.vercel.com",
        "bearer",
        (
            _m("Projects", "/v9/projects?limit=100", "count", "projects"),
            _m("Deployments (newest 100)", "/v6/deployments?limit=100", "count", "deployments"),
        ),
    ),
    App(
        "netlify",
        "Netlify",
        "Your sites.",
        "https://api.netlify.com/api/v1",
        "bearer",
        (_m("Sites", "/sites?per_page=100", "count"),),
    ),
    App(
        "cloudflare",
        "Cloudflare",
        "Your zones (domains).",
        "https://api.cloudflare.com/client/v4",
        "bearer",
        (_m("Zones", "/zones?per_page=50", "value", "result_info.total_count"),),
        (),
        "An API token with Zone read permission.",
    ),
    App(
        "plausible",
        "Plausible",
        "Visitors and page views of one site, last 30 days.",
        "https://plausible.io/api/v1",
        "bearer",
        (
            _m(
                "Visitors, 30 days",
                "/stats/aggregate?site_id={site}&period=30d&metrics=visitors,pageviews",
                "value",
                "results.visitors.value",
            ),
            _m(
                "Page views, 30 days",
                "/stats/aggregate?site_id={site}&period=30d&metrics=visitors,pageviews",
                "value",
                "results.pageviews.value",
            ),
        ),
        (Field("site", "Site", "example.com", "host"),),
    ),
    App(
        "posthog",
        "PostHog",
        "Feature flags and dashboards of one project.",
        "https://app.posthog.com/api",
        "bearer",
        (
            _m("Feature flags", "/projects/{project}/feature_flags/?limit=1", "value", "count"),
            _m("Dashboards", "/projects/{project}/dashboards/?limit=1", "value", "count"),
        ),
        (Field("project", "Project id", "12345"),),
        "A personal API key with read access.",
    ),
    App(
        "sentry",
        "Sentry",
        "Projects and unresolved issues of one organisation.",
        "https://sentry.io/api/0",
        "bearer",
        (
            _m("Projects", "/organizations/{org}/projects/", "count"),
            _m(
                "Unresolved issues (newest 100)",
                "/organizations/{org}/issues/?query=is:unresolved&limit=100",
                "count",
            ),
        ),
        (Field("org", "Organisation", "my-team"),),
        "An auth token with read access.",
    ),
    App(
        "airtable",
        "Airtable",
        "The bases your token can read.",
        "https://api.airtable.com/v0",
        "bearer",
        (_m("Bases", "/meta/bases", "count", "bases"),),
        (),
        "A personal access token with the schema.bases:read scope.",
    ),
    App(
        "discord",
        "Discord bot",
        "The servers your bot is in.",
        "https://discord.com/api/v10",
        "prefix:Bot",
        (_m("Servers", "/users/@me/guilds", "count"),),
        (),
        "A bot token.",
    ),
    App(
        "telegram",
        "Telegram bot",
        "Your bot's name and waiting updates.",
        "https://api.telegram.org",
        "path",
        (
            _m("Bot", "/getMe", "value", "result.username"),
            _m("Waiting updates", "/getUpdates?limit=100", "count", "result"),
        ),
        (),
        "A bot token from BotFather.",
    ),
    App(
        "lemonsqueezy",
        "Lemon Squeezy",
        "Orders, subscriptions and customers.",
        "https://api.lemonsqueezy.com/v1",
        "bearer",
        (
            _m("Orders", "/orders?page[size]=1", "value", "meta.page.total"),
            _m("Subscriptions", "/subscriptions?page[size]=1", "value", "meta.page.total"),
            _m("Customers", "/customers?page[size]=1", "value", "meta.page.total"),
        ),
    ),
    App(
        "gumroad",
        "Gumroad",
        "Products and sales.",
        "https://api.gumroad.com/v2",
        "query:access_token",
        (
            _m("Products", "/products", "count", "products"),
            _m("Sales (newest page)", "/sales", "count", "sales"),
        ),
    ),
    App(
        "paddle",
        "Paddle",
        "Transactions, subscriptions and customers.",
        "https://api.paddle.com",
        "bearer",
        (
            _m("Transactions (newest 100)", "/transactions?per_page=100", "count", "data"),
            _m("Subscriptions (newest 100)", "/subscriptions?per_page=100", "count", "data"),
            _m("Customers (newest 100)", "/customers?per_page=100", "count", "data"),
        ),
    ),
    App(
        "woocommerce",
        "WooCommerce",
        "Orders and products of your shop.",
        "https://{shop}/wp-json/wc/v3",
        "basic",
        (
            _m("Orders (newest 100)", "/orders?per_page=100", "count"),
            _m("Products (newest 100)", "/products?per_page=100", "count"),
        ),
        (Field("shop", "Shop address", "shop.example.com", "host"),),
        "The consumer key and secret joined with a colon: ck_...:cs_... (read only).",
    ),
    App(
        "modrinth",
        "Modrinth",
        "Your projects and their downloads.",
        "https://api.modrinth.com/v2",
        "raw",
        (
            _m("Projects", "/user/{user}/projects", "count"),
            _m("Downloads", "/user/{user}/projects", "sum", "", "downloads"),
            _m("Followers", "/user/{user}/projects", "sum", "", "followers"),
        ),
        (Field("user", "User name", "my-name"),),
        "A personal access token with read access.",
    ),
    App(
        "polar",
        "Polar",
        "Orders, subscriptions and customers.",
        "https://api.polar.sh/v1",
        "bearer",
        (
            _m("Orders", "/orders/?limit=1", "value", "pagination.total_count"),
            _m("Subscriptions", "/subscriptions/?limit=1", "value", "pagination.total_count"),
            _m("Customers", "/customers/?limit=1", "value", "pagination.total_count"),
        ),
    ),
    App(
        "youtube",
        "YouTube channel",
        "Subscribers, views and videos of one channel.",
        "https://www.googleapis.com/youtube/v3",
        "query:key",
        (
            _m(
                "Subscribers",
                "/channels?part=statistics&id={channel}",
                "value",
                "items.0.statistics.subscriberCount",
            ),
            _m(
                "Views",
                "/channels?part=statistics&id={channel}",
                "value",
                "items.0.statistics.viewCount",
            ),
            _m(
                "Videos",
                "/channels?part=statistics&id={channel}",
                "value",
                "items.0.statistics.videoCount",
            ),
        ),
        (Field("channel", "Channel id", "UC..."),),
        "A YouTube Data API key.",
    ),
    App(
        "todoist",
        "Todoist",
        "Open tasks and projects.",
        "https://api.todoist.com/api/v1",
        "bearer",
        (
            _m("Open tasks (first page)", "/tasks?limit=200", "count", "results"),
            _m("Projects (first page)", "/projects?limit=200", "count", "results"),
        ),
    ),
)
BY_ID = {app.id: app for app in APPS}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None  # a redirect is an error here: the key must not travel to another address


def http_get(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers=headers, method="GET")  # noqa: S310 (https only, checked by the caller)
    try:
        with opener.open(request, timeout=SECONDS) as answer:
            return answer.status, answer.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        return error.code, b""


def http_post(url: str, form: dict[str, str]) -> tuple[int, bytes]:
    opener = urllib.request.build_opener(_NoRedirect)
    body = urlencode(form).encode()
    request = urllib.request.Request(  # noqa: S310 (https only, checked by the caller)
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with opener.open(request, timeout=SECONDS) as answer:
            return answer.status, answer.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        return error.code, b""


# (shop, client id) -> (token, monotonic time it stops being used). Kept in memory only.
_shopify_tokens: dict[tuple[str, str], tuple[str, float]] = {}


def shopify_token(shop: str, client: str, secret: str, post: Post = http_post) -> str:
    """A Dev Dashboard app's client ID and secret exchanged for a 24-hour Admin API token
    (Shopify's client credentials grant). Reused until 5 minutes before it runs out."""
    held = _shopify_tokens.get((shop, client))
    if held and held[1] > time.monotonic():
        return held[0]
    url = f"https://{shop}/admin/oauth/access_token"
    status, body = post(
        url, {"grant_type": "client_credentials", "client_id": client, "client_secret": secret}
    )
    if status != 200:
        raise ValueError(
            STATUS.get(status, f"Shopify answered {status} when asked for a token.")
            + " Check the Client ID and secret, that the app is installed on this shop, and that"
            " the shop is in the same Dev Dashboard organisation as the app."
        )
    found = json.loads(body.decode("utf-8"))
    token = found.get("access_token") if isinstance(found, dict) else None
    if not isinstance(token, str) or not token:
        raise ValueError("Shopify sent no token.")
    life = int(found.get("expires_in") or 86399)
    _shopify_tokens[(shop, client)] = (token, time.monotonic() + max(60, life - 300))
    return token


def app_for(app_id: object) -> App:
    if not isinstance(app_id, str) or app_id not in BY_ID:
        raise ValueError("That app is not in the catalogue.")
    return BY_ID[app_id]


def check_fields(app: App, fields: object) -> dict[str, str]:
    """The plain settings an app needs, each checked so it can only ever be part of an address."""
    given = fields if isinstance(fields, dict) else {}
    out = {}
    for field in app.fields:
        value = given.get(field.key)
        value = value.strip() if isinstance(value, str) else ""
        if field.kind == "host":
            value = value.lower().removeprefix("https://").strip("/")
        if field.optional and not value:
            continue  # left out, so an older setting with no such field reads the same
        pattern = HOST if field.kind == "host" else SLUG
        if not pattern.match(value) or len(value) > 200:
            raise ValueError(f"{field.label} must look like {field.example}.")
        out[field.key] = value
    return out


def load_fields(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
        return {
            str(app_id): {str(k): str(v) for k, v in fields.items()}
            for app_id, fields in found.items()
            if isinstance(fields, dict)
        }
    except (ValueError, AttributeError):
        return {}


def save_fields(path: Path, app_id: str, fields: dict[str, str] | None) -> None:
    saved = load_fields(path)
    if fields is None:
        saved.pop(app_id, None)
    else:
        saved[app_id] = fields
    safe_write.write_text(path, json.dumps(saved, indent=2))


def _request(
    app: App, metric: Metric, token: str, fields: dict[str, str]
) -> tuple[str, dict[str, str]]:
    safe = {key: quote(value, safe=".-_") for key, value in fields.items()}
    base = app.base.format(**fields)  # host fields are already checked as bare domain names
    path = metric.path.format(**safe)
    headers = {"Accept": "application/json", "User-Agent": "hippocampus-dashboard"}
    kind, _, name = app.auth.partition(":")
    if kind == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    elif kind == "prefix":
        headers["Authorization"] = f"{name} {token}"
    elif kind == "raw":
        headers["Authorization"] = token
    elif kind == "header":
        headers[name] = token
    elif kind == "basic":
        headers["Authorization"] = "Basic " + base64.b64encode(token.encode()).decode()
    elif kind == "query":
        path += ("&" if "?" in path else "?") + f"{name}={quote(token, safe='')}"
    elif kind == "path":
        base += f"/bot{quote(token, safe=':')}"
    url = base + path
    if not url.startswith("https://"):
        raise ValueError("Only https addresses are read.")
    return url, headers


def _at(found: object, pointer: str) -> object:
    for part in filter(None, pointer.split(".")):
        if isinstance(found, list):
            found = found[int(part)]
        elif isinstance(found, dict):
            found = found[part]
        else:
            raise KeyError(part)
    return found


def _value(metric: Metric, found: object) -> str:
    at = _at(found, metric.pointer)
    if metric.kind == "count":
        if not isinstance(at, list):
            raise TypeError("not a list")
        return str(len(at))
    if metric.kind == "sum":
        if not isinstance(at, list):
            raise TypeError("not a list")
        return str(sum(int(row.get(metric.field) or 0) for row in at if isinstance(row, dict)))
    if metric.kind == "cents":
        if isinstance(at, bool) or not isinstance(at, (int, float)):
            raise TypeError("not a number")
        return f"{at / 100:,.2f}"
    if isinstance(at, bool) or not isinstance(at, (str, int, float)):
        raise TypeError("not a number or a word")
    return str(at)


STATUS = {
    400: "The service did not accept the request (400). The key may be mistyped.",
    401: "The key was refused (401). Check it, or make a new one.",
    403: "The key may not read this (403). It needs read access.",
    404: "Not found (404). Check the settings of this app.",
    429: "The service asked to slow down (429). Try again later.",
}


def read(
    app: App, token: str, fields: dict[str, str], fetch: Fetch = http_get, post: Post = http_post
) -> list[dict[str, str]]:
    """One row per number. A number that cannot be read says why; the others are still shown."""
    if app.id == "shopify" and fields.get("client"):
        try:
            token = shopify_token(fields["shop"], fields["client"], token, post)
        except (OSError, ValueError) as error:
            reason = (
                str(error)
                if isinstance(error, ValueError)
                else f"Shopify did not answer ({type(error).__name__})."
            )
            return [{"label": m.label, "value": "", "error": reason} for m in app.metrics]
    answers: dict[str, tuple[int, bytes] | str] = {}
    rows = []
    for metric in app.metrics:
        row = {"label": metric.label, "value": "", "error": ""}
        try:
            url, headers = _request(app, metric, token, fields)
            if url not in answers:  # several numbers often come from one answer
                try:
                    answers[url] = fetch(url, headers)
                except OSError as error:
                    answers[url] = f"The service did not answer ({type(error).__name__})."
            answer = answers[url]
            if isinstance(answer, str):
                row["error"] = answer
            else:
                status, body = answer
                if status in (301, 302, 303, 307, 308):
                    row["error"] = "The service sent the request elsewhere, which is not followed."
                elif status != 200:
                    row["error"] = STATUS.get(status, f"The service answered {status}.")
                elif len(body) > MAX_BYTES:
                    row["error"] = "The answer was too large to read."
                else:
                    row["value"] = _value(metric, json.loads(body.decode("utf-8")))
        except (ValueError, KeyError, IndexError, TypeError):
            row["error"] = row["error"] or "The answer was not in the expected shape."
        rows.append(row)
    return rows


def catalogue(
    connected: Callable[[str], bool],
    hint: Callable[[str], str | None],
    fields: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    return [
        {
            "id": app.id,
            "name": app.name,
            "what": app.what,
            "key_help": app.key_help,
            "fields": [{"key": f.key, "label": f.label, "example": f.example} for f in app.fields],
            "saved": fields.get(app.id, {}),
            "connected": connected(app.id),
            "hint": hint(app.id),
            "numbers": [metric.label for metric in app.metrics],
        }
        for app in APPS
    ]
