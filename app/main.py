"""Padel stats web app: lets logged-in players enter match results from their phone."""

import hmac
import os
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.db import get_session
from app.models import Match, MatchSet, Player

VERSION = os.environ.get("GIT_SHA", "dev")
VENUES = ["Inde", "Ude"]
MAX_SETS = 3
ONE_YEAR = 365 * 24 * 3600

app = FastAPI(title="Padel Stats", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-insecure-secret"),
    max_age=ONE_YEAR,
    https_only=os.environ.get("COOKIE_SECURE", "1") == "1",
    same_site="lax",
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["version"] = VERSION


def is_set_won(winner_score, loser_score):
    return winner_score == 7 or (winner_score == 6 and loser_score <= 4)


def match_winner(sets):
    """Return "A", "B" or "draw" from a list of (games_a, games_b) tuples. Same rules as build.py."""
    won_a = sum(1 for a, b in sets if is_set_won(a, b))
    won_b = sum(1 for a, b in sets if is_set_won(b, a))
    if won_a > won_b:
        return "A"
    if won_b > won_a:
        return "B"
    return "draw"


def is_logged_in(request: Request):
    return request.session.get("auth") is True


def get_or_create_player(session: Session, name: str) -> Player:
    player = session.scalar(select(Player).where(func.lower(Player.name) == name.lower()))
    if player is None:
        player = Player(name=name)
        session.add(player)
        session.flush()
    return player


@app.get("/healthz")
def healthz():
    """Cheap liveness check (does not touch the database)."""
    return {"status": "ok", "version": VERSION}


@app.get("/healthz/db")
def healthz_db(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    matches = session.scalar(select(func.count()).select_from(Match))
    return {"status": "ok", "version": VERSION, "matches": matches}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    matches = session.scalars(select(Match).order_by(Match.played_on.desc(), Match.id.desc()).limit(50)).unique()
    rows = [
        {"match": m, "winner": match_winner([(s.games_a, s.games_b) for s in m.sets])}
        for m in matches
    ]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"rows": rows, "logged_in": is_logged_in(request), "saved": request.query_params.get("gemt")},
    )


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def login(request: Request, password: str = Form("")):
    expected = os.environ.get("ADMIN_PASSWORD", "")
    if expected and hmac.compare_digest(password.encode(), expected.encode()):
        request.session["auth"] = True
        return RedirectResponse("/ny", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": "Forkert kodeord"}, status_code=401)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


def form_context(session: Session, values: dict, errors: list[str]):
    players = session.scalars(select(Player.name).order_by(Player.name)).all()
    return {"players": players, "venues": VENUES, "values": values, "errors": errors, "max_sets": MAX_SETS}


@app.get("/ny", response_class=HTMLResponse)
def new_match_form(request: Request, session: Session = Depends(get_session)):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    values = {"played_on": date.today().isoformat(), "venue": request.session.get("last_venue", VENUES[0])}
    return templates.TemplateResponse(request, "new_match.html", form_context(session, values, []))


@app.post("/ny")
async def create_match(request: Request, session: Session = Depends(get_session)):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    values = {k: str(v).strip() for k, v in form.items()}
    errors = []

    try:
        played_on = date.fromisoformat(values.get("played_on", ""))
    except ValueError:
        errors.append("Ugyldig dato")
        played_on = None

    venue = values.get("venue", "")
    if venue not in VENUES:
        errors.append("Vælg inde eller ude")

    names = [values.get(k, "") for k in ("a1", "a2", "b1", "b2")]
    if any(not n for n in names):
        errors.append("Udfyld alle fire spillere")
    elif len({n.lower() for n in names}) < 4:
        errors.append("Samme spiller må kun optræde én gang")

    sets = []
    for i in range(1, MAX_SETS + 1):
        raw_a, raw_b = values.get(f"s{i}a", ""), values.get(f"s{i}b", "")
        if not raw_a and not raw_b:
            continue
        try:
            a, b = int(raw_a), int(raw_b)
        except ValueError:
            errors.append(f"Sæt {i}: udfyld begge scorer med tal")
            continue
        if not (0 <= a <= 7 and 0 <= b <= 7):
            errors.append(f"Sæt {i}: scorer skal være mellem 0 og 7")
            continue
        sets.append((a, b))
    if not sets and not any(e.startswith("Sæt") for e in errors):
        errors.append("Indtast mindst ét sæt")

    if errors:
        return templates.TemplateResponse(
            request, "new_match.html", form_context(session, values, errors), status_code=422
        )

    a1, a2, b1, b2 = (get_or_create_player(session, n) for n in names)
    match = Match(played_on=played_on, venue=venue, a1=a1, a2=a2, b1=b1, b2=b2)
    match.sets = [MatchSet(set_no=i, games_a=a, games_b=b) for i, (a, b) in enumerate(sets, start=1)]
    session.add(match)
    session.commit()
    request.session["last_venue"] = venue
    return RedirectResponse(f"/?gemt={match.id}", status_code=303)

