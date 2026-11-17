"""Connected apps: a catalogue of outside services read with the user's own key, GET only."""

import json
from pathlib import Path

import pytest

from core import apps


def _fetch(answers: dict[str, object], seen: list[tuple[str, dict[str, str]]] | None = None):
    def fetch(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        if seen is not None:
            seen.append((url, headers))
        for part, answer in answers.items():
            if part in url:
                if isinstance(answer, int):
                    return answer, b""
                return 200, json.dumps(answer).encode()
        return 404, b""

    return fetch


def test_the_catalogue_has_22_apps_each_with_https_and_at_least_one_number() -> None:
    assert len(apps.APPS) == 22
    assert len(apps.BY_ID) == 22
    for app in apps.APPS:
        assert app.base.startswith("https://"), app.id
        assert app.metrics, app.id
        assert app.auth.partition(":")[0] in (
            "bearer",
            "header",
            "prefix",
            "raw",
            "query",
            "path",
            "basic",
        ), app.id
        named = {f.key for f in app.fields}
        for text in (app.base, *(m.path for m in app.metrics)):
            for used in __import__("re").findall(r"{(\w+)}", text):
                assert used in named, f"{app.id} uses {{{used}}} without a field"


def test_shopify_numbers_are_read_with_the_token_header_from_the_shop_address() -> None:
    seen: list[tuple[str, dict[str, str]]] = []
    fetch = _fetch(
        {
            "/orders/count": {"count": 12},
            "/products/count": {"count": 40},
            "/customers/count": {"count": 9},
        },
        seen,
    )
    rows = apps.read(apps.BY_ID["shopify"], "shpat_x", {"shop": "my-shop.myshopify.com"}, fetch)
    assert [(row["label"], row["value"]) for row in rows] == [
        ("Orders", "12"),
        ("Products", "40"),
        ("Customers", "9"),
    ]
    assert (
        seen[0][0] == "https://my-shop.myshopify.com/admin/api/2024-10/orders/count.json?status=any"
    )
    assert seen[0][1]["X-Shopify-Access-Token"] == "shpat_x"
    assert "Authorization" not in seen[0][1]


def test_each_way_of_sending_a_key_puts_it_in_the_right_place() -> None:
    seen: list[tuple[str, dict[str, str]]] = []
    everything = _fetch({"": {"data": [], "result": [], "products": [], "sales": []}}, seen)
    apps.read(apps.BY_ID["builtbybit"], "tok", {}, everything)
    assert seen[-1][1]["Authorization"] == "Private tok"
    apps.read(apps.BY_ID["stripe"], "rk_x", {}, everything)
    assert seen[-1][1]["Authorization"] == "Bearer rk_x"
    apps.read(apps.BY_ID["gumroad"], "a b", {}, everything)
    assert seen[-1][0].endswith("/sales?access_token=a%20b")
    apps.read(apps.BY_ID["telegram"], "12:ab", {}, everything)
    assert seen[-1][0] == "https://api.telegram.org/bot12:ab/getUpdates?limit=100"
    apps.read(apps.BY_ID["woocommerce"], "ck:cs", {"shop": "shop.example.com"}, everything)
    assert seen[-1][1]["Authorization"] == "Basic Y2s6Y3M="
    apps.read(apps.BY_ID["modrinth"], "mrp", {"user": "me"}, everything)
    assert seen[-1][1]["Authorization"] == "mrp"


def test_counts_sums_cents_and_values_are_read_from_the_answer() -> None:
    stripe = apps.read(
        apps.BY_ID["stripe"],
        "k",
        {},
        _fetch(
            {
                "/balance": {"available": [{"amount": 123456, "currency": "usd"}]},
                "/charges": {"data": [1, 2]},
                "/customers": {"data": []},
            }
        ),
    )
    assert [row["value"] for row in stripe] == ["1,234.56", "usd", "2", "0"]
    modrinth = apps.read(
        apps.BY_ID["modrinth"],
        "k",
        {"user": "me"},
        _fetch(
            {"/projects": [{"downloads": 10, "followers": 2}, {"downloads": 5, "followers": 1}]}
        ),
    )
    assert [row["value"] for row in modrinth] == ["2", "15", "3"]


def test_one_answer_is_fetched_once_and_a_failed_number_does_not_hide_the_others() -> None:
    seen: list[tuple[str, dict[str, str]]] = []
    rows = apps.read(
        apps.BY_ID["github"],
        "k",
        {},
        _fetch({"/user": {"public_repos": 4, "followers": 7}, "/notifications": 401}, seen),
    )
    assert [row["value"] for row in rows] == ["4", "7", ""]
    assert "refused (401)" in rows[2]["error"]
    assert len(seen) == 2  # /user once for two numbers, /notifications once


def test_a_redirect_a_strange_shape_a_dead_network_and_a_huge_answer_each_say_why() -> None:
    app = apps.BY_ID["netlify"]
    assert "not followed" in apps.read(app, "k", {}, _fetch({"/sites": 302}))[0]["error"]
    assert (
        "expected shape"
        in apps.read(app, "k", {}, _fetch({"/sites": {"not": "a list"}}))[0]["error"]
    )

    def dead(_url: str, _headers: dict[str, str]) -> tuple[int, bytes]:
        raise OSError("no route")

    assert "did not answer" in apps.read(app, "k", {}, dead)[0]["error"]

    def huge(_url: str, _headers: dict[str, str]) -> tuple[int, bytes]:
        return 200, b"[" + b"1," * apps.MAX_BYTES + b"1]"

    assert "too large" in apps.read(app, "k", {}, huge)[0]["error"]


@pytest.mark.parametrize(
    "bad",
    [
        "evil.com/path",
        "evil.com?x=1",
        "a b.com",
        "user@evil.com",
        "evil.com:8080",
        "",
        "localhost",
        "x" * 300 + ".com",
        None,
    ],
)
def test_a_shop_address_must_be_a_bare_domain_name(bad: object) -> None:
    with pytest.raises(ValueError, match="must look like"):
        apps.check_fields(apps.BY_ID["shopify"], {"shop": bad})


def test_fields_are_tidied_checked_and_kept_in_a_file(tmp_path: Path) -> None:
    app = apps.BY_ID["shopify"]
    assert apps.check_fields(app, {"shop": " https://My-Shop.myshopify.com/ "}) == {
        "shop": "my-shop.myshopify.com"
    }
    with pytest.raises(ValueError, match="must look like"):
        apps.check_fields(apps.BY_ID["posthog"], {"project": "1/../2"})
    assert apps.check_fields(apps.BY_ID["stripe"], None) == {}
    path = tmp_path / "apps.json"
    apps.save_fields(path, "shopify", {"shop": "a.myshopify.com"})
    assert apps.load_fields(path) == {"shopify": {"shop": "a.myshopify.com"}}
    apps.save_fields(path, "shopify", None)
    assert apps.load_fields(path) == {}
    path.write_text("junk", encoding="utf-8")
    assert apps.load_fields(path) == {}
    with pytest.raises(ValueError, match="not in the catalogue"):
        apps.app_for("nope")


def test_the_catalogue_rows_never_carry_a_key() -> None:
    rows = apps.catalogue(
        lambda app_id: app_id == "stripe", lambda _id: "9xyz", {"shopify": {"shop": "a.b"}}
    )
    stripe = next(row for row in rows if row["id"] == "stripe")
    assert (stripe["connected"], stripe["hint"]) == (True, "9xyz")
    assert next(row for row in rows if row["id"] == "shopify")["saved"] == {"shop": "a.b"}
    assert all("key" not in row and "token" not in row for row in rows)
