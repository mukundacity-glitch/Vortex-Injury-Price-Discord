"""Three original Discord editorial editions within the EXISTING 15-minute injury monitor.

No Actions workflow, cron expression, secret, other bot, or ChatGPT task is changed.
Only a verified 12:00 / 14:00 / 17:00 America/New_York edition can post.
The first scheduled 15-minute check normally occurs at :07; later checks retry
a missed/held edition, never duplicate one with a confirmed Discord receipt.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import branded_renderer as branded

ET = ZoneInfo("America/New_York")
SLOTS = {
    12: ("fixture-targets", "NEXT GAMEWEEK • FIXTURE TARGETS"),
    14: ("transfer-advice", "TRANSFER ADVICE • SQUAD STRUCTURE"),
    17: ("decision-watch", "NEXT GAMEWEEK • DECISION WATCH"),
}
RECEIPTS = Path("data/branded_discord_deliveries.json")
SUMMARY = "https://fantasy.premierleague.com/api/element-summary/{}/"
PRIOR_PUBLIC_RECEIPTS = ("https://raw.githubusercontent.com/"
                         "mukundacity-glitch/Telegram-Bot/main/"
                         "state/ported_task_versions.json")


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _checked_get(session, url):
    response = session.get(url, headers={"Accept": "application/json"},
                           timeout=20)
    response.raise_for_status()
    return response.json()


def slot_for(now):
    """Never change the existing GitHub cron; route at the current ET hour."""
    local = now.astimezone(ET)
    if local.hour not in SLOTS:
        return None
    return SLOTS[local.hour]


def actionable_gw(data, now):
    """Require next flagged GW plus a real future deadline, not a guessed GW."""
    upcoming = [e for e in data.get("events", [])
                if e.get("is_next") and not e.get("finished")]
    if len(upcoming) != 1:
        raise RuntimeError("Official next actionable GW is ambiguous; no Discord edition")
    gw = upcoming[0]
    deadline = gw.get("deadline_time")
    if not deadline:
        raise RuntimeError("Official next GW deadline is missing")
    when = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    if when <= now.astimezone(timezone.utc):
        raise RuntimeError("Upcoming Gameweek deadline passed; hold edition")
    return int(gw["id"]), deadline


def _latest_finished(data):
    finished = [int(event["id"]) for event in data.get("events", [])
                if event.get("finished")]
    if not finished:
        raise RuntimeError("No completed GW to verify actual recent returns")
    return max(finished)


def _fixtures(fixtures, gw, team):
    games = [f for f in fixtures if f.get("event") == gw and
             team in (f.get("team_a"), f.get("team_h")) and
             not f.get("finished") and f.get("kickoff_time")]
    games.sort(key=lambda f: f["kickoff_time"])
    return games


def _difficulty(fixture, team):
    return fixture.get("team_h_difficulty" if fixture.get("team_h") == team
                       else "team_a_difficulty")


def _outside_already_published(session, date_et):
    """Best-effort external research, never claimed as shared/atomic dedup."""
    try:
        versions = _checked_get(session, PRIOR_PUBLIC_RECEIPTS)
        matches = []
        for entry in versions.values():
            if not entry.get("confirmed") or not entry.get("published_at"):
                continue
            published = datetime.fromisoformat(
                entry["published_at"].replace("Z", "+00:00")).astimezone(ET)
            if published.date().isoformat() == date_et:
                matches.extend(int(i) for i in entry.get("last_player_ids", []))
        print(f"Cross-repo confirmed player receipts consulted: {len(matches)}")
        return set(matches)
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        print(f"Cross-repo receipts not accessible ({type(exc).__name__}); "
              "cannot claim shared duplicate protection")
        return set()


def _ranked(data, fixtures, gw, edition, excluded):
    teams = {t["id"]: t for t in data.get("teams", [])}
    ranked = []
    for p in data.get("elements", []):
        if (p.get("id") in excluded or p.get("team") not in teams
                or not p.get("code") or not teams[p["team"]].get("code")
                or not p.get("element_type") in branded.POSITIONS
                or p.get("now_cost") is None or p.get("minutes") is None
                or p.get("selected_by_percent") is None):
            continue
        matches = _fixtures(fixtures, gw, p["team"])
        if not matches:
            continue
        fdr = _difficulty(matches[0], p["team"])
        if fdr not in (1, 2, 3, 4, 5):
            continue
        flagged = p.get("status") in ("d", "i", "s", "u")
        if edition != "decision-watch" and (p.get("status") != "a"
                                            or _num(p["minutes"]) < 180):
            continue
        if edition == "fixture-targets":
            score = (6 - fdr) * 5 + _num(p.get("form")) * 3
        elif edition == "transfer-advice":
            net = _num(p.get("transfers_in_event")) - _num(p.get("transfers_out_event"))
            if net <= 0:
                continue
            score = (6 - fdr) * 4 + _num(p.get("form")) * 2 + min(net / 15000, 25)
        else:
            if not flagged and _num(p["minutes"]) < 180:
                continue
            score = (100 if flagged else 0) + _num(p.get("selected_by_percent"))
        ranked.append((score, p, matches[0], fdr))
    ranked.sort(key=lambda x: (-x[0], x[1]["id"]))
    return ranked


def _verified_last_gw(session, player_id, gw):
    summary = _checked_get(session, SUMMARY.format(player_id))
    history = [h for h in summary.get("history", []) if h.get("round") == gw]
    if len(history) != 1:
        return None
    h = history[0]
    if h.get("total_points") is None or h.get("minutes") is None:
        return None
    return {"points": int(h["total_points"]), "minutes": int(h["minutes"])}


def _existing_edition(prefix):
    try:
        prior = json.loads(RECEIPTS.read_text()) if RECEIPTS.exists() else {}
        if not isinstance(prior, dict):
            raise ValueError("Receipt ledger must be an object")
    except (OSError, ValueError) as exc:
        raise RuntimeError("Cannot verify prior Discord delivery receipts") from exc
    return {key for key, value in prior.items()
            if key.startswith(prefix) and isinstance(value, dict)
            and value.get("message_id")}


def _opponent(fixture, club, teams):
    opponent = fixture["team_a"] if fixture["team_h"] == club else fixture["team_h"]
    return teams[opponent]["short_name"], "H" if fixture["team_h"] == club else "A"


def run_edition(bootstrap, future_fixtures, now=None, *, session=None):
    """Run from the existing scheduled monitor; no independent scheduling."""
    now = now or datetime.now(timezone.utc)
    scheduled = slot_for(now)
    if not scheduled:
        return "outside-edition"
    edition, title = scheduled
    date_et = now.astimezone(ET).date().isoformat()
    gw, deadline = actionable_gw(bootstrap, now)
    completed = _latest_finished(bootstrap)
    # This bot is explicitly scoped to the current 2026/27 season. The
    # duplicate key intentionally excludes the calendar day: identical
    # advice is NEVER republished merely because it is tomorrow.
    season_id = "2026-27"
    prefix = f"discorddaily:{season_id}:GW{gw}:{edition}:"
    prior_versions = _existing_edition(prefix)

    client = session or requests.Session()
    seen_elsewhere = _outside_already_published(client, date_et)
    clubs = {t["id"]: t for t in bootstrap.get("teams", [])}
    candidates = _ranked(bootstrap, future_fixtures, gw, edition, seen_elsewhere)
    picks = []
    used_clubs = set()
    for _, player, fixture, fdr in candidates[:24]:
        if len(picks) == 3:
            break
        if player["team"] in used_clubs:
            continue
        try:
            last = _verified_last_gw(client, player["id"], completed)
            if not last:
                continue
            # A MONITOR risk needs evidence: an actual FPL flag or a short
            # appearance in the last completed Gameweek.
            if (edition == "decision-watch" and player.get("status") == "a"
                    and last["minutes"] >= 60):
                continue
            if (edition != "decision-watch" and last["minutes"] < 60):
                continue
            # Verify live-authentic portrait AND crest before selecting a card.
            branded._current_verified_media(client, int(player["code"]), "photo")
            branded._current_verified_media(client, int(clubs[player["team"]]["code"]), "crest")
        except (requests.RequestException, RuntimeError, OSError, ValueError):
            continue
        action = "BUY" if edition in ("fixture-targets", "transfer-advice") else "MONITOR"
        picks.append({"id": player["id"], "player": player, "fixture": fixture,
                      "fdr": fdr, "last": last, "action": action})
        used_clubs.add(player["team"])

    if not picks:
        print(f"Discord {edition} held: no verified profiles with authentic media")
        return "held-unverified"

    first = picks[0]
    target = first["player"]
    opponent, ha = _opponent(first["fixture"], target["team"], clubs)
    action = first["action"]
    player_name = target.get("web_name") or target.get("second_name")
    headline = title.format(gw=gw)
    render_records = [
        {"id": item["id"],
         "action": f"{item['action']} • GW{completed} {item['last']['points']} pts"}
        for item in picks
    ]
    source_version = sha256(json.dumps({
        "fixture": [item["fixture"].get("id") for item in picks],
        "profiles": [(item["id"], item["player"].get("status"),
                      item["player"].get("news"), item["player"].get("now_cost"),
                      item["last"]["points"], item["last"]["minutes"])
                     for item in picks],
    }, sort_keys=True).encode()).hexdigest()[:20]
    identity = prefix + ":".join(str(i["id"]) for i in picks) + ":" + source_version
    if identity in prior_versions:
        print(f"Unchanged GW{gw} {edition} already delivered; no repeat")
        return "already-delivered"
    if prior_versions:
        headline = "UPDATED • " + headline

    flag = {"a": "FPL available", "d": "FPL doubt", "i": "FPL injured",
            "s": "FPL suspended", "u": "FPL unavailable"}
    if edition == "decision-watch":
        evidence = (f"{player_name}: {flag.get(target.get('status'), 'FPL flag')}; "
                    f"{first['last']['minutes']} GW{completed} mins.")
    elif edition == "transfer-advice":
        net = int(_num(target.get("transfers_in_event")) -
                  _num(target.get("transfers_out_event")))
        evidence = (f"{player_name}: net transfers {net:+,}; "
                    f"{first['last']['points']} GW{completed} pts.")
    else:
        evidence = (f"{player_name}: {first['last']['points']} pts, "
                    f"{first['last']['minutes']} mins in GW{completed}.")
    caption = "\n".join([
        f"GW{gw} | {headline}",
        evidence,
        f"Next: {opponent} ({ha}), FDR {first['fdr']}; deadline {deadline[:10]}.",
        f"{action} {player_name}; check team news. Follow FPL VORTEX.",
        f"#FPL #FPLCommunity #FPLVortex #GW{gw}",
    ])
    if len(caption.splitlines()) != 5:
        raise AssertionError("Five-line caption violated")

    # This will refuse any mismatched blue master, nonexistent team badge,
    # unavailable player photograph, or missing verified footer handle.
    artwork = branded.render_batches(
        f"GW{gw} • {headline}", render_records, bootstrap, future_fixtures,
        session=client)
    if any(im.size != (1920, 1080) for im in artwork):
        raise RuntimeError("Discord graphic failed the 1920×1080 size gate")
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    message_id, posted = branded.receipt_send(
        artwork, caption, identity, webhook, RECEIPTS, session=client)
    if posted:
        print(f"Discord posted GW{gw} {edition}, ID={message_id}, "
              f"source=official FPL, fetched={now.isoformat()}, "
              f"last_completed=GW{completed}, deadline={deadline}")
    return "posted" if posted else "already-delivered"
