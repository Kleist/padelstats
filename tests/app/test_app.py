"""Tests for the match-entry web app."""

from app.main import match_winner

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


def test_index_empty(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Ingen kampe endnu" in resp.text


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

    page = logged_in.get(resp.headers["location"]).text
    assert "Kampen er gemt" in page
    assert "Anders &amp; Bo" in page
    assert "6-3 4-6 7-5" in page
    assert "09/10/2026 · Ude" in page
    assert logged_in.get("/healthz/db").json()["matches"] == 1


def test_six_sets(logged_in):
    six = {f"s{i}{side}": v for i in range(1, 7) for side, v in (("a", "6"), ("b", "4"))}
    assert 'name="s6a"' in logged_in.get("/ny").text
    resp = logged_in.post("/ny", data={**MATCH, **six})
    assert "6-4 6-4 6-4 6-4 6-4 6-4" in logged_in.get(resp.url).text


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


def test_requires_a_set(logged_in):
    data = {k: v for k, v in MATCH.items() if not k.startswith("s")}
    resp = logged_in.post("/ny", data=data)
    assert resp.status_code == 422
    assert "Indtast mindst ét sæt" in resp.text


def test_logout(logged_in):
    logged_in.post("/logout")
    assert logged_in.get("/ny", follow_redirects=False).status_code == 303


def test_match_winner():
    assert match_winner([(6, 3), (6, 4)]) == "A"
    assert match_winner([(6, 3), (3, 6), (5, 7)]) == "B"
    assert match_winner([(6, 3), (3, 6)]) == "draw"
    assert match_winner([(6, 4), (4, 6), (4, 3)]) == "draw"
