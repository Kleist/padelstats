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
