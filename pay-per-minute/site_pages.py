#!/usr/bin/env python3
"""Render the crawlable pages of Pay Per Minute from data.json.

Writes into site/ beside this file:
  index.html, data.json, game/            the interactive app (copied)
  premier-league-wages/                   league hub: every player's wage, ranked
  clubs/<club>/                           one page per club
  players/<player>/                       one page per tracked player
  sitemap.xml, robots.txt

Usage: python3 site_pages.py   (renders from the existing data.json)
SITE_URL sets the absolute address used in canonical links and the sitemap.
"""
import datetime, html, json, os, pathlib, re, shutil

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "site"
SITE_URL = os.environ.get("SITE_URL", "https://web-production-3f6f022b.up.railway.app").rstrip("/")

CLUB_NAMES = {
    "ARS": "Arsenal", "AVL": "Aston Villa", "BOU": "Bournemouth", "BRE": "Brentford", "BHA": "Brighton & Hove Albion",
    "CHE": "Chelsea", "COV": "Coventry City", "CRY": "Crystal Palace", "EVE": "Everton", "FUL": "Fulham",
    "HUL": "Hull City", "IPS": "Ipswich Town", "LEE": "Leeds United", "LIV": "Liverpool", "MCI": "Manchester City",
    "MUN": "Manchester United", "NEW": "Newcastle United", "NFO": "Nottingham Forest", "TOT": "Tottenham Hotspur",
    "SUN": "Sunderland",
}
CLUB_COLOURS = {
    "ARS": "#DB0007", "AVL": "#670E36", "BOU": "#B50E12", "BRE": "#C8102E", "BHA": "#0057B8", "CHE": "#034694",
    "COV": "#3BA6E1", "CRY": "#1B458F", "EVE": "#003399", "FUL": "#1A1A1A", "HUL": "#E67E00", "IPS": "#0044A9",
    "LEE": "#1D428A", "LIV": "#C8102E", "MCI": "#5B9FD6", "MUN": "#DA291C", "NEW": "#241F20", "NFO": "#DD0000",
    "TOT": "#132257", "SUN": "#EB172B",
}
POS_WORD = {"GK": "goalkeeper", "DEF": "defender", "MID": "midfielder", "FWD": "forward"}
UNITS = [  # (one, many, price)
    ("Freddo", "Freddos", 0.30), ("meal deal", "meal deals", 4.0), ("pint", "pints", 5.0),
    ("Premier League match ticket", "match tickets", 50.0), ("replica shirt", "replica shirts", 85.0),
    ("season ticket", "season tickets", 800.0), ("average UK salary", "average UK salaries", 37000.0),
    ("average UK house", "average UK houses", 270000.0),
]
ACTIONS = [  # key, singular, plural, positions
    ("goals", "goal", "Goals", {"DEF", "MID", "FWD"}),
    ("assists", "assist", "Assists", {"DEF", "MID", "FWD"}),
    ("ga", "goal or assist", "Goals + assists", {"DEF", "MID", "FWD"}),
    ("tackles", "tackle", "Tackles", {"DEF", "MID", "FWD"}),
    ("recoveries", "ball recovery", "Recoveries", {"DEF", "MID", "FWD"}),
    ("defcon", "defensive action", "Defensive actions", {"DEF", "MID", "FWD"}),
    ("saves", "save", "Saves", {"GK"}),
    ("cs", "clean sheet", "Clean sheets", {"GK", "DEF"}),
    ("pen_saves", "penalty save", "Penalties saved", {"GK"}),
    ("gc", "goal conceded", "Goals conceded", {"GK"}),
    ("og", "own goal", "Own goals", {"GK", "DEF", "MID", "FWD"}),
]

e = lambda s: html.escape(str(s), quote=True)


def slugify(text):
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def gbp(v):
    return f"£{v:,.0f}"


def compact(v):
    if v >= 1e6:
        return f"£{v / 1e6:.2f}m"
    if v >= 1e3:
        return f"£{int(v / 1e3 + 0.5):,}k"  # round half up, like the app
    return f"£{v:,.0f}"


def money(v):
    return f"£{v:,.0f}" if v >= 100 else f"£{v:,.2f}"


def duration(sec):
    if sec < 90:
        n = max(1, round(sec))
        return f"{n} second{'s' if n != 1 else ''}"
    if sec < 5400:
        return f"{round(sec / 60)} minutes"
    if sec < 172800:
        h = sec / 3600
        return f"{h:.1f} hours" if h < 10 else f"{round(h)} hours"
    return f"{sec / 86400:.1f} days"


def count(p, key):
    return p["goals"] + p["assists"] if key == "ga" else (p.get(key) or 0)


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def enrich(data):
    """Add the figures the app computes in the browser: pay so far, pay per minute, value score, ranks."""
    start = datetime.datetime.fromisoformat(data["season_start"].replace("Z", "+00:00"))
    built = datetime.datetime.fromisoformat(data["built_at"])
    days = max(0.0, (built - start).total_seconds() / 86400)
    players = data["players"]
    for p in players:
        p["earned"] = p["weekly"] / 7 * days
        p["ppm"] = p["earned"] / p["minutes"] if p["minutes"] else None
        p["club"] = CLUB_NAMES.get(p["team"], p["team"])
        p["club_slug"] = slugify(p["club"])
        p.setdefault("display", p["full_name"])
        p.setdefault("slug", slugify(p["display"]))
    pool = [p for p in players if p["minutes"] >= data["rating_min_minutes"] and p.get("rating") is not None]

    def pct(key):
        vals = sorted(p[key] for p in pool)
        def f(v):
            if len(vals) < 2:
                return 50
            below = sum(x < v for x in vals)
            same = sum(x == v for x in vals)
            return (below + (same - 1) / 2) / (len(vals) - 1) * 100
        return f
    r_pct, c_pct = pct("rating"), pct("ppm")
    for p in players:
        p["value"] = round((r_pct(p["rating"]) + (100 - c_pct(p["ppm"]))) / 2) if p in pool else None
    by_wage = sorted(players, key=lambda p: -p["weekly"])
    for i, p in enumerate(by_wage):
        p["league_rank"] = 1 + sum(q["weekly"] > p["weekly"] for q in players)
        p["club_rank"] = 1 + sum(q["weekly"] > p["weekly"] for q in players if q["team"] == p["team"])
    data["days"] = days
    return data


# ---------- page shell ----------

def shared_assets():
    src = (HERE / "index.html").read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
    sprite = re.search(r'(<svg width="0" height="0".*?</svg>)', src, re.S).group(1)
    fonts = re.search(r'(<link rel="stylesheet" href="https://fonts.googleapis.com[^>]+>)', src).group(1)
    return css, sprite, fonts


PAGE_CSS = """
.page { max-width: 1040px; margin: 0 auto; display: grid; gap: 32px; padding-block: 24px 16px; }
.crumbs { font-size: 13px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px; }
.crumbs a { color: var(--muted); }
.ph { display: grid; gap: 12px; }
.ph h1 { font-size: clamp(40px, 7vw, 72px); }
.ph .meta { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; color: var(--muted); font-size: 14px; }
.answer { font-size: 18px; line-height: 1.55; max-width: 68ch; }
.answer strong { color: var(--accent); }
.page h2 { font-size: clamp(24px, 3.4vw, 32px); }
.page section { display: grid; gap: 14px; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }
.facts li { list-style: none; background: var(--sheet); border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; display: flex; gap: 10px; align-items: flex-start; }
.facts li .ic { color: var(--accent); margin-top: 2px; }
.facts ul { margin: 0; padding: 0; }
.tscroll { overflow-x: auto; background: var(--sheet); border: 1px solid var(--line); border-radius: 6px; }
.wtable { width: 100%; border-collapse: collapse; font-size: 14px; }
.wtable th { text-align: left; font: 600 11px/1.2 var(--body); text-transform: uppercase; letter-spacing: .08em; color: var(--muted); background: var(--paper); padding: 10px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; }
.wtable td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: middle; }
.wtable tr:last-child td { border-bottom: 0; }
.wtable .n { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
.wtable th.n { text-align: right; }
.wtable .c { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; }
.wtable th.c { text-align: right; font-family: var(--body); }
.wtable .win { color: var(--good); font-weight: 600; }
.wtable .win .ic { width: 1em; height: 1em; }
.wtable .hl td { background: var(--accent-soft); }
.wtable a { color: var(--ink); font-weight: 600; text-decoration: none; }
.wtable a:hover { text-decoration: underline; }
.wtable .ppm { color: var(--accent); font-weight: 600; }
.who-cell { display: flex; align-items: center; gap: 10px; min-width: 0; }
.faq details { background: var(--sheet); border: 1px solid var(--line); border-radius: 6px; padding: 12px 16px; }
.faq details + details { margin-top: 8px; }
.faq summary { font-weight: 600; cursor: pointer; }
.faq p { margin-top: 8px; color: var(--muted); max-width: 70ch; }
.source { color: var(--muted); font-size: 13px; max-width: 75ch; }
.cta { display: inline-flex; align-items: center; gap: 8px; background: var(--ink); color: var(--paper); text-decoration: none; padding: 10px 16px; border-radius: 4px; font-weight: 600; justify-self: start; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chips a { display: inline-flex; align-items: center; gap: 8px; background: var(--sheet); border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px 6px 6px; color: var(--ink); text-decoration: none; font-size: 14px; }
.chips a:hover { border-color: var(--ink); }
.page-footer { color: var(--muted); font-size: 13px; max-width: 1040px; margin: 0 auto; padding-block: 8px 24px; display: grid; gap: 6px; }
@media (max-width: 720px) {
  .wtable .opt { display: none; } .answer { font-size: 16px; }
  .wtable th, .wtable td { padding: 9px 8px; }
  .wtable .chip { display: none; }
}
"""

NAV = [("/", "house", "Home"), ("/#players", "list", "Players"), ("/#value", "scale", "Best value"),
       ("/#actions", "receipt", "Price per action"), ("/#clubs", "shield", "Clubs"),
       ("/premier-league-wages/", "note", "Wages table"), ("/north-south-divide/", "compass", "North v South"),
       ("/team-of-the-week/", "trophy", "Team of the week"),
       ("/#team", "users", "Team breakdown"),
       ("/#bench", "bench", "Paid to watch"), ("/game/", "shuffle", "Higher or lower"), ("/#you", "user", "You vs them")]


def ic(name, cls=""):
    return f'<svg class="ic{(" " + cls) if cls else ""}" aria-hidden="true"><use href="#i-{name}"/></svg>'


def chip(team):
    return f'<span class="chip" style="background:{CLUB_COLOURS.get(team, "#555")}">{e(team)}</span>'


def page(assets, *, path, title, description, body, current="", jsonld=None):
    css, sprite, fonts = assets
    url = SITE_URL + path
    links = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if href == current else ""}>{ic(i)}{e(label)}</a>' for href, i, label in NAV)
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (jsonld or []))
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Pay Per Minute">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(url)}">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
{fonts}
<style>{css}{PAGE_CSS}</style>
{ld}
</head>
<body>
{sprite}
<nav class="topnav" aria-label="Pages">
  <div class="topnav-in">
    <a class="brand" href="/">Pay per <span>minute</span></a>
    <div class="navlinks">{links}</div>
  </div>
</nav>
<main class="page">
{body}
</main>
<footer class="page-footer">
  <p>Wages are reported estimates: clubs don't publish salaries. Minutes, goals and other stats come from the Fantasy Premier League API (Opta data) and refresh several times a day.</p>
  <p><a href="/premier-league-wages/">Premier League wages table</a> · <a href="/">Pay Per Minute home</a></p>
</footer>
</body>
</html>
"""


def faq_ld(qas):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}} for q, a in qas]}


def crumbs_ld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE_URL + href} for i, (name, href) in enumerate(items)]}


def faq_html(qas):
    return '<section class="faq"><h2>' + ic("sparkle", "h-ic") + "Questions</h2>" + "".join(
        f"<details{' open' if i == 0 else ''}><summary>{e(q)}</summary><p>{a}</p></details>" for i, (q, a) in enumerate(qas)) + "</section>"


def crumbs_html(items):
    parts = [f'<a href="{href}">{e(name)}</a>' for name, href in items[:-1]] + [f"<span>{e(items[-1][0])}</span>"]
    return '<nav class="crumbs" aria-label="Breadcrumb">' + " / ".join(parts) + "</nav>"


def source_text(p):
    src = p.get("source") or ""
    return "press reports" if src.lower().startswith("reported estimate") else src


def player_link(p):
    return f'<a href="/players/{p["slug"]}/">{e(p["display"])}</a>'


def player_table(rows, highlight=None, show_club=True):
    head = ("<tr><th class='opt'>#</th><th>Player</th>" + ("<th class='opt'>Club</th>" if show_club else "")
            + "<th class='opt'>Pos</th><th class='n'>Weekly</th><th class='n opt'>Yearly</th>"
              "<th class='n opt'>Minutes</th><th class='n'>£ per min</th></tr>")
    body = "".join(
        f"<tr{' class=hl' if p is highlight else ''}><td class='n opt'>{i + 1}</td>"
        f"<td><span class='who-cell'>{chip(p['team'])}{player_link(p)}</span></td>"
        + (f"<td class='opt'><a href='/clubs/{p['club_slug']}/'>{e(p['club'])}</a></td>" if show_club else "")
        + f"<td class='opt'>{p['pos']}</td><td class='n'>{gbp(p['weekly'])}</td><td class='n opt'>{compact(p['weekly'] * 52)}</td>"
          f"<td class='n opt'>{p['minutes']:,}</td><td class='n ppm'>{money(p['ppm']) if p['ppm'] else '–'}</td></tr>"
        for i, p in enumerate(rows))
    return f"<div class='tscroll'><table class='wtable'><thead>{head}</thead><tbody>{body}</tbody></table></div>"


# ---------- player pages ----------

def render_player(assets, data, p):
    players, season, gw = data["players"], data["season"], data["gameweek"]
    name, club = p["display"], p["club"]
    yearly = p["weekly"] * 52
    per_sec = p["weekly"] / 604800
    mates = sorted([q for q in players if q["team"] == p["team"]], key=lambda q: -q["weekly"])
    top_mate = mates[0]
    ppm_txt = money(p["ppm"]) if p["ppm"] else None

    if ppm_txt:
        answer = (f"{e(name)} earns a reported <strong>{gbp(p['weekly'])} a week</strong> ({compact(yearly)} a year) at {e(club)}. "
                  f"That's {p['minutes']:,} Premier League minutes played after gameweek {gw}, so every minute on the pitch "
                  f"has cost <strong>{ppm_txt}</strong>.")
        desc = (f"{name} earns a reported {gbp(p['weekly'])} a week ({compact(yearly)} a year) at {club}. "
                f"That's {ppm_txt} for every Premier League minute played in {season}.")
    else:
        answer = (f"{e(name)} earns a reported <strong>{gbp(p['weekly'])} a week</strong> ({compact(yearly)} a year) at {e(club)}, "
                  f"and has been paid <strong>{compact(p['earned'])}</strong> this season without playing a Premier League minute.")
        desc = f"{name} earns a reported {gbp(p['weekly'])} a week at {club} and has been paid {compact(p['earned'])} in {season} without a league minute."

    tiles = [("wallet", "Weekly wage", gbp(p["weekly"]), f"{compact(yearly)} a year, before tax"),
             ("clock", "Per minute played", ppm_txt or "No minutes", f"{p['minutes']:,} league minutes"),
             ("coins", "Paid so far", compact(p["earned"]), f"{round(data['days'])} days of {season}"),
             ("star", "Rating", f"{p['rating']:.1f}" if p.get("rating") is not None else "–", "out of 10, from FPL BPS"),
             ("scale", "Value score", f"{p['value']}/100" if p.get("value") is not None else "–", "rating vs cost per minute"),
             ("trophy", "Wage rank", ordinal(p["league_rank"]), f"in the league, {ordinal(p['club_rank'])} at {club}")]
    tiles_html = '<div class="tiles">' + "".join(
        f'<div class="tile"><span class="label">{ic(i)}{e(l)}</span><b>{e(v)}</b><small>{e(s)}</small></div>' for i, l, v, s in tiles) + "</div>"

    fun = []
    for one, many, price in UNITS[:2] + UNITS[3:4] + UNITS[6:7]:
        sec = price / per_sec
        if sec < 1:
            fun.append(("clock", f"Earns <strong>{per_sec / price:.1f} {many}</strong> every second, day and night."))
        else:
            fun.append(("clock", f"Earns {'an' if one[0].lower() in 'aeiou' else 'a'} {one} every <strong>{duration(sec)}</strong>."))
    if p["goals"]:
        per_goal = p["earned"] / p["goals"]
        fun.append(("ball", f"Each league goal has cost <strong>{per_goal / 4:,.0f} meal deals</strong> ({compact(per_goal)})."))
    if p["pos"] == "GK" and p.get("saves"):
        fun.append(("glove", f"Each save has cost <strong>{p['earned'] / p['saves'] / 5:,.0f} pints</strong> ({compact(p['earned'] / p['saves'])})."))
    if p["ppm"]:
        fun.append(("ticket", f"Every minute on the pitch costs <strong>{p['ppm'] / 50:,.0f} match tickets</strong>."))
    fun_html = '<section><h2>' + ic("sparkle", "h-ic") + 'What that buys</h2><div class="facts"><ul class="facts">' + "".join(
        f"<li>{ic(i)}<span>{t}</span></li>" for i, t in fun) + "</ul></div></section>"

    rows = []
    for key, single, plural, pos in ACTIONS:
        if p["pos"] not in pos:
            continue
        n = count(p, key)
        rows.append(f"<tr><td>{e(plural)}</td><td class='n'>{n}</td><td class='n ppm'>{compact(p['earned'] / n) if n else '–'}</td></tr>")
    actions_html = ('<section><h2>' + ic("receipt", "h-ic") + 'Cost per action</h2>'
                    f"<p class='lede'>What {e(name)} has been paid this season for each one, in the Premier League. Only actions that suit a {POS_WORD[p['pos']]} are shown.</p>"
                    "<div class='tscroll'><table class='wtable'><thead><tr><th>Action</th><th class='n'>This season</th><th class='n'>Paid per action</th></tr></thead><tbody>"
                    + "".join(rows) + "</tbody></table></div></section>")

    club_html = (f'<section><h2>{ic("shield", "h-ic")}{e(club)} wages</h2>'
                 + player_table(mates[:12], highlight=p, show_club=False)
                 + f'<a class="cta" href="/clubs/{p["club_slug"]}/">{ic("shield")}All {e(club)} wages</a></section>')

    near = sorted([q for q in players if q is not p], key=lambda q: (abs(q["weekly"] - p["weekly"]), -q["weekly"]))[:8]
    near_html = (f'<section><h2>{ic("users", "h-ic")}Paid like {e(name)}</h2><div class="chips">'
                 + "".join(f'<a href="/players/{q["slug"]}/">{chip(q["team"])}{e(q["display"])} · {compact(q["weekly"])}/wk</a>' for q in near)
                 + "</div></section>")

    if top_mate is p:
        rank_answer = f"Yes. Of the {club} players we track, {e(name)} has the highest reported wage at {gbp(p['weekly'])} a week."
    else:
        rank_answer = (f"No. {e(name)} is the {ordinal(p['club_rank'])}-highest-paid {club} player we track. "
                       f"{player_link(top_mate)} earns the most, at a reported {gbp(top_mate['weekly'])} a week.")
    qas = [
        (f"How much does {name} earn a week?",
         f"A reported {gbp(p['weekly'])} a week before tax, which is about {compact(yearly)} a year. Source: {e(source_text(p))}. Clubs don't publish wages, so this is an estimate."),
        (f"How much does {name} earn per minute?",
         (f"{ppm_txt} for every Premier League minute played in {season} so far: {compact(p['earned'])} paid across {p['minutes']:,} minutes."
          if ppm_txt else f"{e(name)} hasn't played a Premier League minute in {season} yet, but has still been paid {compact(p['earned'])}.")
         + f" Around the clock, the wage works out at {money(p['weekly'] / 10080)} a minute."),
        (f"Is {name} the highest-paid player at {club}?", rank_answer),
        (f"How long does it take {name} to earn the average UK salary?",
         f"About {duration(37000 / per_sec)}, based on a £37,000 average UK salary and a {gbp(p['weekly'])} weekly wage."),
    ]
    crumbs = [("Home", "/"), ("Premier League wages", "/premier-league-wages/"), (club, f"/clubs/{p['club_slug']}/"), (name, f"/players/{p['slug']}/")]
    body = (crumbs_html(crumbs)
            + f'<header class="ph"><div class="meta">{chip(p["team"])}<span>{e(club)}</span><span>{POS_WORD[p["pos"]].capitalize()}</span><span>{e(season)}</span></div>'
            + f"<h1>{e(name)} salary</h1><p class='answer'>{answer}</p></header>"
            + tiles_html + fun_html + actions_html + club_html + near_html + faq_html(qas)
            + f"<p class='source'>{ic('note')} Wage source: {e(source_text(p))}. Reported estimate, before tax, excluding bonuses. "
              f"Minutes and stats from the Fantasy Premier League API, updated {datetime.date.fromisoformat(data['built_at'][:10]).strftime('%-d %B %Y')}.</p>"
            + f'<a class="cta" href="/#players">{ic("list")}Compare every player</a>')
    weekly_k = f"£{p['weekly'] / 1000:,.0f}k" if p["weekly"] >= 1000 else gbp(p["weekly"])
    title = f"{name} salary {season}: {weekly_k} a week" + (f", {ppm_txt} per minute played" if ppm_txt else "") + " | Pay Per Minute"
    return page(assets, path=f"/players/{p['slug']}/", title=title, description=desc, body=body,
                jsonld=[faq_ld(qas), crumbs_ld(crumbs)])


# ---------- club pages ----------

def club_stats(players, team):
    squad = sorted([p for p in players if p["team"] == team], key=lambda p: -p["weekly"])
    earned = sum(p["earned"] for p in squad)
    minutes = sum(p["minutes"] for p in squad)
    return squad, earned, minutes


def render_club(assets, data, team, ranks):
    players, season = data["players"], data["season"]
    club = CLUB_NAMES[team]
    slug = slugify(club)
    squad, earned, minutes = club_stats(players, team)
    weekly = sum(p["weekly"] for p in squad)
    goals = sum(p["goals"] for p in squad)
    ppm = earned / minutes if minutes else 0
    top = squad[0]
    desc = (f"{club} wages {season}: {top['display']} is the highest-paid at a reported {gbp(top['weekly'])} a week. "
            f"See every tracked player's salary and what {club} pay per minute played.")
    answer = (f"The {len(squad)} {e(club)} players we track earn a combined <strong>{compact(weekly)} a week</strong>. "
              f"{player_link(top)} is the highest paid at a reported {gbp(top['weekly'])} a week. "
              f"Across their {minutes:,} Premier League minutes this season, {e(club)} have paid <strong>{money(ppm)} per minute played</strong>, "
              f"the {ordinal(ranks[team])}-highest in the league.")
    tiles = [("wallet", "Weekly wages", compact(weekly), f"{len(squad)} tracked players"),
             ("coins", "Paid so far", compact(earned), season),
             ("clock", "Per minute played", money(ppm), f"{ordinal(ranks[team])} of 20"),
             ("ball", "Per league goal", compact(earned / goals) if goals else "No goals", f"{goals} goals by tracked players")]
    tiles_html = '<div class="tiles">' + "".join(
        f'<div class="tile"><span class="label">{ic(i)}{e(l)}</span><b>{e(v)}</b><small>{e(s)}</small></div>' for i, l, v, s in tiles) + "</div>"
    qas = [(f"Who is the highest-paid player at {club}?",
            f"{e(top['display'])}, on a reported {gbp(top['weekly'])} a week ({compact(top['weekly'] * 52)} a year)."),
           (f"How much do {club} pay their players per week?",
            f"The {len(squad)} players we track earn a combined {compact(weekly)} a week. The full squad costs more, because we only list players with a reported wage."),
           (f"How much do {club} pay per minute played?",
            f"{money(ppm)} per Premier League minute in {season}, {ordinal(ranks[team])}-highest of the 20 clubs.")]
    crumbs = [("Home", "/"), ("Premier League wages", "/premier-league-wages/"), (club, f"/clubs/{slug}/")]
    others = "".join(f'<a href="/clubs/{slugify(CLUB_NAMES[t])}/">{chip(t)}{e(CLUB_NAMES[t])}</a>' for t in sorted(CLUB_NAMES, key=lambda t: CLUB_NAMES[t]) if t != team)
    body = (crumbs_html(crumbs)
            + f'<header class="ph"><div class="meta">{chip(team)}<span>Premier League</span><span>{e(season)}</span></div>'
            + f"<h1>{e(club)} wages</h1><p class='answer'>{answer}</p></header>" + tiles_html
            + f'<section><h2>{ic("list", "h-ic")}Every {e(club)} salary</h2>' + player_table(squad, show_club=False) + "</section>"
            + faq_html(qas)
            + f'<section><h2>{ic("shield", "h-ic")}Other clubs</h2><div class="chips">{others}</div></section>'
            + f'<a class="cta" href="/#team">{ic("users")}Team breakdown: cost per goal, assist and save</a>')
    title = f"{club} wages {season}: every player's salary and pay per minute | Pay Per Minute"
    return page(assets, path=f"/clubs/{slug}/", title=title, description=desc, body=body, jsonld=[faq_ld(qas), crumbs_ld(crumbs)])


# ---------- league hub ----------

def render_hub(assets, data, ranks):
    players, season = data["players"], data["season"]
    ranked = sorted(players, key=lambda p: -p["weekly"])
    top = ranked[0]
    avg = sum(p["weekly"] for p in players) / len(players)
    dearest_club = min(ranks, key=ranks.get)
    per_club = []
    for team in sorted(CLUB_NAMES, key=lambda t: CLUB_NAMES[t]):
        squad = [p for p in ranked if p["team"] == team]
        if squad:
            per_club.append(squad[0])
    answer = (f"{player_link(top)} is the highest-paid player in the Premier League, on a reported <strong>{gbp(top['weekly'])} a week</strong>. "
              f"Across the {len(players)} players we track the average is {gbp(avg)} a week, and "
              f"{e(CLUB_NAMES[dearest_club])} pay the most per minute played.")
    best_html = ('<section><h2>' + ic("trophy", "h-ic") + 'Highest-paid player at every club</h2>'
                 "<div class='tscroll'><table class='wtable'><thead><tr><th>Club</th><th>Player</th><th class='n'>Weekly</th><th class='n opt'>£ per min</th></tr></thead><tbody>"
                 + "".join(f"<tr><td><span class='who-cell'>{chip(p['team'])}<a href='/clubs/{p['club_slug']}/'>{e(p['club'])}</a></span></td>"
                           f"<td>{player_link(p)}</td><td class='n'>{gbp(p['weekly'])}</td><td class='n opt ppm'>{money(p['ppm']) if p['ppm'] else '–'}</td></tr>" for p in per_club)
                 + "</tbody></table></div></section>")
    club_rows = sorted(ranks, key=ranks.get)
    clubs_html = ('<section><h2>' + ic("shield", "h-ic") + 'Club wage bills</h2>'
                  "<div class='tscroll'><table class='wtable'><thead><tr><th>#</th><th>Club</th><th class='n'>Weekly (tracked)</th><th class='n opt'>Players</th><th class='n'>£ per min</th></tr></thead><tbody>"
                  + "".join(
                      (lambda sq, ea, mi: f"<tr><td class='n'>{ranks[t]}</td><td><span class='who-cell'>{chip(t)}<a href='/clubs/{slugify(CLUB_NAMES[t])}/'>{e(CLUB_NAMES[t])}</a></span></td>"
                                          f"<td class='n'>{compact(sum(p['weekly'] for p in sq))}</td><td class='n opt'>{len(sq)}</td><td class='n ppm'>{money(ea / mi) if mi else '–'}</td></tr>")(*club_stats(players, t))
                      for t in club_rows)
                  + "</tbody></table></div></section>")
    qas = [("Who is the highest-paid Premier League player?",
            f"{e(top['display'])} of {e(top['club'])}, on a reported {gbp(top['weekly'])} a week ({compact(top['weekly'] * 52)} a year)."),
           ("What is the average Premier League wage?",
            f"About {gbp(avg)} a week across the {len(players)} players with a reported wage. Squad players on smaller deals are under-represented, so the true average is lower."),
           ("Which Premier League club pays the most per minute played?",
            f"{e(CLUB_NAMES[dearest_club])}, once wages are divided by the league minutes their tracked players have actually played.")]
    crumbs = [("Home", "/"), ("Premier League wages", "/premier-league-wages/")]
    body = (crumbs_html(crumbs)
            + f'<header class="ph"><div class="meta"><span>Premier League</span><span>{e(season)}</span><span>After gameweek {data["gameweek"]}</span></div>'
            + f"<h1>Premier League wages {e(season)}</h1><p class='answer'>{answer}</p></header>"
            + best_html + clubs_html
            + f'<section><h2>{ic("list", "h-ic")}Every player, by weekly wage</h2>' + player_table(ranked) + "</section>"
            + faq_html(qas))
    title = f"Premier League wages {season}: every player's salary, ranked | Pay Per Minute"
    desc = (f"Every Premier League player's reported salary for {season}, ranked. {top['display']} is the highest paid on "
            f"{gbp(top['weekly'])} a week. Plus the highest earner at every club and what each club pays per minute played.")
    return page(assets, path="/premier-league-wages/", title=title, description=desc, body=body, current="/premier-league-wages/",
                jsonld=[faq_ld(qas), crumbs_ld(crumbs)])


# ---------- team of the week ----------

XI_KINDS = [
    ("value", "tick", "Value XI", "The best value for money: the highest match ratings for the lowest pay per minute. Players need 60 minutes that gameweek."),
    ("overpaid", "cross", "Overpaid XI", "The worst value: low match ratings on big wages. Players need 60 minutes that gameweek."),
    ("bench", "bench", "Paid to watch XI", "The best-paid tracked players who didn't play a league minute that gameweek."),
]


def pitch_html(team, kind, label):
    rows = []
    for pos in ("FWD", "MID", "DEF", "GK"):
        toks = []
        for p, st in team:
            if p["pos"] != pos:
                continue
            stat = f"{compact(p['weekly'])}/wk" if kind == "bench" else f"{st['r']:.1f} · {money(p['weekly'] / st['m'])}/min"
            toks.append(f'<a class="tok" href="/players/{p["slug"]}/"><span class="disc" style="background:{CLUB_COLOURS.get(p["team"], "#555")}">{e(p["team"])}</span>'
                        f'<span class="tname">{e(p["name"])}</span><span class="tstat">{e(stat)}</span></a>')
        rows.append(f'<div class="prow">{"".join(toks)}</div>')
    return f'<div class="pitch" role="img" aria-label="{e(label)}"><span class="half" aria-hidden="true"></span>{"".join(rows)}</div>'


def xi_table(team, kind):
    head = ("<tr><th>Pos</th><th>Player</th><th class='opt'>Club</th><th class='n opt'>Weekly</th>"
            + ("<th class='n'>Paid this season</th>" if kind == "bench" else "<th class='n opt'>Mins</th><th class='n'>Rating</th><th class='n'>Value</th>") + "</tr>")
    body = ""
    for p, st in team:
        body += (f"<tr><td>{p['pos']}</td><td><span class='who-cell'>{chip(p['team'])}{player_link(p)}</span></td>"
                 f"<td class='opt'><a href='/clubs/{p['club_slug']}/'>{e(p['club'])}</a></td><td class='n opt'>{compact(p['weekly'])}</td>"
                 + (f"<td class='n ppm'>{compact(p['earned'])}</td>" if kind == "bench"
                    else f"<td class='n opt'>{st['m']}</td><td class='n'>{st['r']:.1f}</td><td class='n ppm'>{st['v']}</td>") + "</tr>")
    return f"<div class='tscroll'><table class='wtable'><thead>{head}</thead><tbody>{body}</tbody></table></div>"


def render_xi(assets, data, g, latest):
    by_id = {p["id"]: p for p in data["players"]}
    gw, season = g["gw"], data["season"]
    sections, summary = [], {}
    for kind, icon, label, blurb in XI_KINDS:
        team = [(by_id[i], g["stats"][str(i)]) for i in g["teams"][kind] if i in by_id and str(i) in g["stats"]]
        wages = sum(p["weekly"] for p, _ in team)
        rated = [st["r"] for _, st in team if st.get("r") is not None]
        summary[kind] = (team, wages, sum(rated) / len(rated) if rated else 0)
        fact = (f"Cost <strong>{compact(wages)}</strong> in wages, average rating {summary[kind][2]:.1f}." if kind != "bench"
                else f"<strong>{compact(wages)}</strong> paid to players who didn't kick a ball.")
        sections.append(f'<section><h2>{ic(icon, "h-ic")}{e(label)}</h2><p class="lede">{e(blurb)} {fact}</p>'
                        + pitch_html(team, kind, f"Gameweek {gw} {label}") + xi_table(team, kind) + "</section>")
    best = max(summary["value"][0], key=lambda x: x[1]["v"], default=None)
    worst = min(summary["overpaid"][0], key=lambda x: x[1]["v"], default=None)
    answer = (f"Gameweek {gw}'s Value XI cost <strong>{compact(summary['value'][1])}</strong> in wages; the Overpaid XI took home "
              f"<strong>{compact(summary['overpaid'][1])}</strong>."
              + (f" Best value: {player_link(best[0])} ({best[1]['r']:.1f} rating on {compact(best[0]['weekly'])} a week)." if best else "")
              + (f" Worst value: {player_link(worst[0])} ({worst[1]['r']:.1f} on {compact(worst[0]['weekly'])} a week)." if worst else ""))
    path = "/team-of-the-week/" if latest else f"/team-of-the-week/gameweek-{gw}/"
    others = sorted((x["gw"] for x in data["gameweeks"]), reverse=True)
    gw_links = "".join(f'<a href="/team-of-the-week/gameweek-{n}/">{ic("calendar")}Gameweek {n}</a>' for n in others if n != gw or latest)
    crumbs = [("Home", "/"), ("Team of the week", "/team-of-the-week/")] + ([] if latest else [(f"Gameweek {gw}", path)])
    qas = [(f"Who made the Premier League Value XI in gameweek {gw}?",
            ", ".join(e(p["display"]) for p, _ in summary["value"][0]) + "."),
           (f"Who was the most overpaid Premier League player in gameweek {gw}?",
            f"{e(worst[0]['display'])}, with a {worst[1]['r']:.1f} match rating on a reported {gbp(worst[0]['weekly'])} a week." if worst else "Not enough data yet."),
           ("How is the team of the week picked?",
            "Each player's match rating comes from FPL's Bonus Points System, compared with everyone in the same position that gameweek. "
            "The value score blends that rating with how cheap each minute was. Players need 60 minutes to be picked on merit.")]
    body = (crumbs_html(crumbs)
            + f'<header class="ph"><div class="meta"><span>Premier League</span><span>{e(season)}</span><span>Gameweek {gw}</span></div>'
            + f"<h1>Team of the week{'' if latest else f': gameweek {gw}'}</h1><p class='answer'>{answer}</p></header>"
            + "".join(sections) + faq_html(qas)
            + f'<section><h2>{ic("calendar", "h-ic")}Other gameweeks</h2><div class="chips">{gw_links}</div></section>'
            + f'<a class="cta" href="/#xi">{ic("trophy")}Open the interactive team of the week</a>')
    title = f"Premier League team of the week: gameweek {gw} Value XI and Overpaid XI | Pay Per Minute"
    desc = (f"Premier League gameweek {gw} team of the week by value for money: the Value XI, the Overpaid XI and the best-paid players "
            f"who didn't play. Value XI wage bill {compact(summary['value'][1])}.")
    return page(assets, path=path, title=title, description=desc, body=body, current="/team-of-the-week/",
                jsonld=[faq_ld(qas), crumbs_ld(crumbs)])


# ---------- north v south ----------

REGION = {"LIV": "North", "EVE": "North", "MCI": "North", "MUN": "North", "NEW": "North", "SUN": "North", "LEE": "North", "HUL": "North",
          "AVL": "Midlands", "NFO": "Midlands", "COV": "Midlands", "ARS": "London", "CHE": "London", "TOT": "London", "CRY": "London",
          "FUL": "London", "BRE": "London", "BOU": "South coast", "BHA": "South coast", "IPS": "East Anglia"}
DERBIES = [("Manchester derby", "MCI", "MUN"), ("Merseyside derby", "LIV", "EVE"), ("North London derby", "ARS", "TOT"),
           ("Tyne–Wear derby", "NEW", "SUN"), ("West London derby", "CHE", "FUL"), ("M23 derby", "BHA", "CRY"), ("Yorkshire derby", "LEE", "HUL")]


def side(team):
    return "North" if REGION.get(team) in ("North", "Midlands") else "South"


def poss(name):
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def group(players, avail):
    earned = sum(p["earned"] for p in players)
    minutes = sum(p["minutes"] for p in players)
    goals = sum(p["goals"] for p in players)
    ga = sum(p["goals"] + p["assists"] for p in players)
    valued = [p for p in players if p.get("value") is not None]
    return {"n": len(players), "weekly": sum(p["weekly"] for p in players),
            "ppm": earned / minutes if minutes else None, "per_goal": earned / goals if goals else None,
            "per_ga": earned / ga if ga else None,
            "idle": sum(p["earned"] * max(0, 1 - p["minutes"] / avail) for p in players) if avail else 0,
            "value": sum(p["value"] for p in valued) / len(valued) if valued else None,
            "best": max(valued, key=lambda p: p["value"], default=None), "worst": min(valued, key=lambda p: p["value"], default=None),
            "top": max(players, key=lambda p: p["weekly"], default=None)}


def short_link(p):
    return f'<a href="/players/{p["slug"]}/">{e(p["name"])}</a>'


def cmp_table(heads, stats, rows):
    out = "<tr><th></th>" + "".join(f"<th class='c'>{e(h)}</th>" for h in heads) + "</tr>"
    body = ""
    for label, fmt, better, key in rows:
        win = -1
        if better and all(key(st) is not None for st in stats):
            vals = [key(st) for st in stats]
            if len(set(vals)) > 1:
                win = vals.index(min(vals) if better == "low" else max(vals))
        body += f"<tr><td>{e(label)}</td>" + "".join(
            f"<td class='c{' win' if i == win else ''}'>{ic('tick') + ' ' if i == win else ''}{fmt(st)}</td>" for i, st in enumerate(stats)) + "</tr>"
    return f"<div class='tscroll'><table class='wtable'><thead>{out}</thead><tbody>{body}</tbody></table></div>"


CMP = [
    ("Tracked players", lambda s: str(s["n"]), None, None),
    ("Weekly wages", lambda s: compact(s["weekly"]), None, None),
    ("Average weekly wage", lambda s: compact(s["weekly"] / s["n"]) if s["n"] else "–", None, None),
    ("Pay per minute played", lambda s: money(s["ppm"]) if s["ppm"] else "–", "low", lambda s: s["ppm"]),
    ("Cost per goal", lambda s: compact(s["per_goal"]) if s["per_goal"] else "–", "low", lambda s: s["per_goal"]),
    ("Cost per goal or assist", lambda s: compact(s["per_ga"]) if s["per_ga"] else "–", "low", lambda s: s["per_ga"]),
    ("Idle pay (paid, not playing)", lambda s: compact(s["idle"]), None, None),
    ("Average value score", lambda s: f"{s['value']:.0f}/100" if s["value"] is not None else "–", "high", lambda s: s["value"]),
    ("Best value", lambda s: f"{short_link(s['best'])} ({s['best']['value']})" if s["best"] else "–", None, None),
    ("Most overpaid", lambda s: f"{short_link(s['worst'])} ({s['worst']['value']})" if s["worst"] else "–", None, None),
    ("Highest paid", lambda s: f"{short_link(s['top'])}, {compact(s['top']['weekly'])}/wk" if s["top"] else "–", None, None),
]


def render_divide(assets, data):
    players, season = data["players"], data["season"]
    avail = data["gameweek"] * 90
    N = group([p for p in players if side(p["team"]) == "North"], avail)
    S = group([p for p in players if side(p["team"]) == "South"], avail)
    dear, cheap, dn, cn = (N, S, "North", "South") if (N["ppm"] or 0) > (S["ppm"] or 0) else (S, N, "South", "North")
    pct = round((dear["ppm"] / cheap["ppm"] - 1) * 100) if dear["ppm"] and cheap["ppm"] else 0
    better_value = "North" if (N["value"] or 0) > (S["value"] or 0) else "South"
    answer = (f"The {dn}'s Premier League players cost <strong>{pct}% more per minute played</strong> than the {cn}'s: "
              f"{money(dear['ppm'])} against {money(cheap['ppm'])}. On value for money, the <strong>{better_value}</strong> comes out on top. "
              f"The line runs from the Severn to the Wash, so the Midlands count as the North.")
    regions = ["North", "Midlands", "London", "South coast", "East Anglia"]
    reg_rows = ""
    for r in regions:
        st = group([p for p in players if REGION.get(p["team"]) == r], avail)
        clubs = ", ".join(CLUB_NAMES[t] for t in REGION if REGION[t] == r)
        val_txt = f"{st['value']:.0f}" if st["value"] is not None else "–"
        reg_rows += (f"<tr><td><strong>{r}</strong><small class='opt' style='color:var(--muted);display:block'>{e(clubs)}</small></td><td class='n opt'>{st['n']}</td>"
                     f"<td class='n'>{compact(st['weekly'] / st['n']) if st['n'] else '–'}</td><td class='n ppm'>{money(st['ppm']) if st['ppm'] else '–'}</td>"
                     f"<td class='n opt'>{compact(st['per_goal']) if st['per_goal'] else '–'}</td><td class='n'>{val_txt}</td></tr>")
    region_html = ("<section><h2>" + ic("compass", "h-ic") + "Region by region</h2><div class='tscroll'><table class='wtable'><thead><tr><th>Region</th>"
                   "<th class='n opt'>Players</th><th class='n'>Avg wage</th><th class='n'>£ per min</th><th class='n opt'>Per goal</th><th class='n'>Value</th></tr></thead><tbody>"
                   + reg_rows + "</tbody></table></div></section>")
    drows = [r for r in CMP if r[0] in ("Weekly wages", "Pay per minute played", "Cost per goal", "Average value score", "Best value", "Most overpaid")]
    derby_html, derby_qas = "", []
    for title, a, b in DERBIES:
        A = group([p for p in players if p["team"] == a], avail)
        B = group([p for p in players if p["team"] == b], avail)
        verdict = "Not enough tracked players to call it."
        if A["ppm"] and B["ppm"]:
            hi, lo, hs, ls = (a, b, A, B) if A["ppm"] > B["ppm"] else (b, a, B, A)
            verdict = f"{poss(CLUB_NAMES[hi])} players cost {round((hs['ppm'] / ls['ppm'] - 1) * 100)}% more per minute than {poss(CLUB_NAMES[lo])}."
            derby_qas.append((f"Who pays more per minute in the {title}?", verdict))
        derby_html += (f"<section><h3 class='fact' style='font-size:clamp(20px,3vw,26px)'>{ic('swords')}{e(title)}: {e(CLUB_NAMES[a])} v {e(CLUB_NAMES[b])}</h3>"
                       f"<p class='lede'>{e(verdict)}</p>" + cmp_table([CLUB_NAMES[a], CLUB_NAMES[b]], [A, B], drows) + "</section>")
    qas = [("Do northern or southern Premier League clubs pay more?",
            f"Per minute actually played, the {dn} pays more: {money(dear['ppm'])} against {money(cheap['ppm'])} for the {cn}, {pct}% more."),
           ("Which half of the country gets better value from its footballers?",
            f"The {better_value}, with an average value score of {max(N['value'] or 0, S['value'] or 0):.0f} out of 100, which blends match rating with pay per minute.")] + derby_qas[:4]
    crumbs = [("Home", "/"), ("North v South", "/north-south-divide/")]
    body = (crumbs_html(crumbs)
            + f'<header class="ph"><div class="meta"><span>Premier League</span><span>{e(season)}</span><span>After gameweek {data["gameweek"]}</span></div>'
            + f"<h1>North v South</h1><p class='answer'>{answer}</p></header>"
            + "<section><h2>" + ic("compass", "h-ic") + "The divide in numbers</h2>" + cmp_table(["The North", "The South"], [N, S], CMP) + "</section>"
            + region_html + "<section><h2>" + ic("swords", "h-ic") + "Derby day</h2></section>" + derby_html + faq_html(qas)
            + f'<a class="cta" href="/#divide">{ic("compass")}Filter by position in the app</a>')
    title = f"North v South: which Premier League clubs pay more per minute? {season} | Pay Per Minute"
    desc = (f"The football north–south divide in wages. The {dn}'s Premier League players cost {pct}% more per minute played in {season}. "
            f"Plus Manchester, Merseyside, North London and Tyne–Wear derbies head to head.")
    return page(assets, path="/north-south-divide/", title=title, description=desc, body=body, current="/north-south-divide/",
                jsonld=[faq_ld(qas), crumbs_ld(crumbs)])


# ---------- write everything ----------

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def render(data=None):
    data = json.loads((HERE / "data.json").read_text(encoding="utf-8")) if data is None else json.loads(json.dumps(data))
    enrich(data)
    assets = shared_assets()
    players = data["players"]

    per_min = {}
    for team in CLUB_NAMES:
        squad, earned, minutes = club_stats(players, team)
        if squad and minutes:
            per_min[team] = earned / minutes
    ranks = {t: i + 1 for i, t in enumerate(sorted(per_min, key=lambda t: -per_min[t]))}

    OUT.mkdir(exist_ok=True)
    write(OUT / "index.html", (HERE / "index.html").read_text(encoding="utf-8"))
    shutil.copyfile(HERE / "data.json", OUT / "data.json.tmp"); (OUT / "data.json.tmp").replace(OUT / "data.json")
    if (HERE / "game.html").exists():
        write(OUT / "game" / "index.html", (HERE / "game.html").read_text(encoding="utf-8"))

    urls = ["/", "/premier-league-wages/"]
    write(OUT / "premier-league-wages" / "index.html", render_hub(assets, data, ranks))
    for team in ranks:
        write(OUT / "clubs" / slugify(CLUB_NAMES[team]) / "index.html", render_club(assets, data, team, ranks))
        urls.append(f"/clubs/{slugify(CLUB_NAMES[team])}/")
    live = set()
    for p in players:
        write(OUT / "players" / p["slug"] / "index.html", render_player(assets, data, p))
        urls.append(f"/players/{p['slug']}/")
        live.add(p["slug"])
    for old in (OUT / "players").iterdir():  # remove pages for players who have left
        if old.is_dir() and old.name not in live:
            shutil.rmtree(old, ignore_errors=True)
    if (OUT / "game" / "index.html").exists():
        urls.append("/game/")
    write(OUT / "north-south-divide" / "index.html", render_divide(assets, data))
    urls.append("/north-south-divide/")
    gws = data.get("gameweeks") or []
    if gws:
        write(OUT / "team-of-the-week" / "index.html", render_xi(assets, data, gws[-1], latest=True))
        urls.append("/team-of-the-week/")
        for g in gws:
            write(OUT / "team-of-the-week" / f"gameweek-{g['gw']}" / "index.html", render_xi(assets, data, g, latest=False))
            urls.append(f"/team-of-the-week/gameweek-{g['gw']}/")

    today = data["built_at"][:10]
    write(OUT / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{e(SITE_URL + u)}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    write(OUT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    print(f"Rendered {len(urls)} pages into {OUT.name}/", flush=True)


if __name__ == "__main__":
    render()
