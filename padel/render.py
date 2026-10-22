"""Render the stats page (templates/index.html) from match dicts."""

import os

from jinja2 import Environment, FileSystemLoader
from jinja2.utils import htmlsafe_json_dumps

from padel.stats import build_stats

_template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
# Autoescape: player names come from the app's form.
_env = Environment(loader=FileSystemLoader(_template_dir), autoescape=True)
TEMPLATE = _env.get_template("index.html")


def render_html(matches, app_bar=None, filter_bar=None):
    """Render the stats page.

    app_bar / filter_bar: optional Markup from the web app, shown above the title (login, + Indtast kamp)
    and below it (filters). The acceptance test passes neither.
    """
    stats = build_stats(matches)
    stats_json = {"elo": stats["elo_dict"], "pairCounts": stats["pair_counts"], "eloHistory": stats["elo_history"]}
    return TEMPLATE.render(
        matches=matches,
        stats=stats,
        # JSON for a <script> block: <, >, & and ' are \u-escaped. Key order kept (no sort_keys).
        stats_json=htmlsafe_json_dumps(stats_json),
        app_bar=app_bar,
        filter_bar=filter_bar,
    )
