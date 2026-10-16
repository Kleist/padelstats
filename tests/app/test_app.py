"""Tests for the match-entry web app."""

MATCH = {
    "played_on": "2026-10-09", "venue": "Ude",
    "a1": "Anders", "a2": "Bo", "b1": "Carsten", "b2": "Dennis",
    "s1a": "6", "s1b": "3", "s2a": "4", "s2b": "6", "s3a": "7", "s3b": "5",
}


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_healthz_db(client):
    resp = client.get("/healthz/db")
    assert resp.json() == {"status": "ok", "version": "dev", "matches": 0}


def text(resp):
    """Response body with whitespace collapsed (the stats template spreads set scores over lines)."""
    return " ".join(resp.text.split())


def test_index_is_the_stats_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "0 kampe spillet" in resp.text
    assert "Leaderboard" in resp.text
    assert 'href="/ny"' in resp.text
    assert "Log ud" not in resp.text


def test_new_match_requires_login(client):
    assert client.get("/ny", follow_redirects=False).headers["location"] == "/login"
    resp = client.post("/ny", data=MATCH, follow_redirects=False)
    assert resp.headers["location"] == "/login"
    assert client.get("/healthz/db").json()["matches"] == 0


def test_wrong_password(client):
    resp = client.post("/login", data={"password": "forkert"})
    assert resp.status_code == 401
    assert client.get("/ny", follow_redirects=False).status_code == 303


def test_login_ignores_surrounding_whitespace(client):
    resp = client.post("/login", data={"password": " hemmelig "}, follow_redirects=False)
    assert resp.headers["location"] == "/ny"


def test_failed_login_is_logged_without_password(client, caplog):
    client.post("/login", data={"password": "Hemmelig"})
    client.post("/login", data={"password": "forkert"})
    assert "wrong letter case" in caplog.text
    assert "7 chars submitted, 8 expected" in caplog.text
    assert "forkert" not in caplog.text


def test_login_logs_missing_admin_password(client, caplog, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD")
    assert client.post("/login", data={"password": "hemmelig"}).status_code == 401
    assert "ADMIN_PASSWORD is not set" in caplog.text


def test_create_match(logged_in):
    resp = logged_in.post("/ny", data=MATCH, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/?gemt=")

    page = text(logged_in.get(resp.headers["location"]))
    assert "Kampen er gemt" in page
    assert "Log ud" in page
    assert "1 kampe spillet" in page
    assert "Anders &amp; Bo" in page
    assert "6-3, 4-6, 7-5" in page
    assert '<td data-sort="2026-10-09">09/10/2026</td> <td>Ude</td>' in page
    assert logged_in.get("/healthz/db").json()["matches"] == 1


def test_stats_include_entered_matches(logged_in):
    logged_in.post("/ny", data=MATCH)
    logged_in.post("/ny", data={**MATCH, "played_on": "2026-10-10", "s3a": "2", "s3b": "6"})
    page = text(logged_in.get("/"))
    assert "2 kampe spillet" in page
    assert "Carsten &amp; Dennis" in page
    assert '"Anders": [{"date": "09/10/2026"' in page  # Elo history for the chart


def test_form_has_score_buttons_and_fallback_fields(logged_in):
    form = logged_in.get("/ny").text
    for side in ("a", "b"):
        for n in range(8):
            assert f'data-side="{side}" data-score="{n}"' in form
    assert 'name="s1a"' in form and 'name="s6b"' in form  # what the buttons fill in; used as-is without JavaScript


def test_form_has_player_buttons_and_fallback_fields(logged_in):
    logged_in.post("/ny", data=MATCH)
    form = logged_in.get("/ny").text
    for name in ("Anders", "Bo", "Carsten", "Dennis"):
        assert f'class="player-btn" data-name="{name}"' in form
    assert 'id="new-player"' in form  # type a new player as the last option
    for slot in ("a1", "a2", "b1", "b2"):
        assert f'name="{slot}"' in form  # the buttons fill these plain fields, in this order


def test_six_sets(logged_in):
    six = {f"s{i}{side}": v for i in range(1, 7) for side, v in (("a", "6"), ("b", "4"))}
    assert 'name="s6a"' in logged_in.get("/ny").text
    resp = logged_in.post("/ny", data={**MATCH, **six})
    assert "6-4, 6-4, 6-4, 6-4, 6-4, 6-4" in text(logged_in.get(resp.url))


def test_players_are_reused_case_insensitively(logged_in):
    logged_in.post("/ny", data=MATCH)
    logged_in.post("/ny", data={**MATCH, "a1": "anders"})
    form = logged_in.get("/ny").text
    assert form.count('<option value="Anders">') == 1
    assert '<option value="anders">' not in form


def test_players_with_danish_letters_are_reused(logged_in):
    # SQL lower() only folds ASCII in SQLite (and depends on collation in Postgres), so Ø must match in Python.
    for name in ("Øjvind", "øjvind", "ØJVIND"):
        resp = logged_in.post("/ny", data={**MATCH, "a1": name}, follow_redirects=False)
        assert resp.status_code == 303, name
    form = logged_in.get("/ny").text
    assert form.count('data-name="Øjvind"') + form.count('<option value="Øjvind">') >= 1
    assert "øjvind" not in form and "ØJVIND" not in form


def test_remembers_last_venue(logged_in):
    logged_in.post("/ny", data=MATCH)
    assert "<option selected>Ude</option>" in logged_in.get("/ny").text


def test_validation_errors(logged_in):
    bad = {**MATCH, "b2": "anders", "s1a": "9", "s2b": "", "venue": "Mars"}
    resp = logged_in.post("/ny", data=bad)
    assert resp.status_code == 422
    for msg in ("Samme spiller", "Sæt 1: scorer skal være mellem 0 og 7", "Sæt 2: udfyld begge", "Vælg inde eller ude"):
        assert msg in resp.text
    assert 'value="Carsten"' in resp.text  # entered values are kept
    assert logged_in.get("/healthz/db").json()["matches"] == 0


def test_player_names_are_restricted(logged_in):
    for name in ("<script>", "Bo\"", "a&b", "_x", "x" * 51):
        resp = logged_in.post("/ny", data={**MATCH, "a2": name})
        assert resp.status_code == 422, name
        assert "Spillernavne må kun" in resp.text
    resp = logged_in.post("/ny", data={**MATCH, "a2": "Søren B. O'Ærø-Hansen 2"}, follow_redirects=False)
    assert resp.status_code == 303


def test_requires_a_set(logged_in):
    data = {k: v for k, v in MATCH.items() if not k.startswith("s")}
    resp = logged_in.post("/ny", data=data)
    assert resp.status_code == 422
    assert "Indtast mindst ét sæt" in resp.text


def test_logout(logged_in):
    logged_in.post("/logout")
    assert logged_in.get("/ny", follow_redirects=False).status_code == 303


def _filter_data(client):
    """Three matches: 2025 inde (Anders, Bo, Carsten, Dennis), 2026 ude and 2026 inde (with Øjvind)."""
    client.post("/ny", data={**MATCH, "played_on": "2025-11-02", "venue": "Inde"})
    client.post("/ny", data={**MATCH, "played_on": "2026-01-15", "venue": "Ude"})
    client.post("/ny", data={**MATCH, "played_on": "2026-03-05", "venue": "Inde", "b2": "Øjvind"})


def test_filters_by_months_venue_and_players(logged_in):
    _filter_data(logged_in)
    assert "3 kampe spillet" in logged_in.get("/").text
    assert "1 kampe spillet" in logged_in.get("/?maaned=2026-01").text
    assert "2 kampe spillet" in logged_in.get("/?maaned=2025-11&maaned=2026-03").text  # any of the months
    assert "2 kampe spillet" in logged_in.get("/?sted=Inde").text
    assert "3 kampe spillet" in logged_in.get("/?sted=Inde&sted=Ude").text
    assert "1 kampe spillet" in logged_in.get("/?maaned=2026-01&maaned=2026-03&sted=Inde").text
    assert "1 kampe spillet" in logged_in.get("/?spiller=Øjvind").text
    assert "3 kampe spillet" in logged_in.get("/?spiller=Anders&spiller=Bo").text
    page = logged_in.get("/?spiller=Carsten&spiller=Dennis").text  # all chosen players must have played
    assert "2 kampe spillet" in page
    assert "Viser 2 af 3 kampe (hvor alle valgte spillere var med)" in page
    assert 'value="Carsten" checked' in page and 'value="Bo" checked' not in page


def test_filter_bar_shows_choices_and_ignores_unknown_values(logged_in):
    _filter_data(logged_in)
    page = logged_in.get("/?aar=2026&maaned=2024-13&sted=Mars&spiller=Nobody").text
    assert "3 kampe spillet" in page
    assert "Nulstil" not in page
    assert "Alle år" not in page and "Inde og ude" not in page
    months = [m for m in ("november 25", "januar 26", "marts 26") if m in page]
    assert months == ["november 25", "januar 26", "marts 26"]
    assert page.index("november 25") < page.index("januar 26") < page.index("marts 26")  # calendar order
    assert 'name="maaned" value="2026-01"' in page and 'name="sted" value="Inde"' in page
    names = [n for n in ("Anders", "Bo", "Carsten", "Dennis", "Øjvind") if f'value="{n}"' in page]
    assert names == ["Anders", "Bo", "Carsten", "Dennis", "Øjvind"]
    assert page.index('value="Dennis"') < page.index('value="Øjvind"')  # Danish order: Ø after Z


def test_filters_are_behind_a_toggle(logged_in):
    _filter_data(logged_in)
    page = logged_in.get("/").text
    assert '<details id="filter-box">' in page  # closed by default
    assert ">Filtre</summary>" in page and "Viser" not in page
    page = logged_in.get("/?maaned=2026-01&spiller=Anders&spiller=Bo").text
    assert ">Filtre (3)</summary>" in page
    assert "Viser 1 af 3 kampe" in page  # shown outside the toggle, so an active filter is visible


def test_month_label():
    from app.main import month_label
    assert month_label("2026-01") == "januar 26"
    assert month_label("2025-12") == "december 25"


def test_danish_sort_key():
    from app.main import danish_sort_key
    names = ["Åse", "Øjvind", "Zack", "Ærtebjerg", "anders", "Bo"]
    assert sorted(names, key=danish_sort_key) == ["anders", "Bo", "Zack", "Ærtebjerg", "Øjvind", "Åse"]
