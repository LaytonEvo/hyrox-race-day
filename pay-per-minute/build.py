#!/usr/bin/env python3
"""Join reported wages (wages.csv) with live minutes from the Fantasy Premier League API.

Usage: python3 build.py [path/to/bootstrap-static.json]
Without an argument it downloads the FPL data. Writes data.json beside this file.
"""
import csv, re, json, sys, urllib.request, datetime, pathlib, statistics, unicodedata

HERE = pathlib.Path(__file__).resolve().parent
FPL_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
LIVE_URL = "https://fantasy.premierleague.com/api/event/{}/live/"
FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"
XI_MIN_MINUTES = 60  # a player needs this many minutes in a gameweek to be picked on merit
FORMATION = [("GK", 1), ("DEF", 4), ("MID", 3), ("FWD", 3)]
POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
LEFT_LEAGUE = re.compile(r"\bhas joined\b", re.I)  # FPL news for permanent moves and loans out


def left_league(e):
    """FPL keeps departed players in its list, marked unavailable with 'Has joined X ...' news."""
    return e["status"] == "u" and bool(LEFT_LEAGUE.search(e["news"]))


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


RATING_MIN_MINUTES = 270  # three full matches before a player counts towards the rating scale


def rating_scale(elements):
    """Mean and spread of BPS per 90 for each position, across every PL player with enough minutes."""
    scale = {}
    for pos in POSITIONS:
        vals = [e["bps"] / e["minutes"] * 90 for e in elements
                if e["element_type"] == pos and e["minutes"] >= RATING_MIN_MINUTES]
        if len(vals) >= 5:
            scale[pos] = (statistics.mean(vals), statistics.pstdev(vals) or 1)
    return scale


def rating(e, scale):
    """Turn BPS per 90 into a familiar 4-10 match rating: 6.5 is an average player in that position."""
    if not e["minutes"] or e["element_type"] not in scale:
        return None
    mean, sd = scale[e["element_type"]]
    z = (e["bps"] / e["minutes"] * 90 - mean) / sd
    return round(min(10.0, max(4.0, 6.5 + 0.9 * z)), 2)


def load_fpl(path=None):
    if path:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    req = urllib.request.Request(FPL_URL, headers={"User-Agent": "pay-per-minute/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def load_live(gw):
    req = urllib.request.Request(LIVE_URL.format(gw), headers={"User-Agent": "pay-per-minute/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def percentile_fn(values):
    vals = sorted(values)
    def f(v):
        if len(vals) < 2:
            return 50
        return (sum(x < v for x in vals) + (sum(x == v for x in vals) - 1) / 2) / (len(vals) - 1) * 100
    return f


def gameweek_teams(fpl, players, gws):
    """Value XI, Overpaid XI and Paid-to-watch XI for each finished gameweek (4-3-3)."""
    pos_of = {e["id"]: POSITIONS.get(e["element_type"]) for e in fpl["elements"]}
    tracked = {p["id"]: p for p in players}
    out = []
    for gw in gws:
        try:
            live = load_live(gw)
        except Exception as exc:  # one missing gameweek shouldn't stop the build
            print(f"GW{gw} live stats unavailable: {exc}")
            continue
        stats = {x["id"]: x["stats"] for x in live["elements"]}
        scale = {}
        for pos in POSITIONS.values():
            vals = [s["bps"] for pid, s in stats.items() if pos_of.get(pid) == pos and s["minutes"] >= XI_MIN_MINUTES]
            if len(vals) >= 5:
                scale[pos] = (statistics.mean(vals), statistics.pstdev(vals) or 1)
        rows = {}
        for pid, p in tracked.items():
            s = stats.get(pid, {})
            m = s.get("minutes", 0)
            r = None
            if m >= XI_MIN_MINUTES and p["pos"] in scale:
                mean, sd = scale[p["pos"]]
                r = round(min(10.0, max(4.0, 6.5 + 0.9 * (s["bps"] - mean) / sd)), 1)
            rows[pid] = {"id": pid, "m": m, "g": s.get("goals_scored", 0), "a": s.get("assists", 0),
                         "sv": s.get("saves", 0), "cs": s.get("clean_sheets", 0), "gc": s.get("goals_conceded", 0),
                         "og": s.get("own_goals", 0), "r": r}
        elig = [row for row in rows.values() if row["r"] is not None]
        r_pct = percentile_fn([row["r"] for row in elig])
        c_pct = percentile_fn([tracked[row["id"]]["weekly"] / row["m"] for row in elig])
        for row in elig:
            row["v"] = round((r_pct(row["r"]) + 100 - c_pct(tracked[row["id"]]["weekly"] / row["m"])) / 2)

        def team(cands, key):
            picked = []
            for pos, n in FORMATION:
                picked += [row["id"] for row in sorted((c for c in cands if tracked[c["id"]]["pos"] == pos), key=key)[:n]]
            return picked
        teams = {
            "value": team(elig, lambda row: (-row["v"], -row["r"])),
            "overpaid": team(elig, lambda row: (row["v"], -tracked[row["id"]]["weekly"])),
            "bench": team([row for row in rows.values() if row["m"] == 0], lambda row: -tracked[row["id"]]["weekly"]),
        }
        used = {pid for ids in teams.values() for pid in ids}
        out.append({"gw": gw, "teams": teams, "stats": {str(pid): rows[pid] for pid in used}})
    return out


def manager_records(fpl, season_start, built_at):
    """Join managers.csv with results from the FPL fixtures feed: games, points and pay during each manager's spell."""
    path = HERE / "managers.csv"
    if not path.exists():
        return []
    try:
        req = urllib.request.Request(FIXTURES_URL, headers={"User-Agent": "pay-per-minute/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            fixtures = [f for f in json.load(r) if f.get("finished") and f.get("kickoff_time")]
    except Exception as exc:
        print(f"Fixtures unavailable: {exc}")
        fixtures = []
    short = {t["id"]: t["short_name"] for t in fpl["teams"]}
    start0 = datetime.datetime.fromisoformat(season_start.replace("Z", "+00:00"))
    now = datetime.datetime.fromisoformat(built_at)
    day = lambda d: datetime.datetime.fromisoformat(d + "T00:00:00+00:00")
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            start = max(start0, day(row["start"])) if row["start"] else start0
            end = day(row["end"]) if row["end"] else now
            rec = {"team": row["team"], "name": row["manager"], "slug": slugify(row["manager"]),
                   "annual": int(row["annual_gbp"]) if row["annual_gbp"] else None, "source": row["source"],
                   "start": row["start"] or None, "end": row["end"] or None, "current": not row["end"],
                   "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0}
            for fx in fixtures:
                ko = datetime.datetime.fromisoformat(fx["kickoff_time"].replace("Z", "+00:00"))
                if not (start <= ko <= end):
                    continue
                if short.get(fx["team_h"]) == row["team"]:
                    us, them = fx["team_h_score"], fx["team_a_score"]
                elif short.get(fx["team_a"]) == row["team"]:
                    us, them = fx["team_a_score"], fx["team_h_score"]
                else:
                    continue
                rec["gf"] += us; rec["ga"] += them
                rec["w" if us > them else "d" if us == them else "l"] += 1
            rec["games"] = rec["w"] + rec["d"] + rec["l"]
            rec["pts"] = rec["w"] * 3 + rec["d"]
            rec["days"] = max(0.0, (min(end, now) - start).total_seconds() / 86400)
            rec["earned"] = rec["annual"] / 365 * rec["days"] if rec["annual"] else None
            out.append(rec)
    return out


def main(argv=None, render=False):
    argv = sys.argv[1:] if argv is None else argv
    fpl = load_fpl(argv[0] if argv else None)
    teams = {t["id"]: t for t in fpl["teams"]}
    by_key = {}
    for e in fpl["elements"]:
        by_key.setdefault((teams[e["team"]]["short_name"], e["web_name"]), []).append(e)

    events = fpl["events"]
    finished = [ev for ev in events if ev["finished"]]
    season_start = events[0]["deadline_time"]
    season = f"{season_start[:4]}/{int(season_start[2:4]) + 1:02d}"

    scale = rating_scale(fpl["elements"])
    players, missing, departed = [], [], []
    with open(HERE / "wages.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            matches = by_key.get((row["team"], row["player"]))
            if not matches or len(matches) > 1:
                missing.append(f'{row["team"]} {row["player"]}' + (" (ambiguous)" if matches else ""))
                continue
            e = matches[0]
            if left_league(e):
                departed.append(f'{row["team"]} {row["player"]}: {e["news"]}')
                continue
            players.append({
                "id": e["id"],
                "name": e["web_name"],
                "full_name": f'{e["first_name"]} {e["second_name"]}',
                "display": (e.get("known_name") or f'{e["first_name"]} {e["second_name"]}').strip(),
                "team": row["team"],
                "pos": POSITIONS.get(e["element_type"], "?"),
                "weekly": int(row["weekly_gbp"]),
                "source": row["source"],
                "minutes": e["minutes"],
                "starts": e["starts"],
                "goals": e["goals_scored"],
                "assists": e["assists"],
                "bps": e["bps"],
                "points": e["total_points"],
                "rating": rating(e, scale),
                "xgi": round(float(e["expected_goal_involvements"] or 0), 2),
                "tackles": e["tackles"],
                "recoveries": e["recoveries"],
                "cbi": e["clearances_blocks_interceptions"],
                "defcon": e["defensive_contribution"],
                "og": e["own_goals"],
                "saves": e["saves"],
                "cs": e["clean_sheets"],
                "pen_saves": e["penalties_saved"],
                "gc": e["goals_conceded"],
                "photo": e["photo"].replace(".jpg", ""),
                "status": e["status"],
                "news": e["news"],
            })

    seen = {}
    for p in players:  # stable, unique URL slugs for player pages
        base = slugify(p["display"]) or str(p["id"])
        slug = base if base not in seen else f'{base}-{p["team"].lower()}'
        seen[slug] = True
        p["slug"] = slug

    clubs = []
    for t in fpl["teams"]:
        squad = [e for e in fpl["elements"] if e["team"] == t["id"]]
        clubs.append({
            "short": t["short_name"],
            "name": t["name"],
            "played": t["played"] or None,
            "squad_minutes": sum(e["minutes"] for e in squad),
        })

    gameweeks = gameweek_teams(fpl, players, [ev["id"] for ev in finished])
    built_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    managers = manager_records(fpl, season_start, built_at)

    out = {
        "gameweeks": gameweeks,
        "season": season,
        "season_start": season_start,
        "gameweek": finished[-1]["id"] if finished else 0,
        "built_at": built_at,
        "managers": managers,
        "rating_min_minutes": RATING_MIN_MINUTES,
        "players": sorted(players, key=lambda p: -p["weekly"]),
        "clubs": clubs,
        "unmatched_wages": missing,
        "left_league": departed,
    }
    tmp = HERE / "data.json.tmp"  # write then rename, so the server never serves a half-written file
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(HERE / "data.json")
    if render:
        import site_pages
        site_pages.render(out)
    print(f"{len(players)} players written, GW{out['gameweek']}, {len(missing)} unmatched: {missing}, {len(departed)} left the league")


if __name__ == "__main__":
    main()
