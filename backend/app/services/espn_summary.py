from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.settings import settings

SPORT_TO_SUMMARY_URL = {
    "nfl": settings.ESPN_NFL_SUMMARY_URL,
    "nba": settings.ESPN_NBA_SUMMARY_URL,
    "mlb": settings.ESPN_MLB_SUMMARY_URL,
    "nhl": settings.ESPN_NHL_SUMMARY_URL,
}


def _snake(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.lower().strip("_")


def _parse_made_attempts(v: Any) -> Tuple[Optional[int], Optional[int]]:
    # supports "18/27" and "7-13"
    if v is None:
        return None, None
    s = str(v).strip()
    if not s:
        return None, None
    m = re.match(r"^(\d+)\s*[/\-]\s*(\d+)$", s)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        s = str(x).strip().replace(",", "")
        if not s:
            return None
        # avoid ratio strings like "7-13" and "18/27"
        if "/" in s or "-" in s:
            return None
        return int(float(s))
    except Exception:
        return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip().replace("%", "").replace(",", "")
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def _extract_team_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    box = (payload or {}).get("boxscore") or {}
    teams = box.get("teams") or []
    return teams if isinstance(teams, list) else []


def _iter_stat_entries(node: Any):
    """
    ESPN is inconsistent: team stats can be flat OR nested by categories.
    Yield leaf dicts that contain (name/abbreviation/label) and (displayValue/value).
    """
    if node is None:
        return

    if isinstance(node, list):
        for item in node:
            yield from _iter_stat_entries(item)
        return

    if isinstance(node, dict):
        # Leaf stat
        if ("displayValue" in node or "value" in node) and (
            "name" in node or "abbreviation" in node or "label" in node
        ):
            yield node
            return

        # Known containers
        for k in ("statistics", "stats", "categories", "splits", "items", "entries"):
            child = node.get(k)
            if isinstance(child, (list, dict)):
                yield from _iter_stat_entries(child)


def _find_players_totals_nfl(payload: Dict[str, Any], team_code: str) -> Dict[str, Any]:
    """
    Fallback when teams[].statistics doesn't include C/ATT.
    Looks in boxscore.players for the team's 'passing' category totals and parses C/ATT.
    """
    box = (payload or {}).get("boxscore") or {}
    players = box.get("players") or []
    if not isinstance(players, list):
        return {}

    team_code = (team_code or "").upper().strip()
    if not team_code:
        return {}

    for team_block in players:
        team = (team_block or {}).get("team") or {}
        abbr = (team.get("abbreviation") or "").upper().strip()
        if abbr != team_code:
            continue

        stats_cats = team_block.get("statistics") or []
        if not isinstance(stats_cats, list):
            continue

        for cat in stats_cats:
            cat_name = (cat.get("name") or "").lower().strip()
            if cat_name != "passing":
                continue

            labels = cat.get("labels") or []
            totals = cat.get("totals") or []
            if not isinstance(labels, list) or not isinstance(totals, list):
                continue

            # Find a "C/ATT"-type label
            target_idx = None
            for i, lab in enumerate(labels):
                lab_s = (str(lab) or "").strip().lower()
                if lab_s in {"c/att", "c-att", "comp-att", "completions-attempts", "cmp-att"}:
                    target_idx = i
                    break

            if target_idx is not None and target_idx < len(totals):
                v = totals[target_idx]
                return {"c_att": v}

    return {}


def _standardize_nfl(raw: Dict[str, Any]) -> Dict[str, Any]:
    def g(*keys: str) -> Any:
        for k in keys:
            if k in raw:
                return raw.get(k)
        return None

    out: Dict[str, Any] = {}

    # Combined C/ATT
    ca = g(
        "completions_attempts",
        "completion_attempts",
        "passing_completions_attempts",
        "pass_completions_attempts",
        "c_att",
        "cmp_att",
        "comp_att",
        "c_a",
        "comp_att_total",
        "cmp_att_total",
    )
    if ca:
        cmp_, att_ = _parse_made_attempts(ca)
        if cmp_ is not None:
            out["pass_cmp"] = cmp_
        if att_ is not None:
            out["pass_att"] = att_

    # Separate completions/attempts
    if out.get("pass_cmp") is None:
        out["pass_cmp"] = _safe_int(g("completions", "passing_completions", "pass_completions", "cmp", "comp"))
    if out.get("pass_att") is None:
        out["pass_att"] = _safe_int(g("attempts", "passing_attempts", "pass_attempts", "att", "pass_att"))

    if out.get("completion_pct") is None and out.get("pass_cmp") is not None and out.get("pass_att"):
        att = out["pass_att"]
        if att and att > 0:
            out["completion_pct"] = round((out["pass_cmp"] / att) * 100.0, 6)

    out["pass_yds"] = _safe_int(
        g("passing_yards", "passingyards", "net_passing_yards", "netpassingyards", "pass_yards", "passyds", "pass_yds")
    )

    out["rush_att"] = _safe_int(g("rushing_attempts", "rushingattempts", "rush_attempts", "rushatt", "rush_att"))
    out["rush_yds"] = _safe_int(g("rushing_yards", "rushingyards", "rush_yards", "rushyds", "rush_yds"))

    out["total_yds"] = _safe_int(g("total_yards", "totalyards", "yds", "totalyds"))
    out["turnovers"] = _safe_int(g("turnovers", "to", "total_turnovers", "turnover"))

    sacks_combo = g(
        "sacks_yards_lost",
        "sacksyardslost",
        "sacks_yl",
        "sacks_y_l",
        "sacks_yds_lost",
        "qb_sacks_yards_lost",
        "sacks_yards",
    )
    if sacks_combo:
        s_cnt, s_yl = _parse_made_attempts(sacks_combo)
        if s_cnt is not None:
            out["sacks"] = s_cnt
        if s_yl is not None:
            out["sacks_yards_lost"] = s_yl
    else:
        out["sacks"] = _safe_int(g("sacks", "qb_sacks"))

    td = g(
        "third_down_eff",
        "third_down_efficiency",
        "thirddowneff",
        "thirddownefficiency",
        "3rd_down_eff",
        "third_down_conversions_attempts",
        "third_down",
        "third_down_conv",
        "third_down_pct",
    )
    if td:
        made, att = _parse_made_attempts(td)
        if made is not None and att and att > 0:
            out["third_down_pct"] = round((made / att) * 100.0, 6)
        else:
            pct = _safe_float(td)
            if pct is not None:
                out["third_down_pct"] = round(pct, 6)

    rz = g(
        "red_zone_eff",
        "red_zone_efficiency",
        "redzoneeff",
        "redzoneefficiency",
        "red_zone",
        "rz_eff",
        "rz",
        "red_zone_td_pct",
    )
    if rz:
        made, att = _parse_made_attempts(rz)
        if made is not None and att and att > 0:
            out["red_zone_td_pct"] = round((made / att) * 100.0, 6)
        else:
            pct = _safe_float(rz)
            if pct is not None:
                out["red_zone_td_pct"] = round(pct, 6)

    # Derived
    pass_att = out.get("pass_att")
    pass_yds = out.get("pass_yds")
    rush_att = out.get("rush_att")
    rush_yds = out.get("rush_yds")
    sacks = out.get("sacks")
    total_yds = out.get("total_yds")

    if out.get("ypa") is None and pass_att and pass_att > 0 and pass_yds is not None:
        out["ypa"] = round(pass_yds / pass_att, 6)
    if out.get("rypa") is None and rush_att and rush_att > 0 and rush_yds is not None:
        out["rypa"] = round(rush_yds / rush_att, 6)

    if pass_att is not None and rush_att is not None:
        dropbacks = pass_att + (sacks or 0)
        denom = dropbacks + rush_att
        if denom > 0:
            out["pass_rate"] = round(dropbacks / denom, 6)
        if dropbacks > 0 and sacks is not None:
            out["sack_rate"] = round(sacks / dropbacks, 6)

    if out.get("plays") is None and pass_att is not None and rush_att is not None:
        out["plays"] = int(pass_att + rush_att + (sacks or 0))
    if out.get("ypp") is None and out.get("plays") and total_yds is not None:
        plays = out["plays"]
        if plays and plays > 0:
            out["ypp"] = round(total_yds / plays, 6)

    return {k: v for k, v in out.items() if v is not None}


def _standardize_nba(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Standardize NBA team boxscore stats across ESPN naming inconsistencies.

    Output fields are compact + numeric so the frontend can compute derived metrics.
    """

    def g(*keys: str) -> Any:
        for k in keys:
            if k in raw:
                return raw.get(k)
        return None

    out: Dict[str, Any] = {}

    # Shooting (made/attempts)
    fg = g(
        "fg",
        "field_goals",
        "fieldgoals",
        "field_goals_made_attempted",
        "field_goals_made_attempts",
        "fgm_fga",
        "fgm_a",
    )
    if fg:
        m, a = _parse_made_attempts(fg)
        if m is not None:
            out["fg_m"] = m
        if a is not None:
            out["fg_a"] = a

    tp = g(
        "3pt",
        "3ptfg",
        "3ptfgs",
        "three_point_field_goals",
        "three_point_field_goals_made_attempted",
        "three_point",
        "3pm_3pa",
        "3pm_a",
    )
    if tp:
        m, a = _parse_made_attempts(tp)
        if m is not None:
            out["tp_m"] = m
        if a is not None:
            out["tp_a"] = a

    ft = g(
        "ft",
        "free_throws",
        "freethrows",
        "free_throws_made_attempted",
        "ftm_fta",
        "ftm_a",
    )
    if ft:
        m, a = _parse_made_attempts(ft)
        if m is not None:
            out["ft_m"] = m
        if a is not None:
            out["ft_a"] = a

    # Percentages (fallback to computed)
    out["fg_pct"] = _safe_float(
        g("fg%", "fg_pct", "field_goal_pct", "field_goals_pct", "field_goal_percentage")
    )
    out["tp_pct"] = _safe_float(g("3pt%", "3pt_pct", "three_point_pct", "three_point_percentage"))
    out["ft_pct"] = _safe_float(g("ft%", "ft_pct", "free_throw_pct", "free_throw_percentage"))

    if out.get("fg_pct") is None and out.get("fg_m") is not None and out.get("fg_a"):
        a = out["fg_a"]
        if a and a > 0:
            out["fg_pct"] = round((out["fg_m"] / a) * 100.0, 6)
    if out.get("tp_pct") is None and out.get("tp_m") is not None and out.get("tp_a"):
        a = out["tp_a"]
        if a and a > 0:
            out["tp_pct"] = round((out["tp_m"] / a) * 100.0, 6)
    if out.get("ft_pct") is None and out.get("ft_m") is not None and out.get("ft_a"):
        a = out["ft_a"]
        if a and a > 0:
            out["ft_pct"] = round((out["ft_m"] / a) * 100.0, 6)

    # Counting stats
    out["oreb"] = _safe_int(g("off_reb", "offensive_rebounds", "oreb", "or"))
    out["dreb"] = _safe_int(g("def_reb", "defensive_rebounds", "dreb", "dr"))
    out["reb"] = _safe_int(g("reb", "rebound", "rebounds", "trb", "total_rebounds"))
    out["ast"] = _safe_int(g("ast", "assists", "assist"))
    out["tov"] = _safe_int(g("to", "tov", "turnovers", "turnover"))
    out["stl"] = _safe_int(g("stl", "steals", "steal"))
    out["blk"] = _safe_int(g("blk", "blocks", "block"))
    out["pf"] = _safe_int(g("pf", "personal_fouls", "fouls"))

    # Possessions estimate: Poss ≈ FGA + 0.44*FTA - OREB + TOV
    fga = out.get("fg_a")
    fta = out.get("ft_a")
    oreb = out.get("oreb")
    tov = out.get("tov")
    if fga is not None and fta is not None and tov is not None:
        poss = float(fga) + 0.44 * float(fta) + float(tov) - float(oreb or 0)
        if poss > 0:
            out["possessions_est"] = round(poss, 6)

    return {k: v for k, v in out.items() if v is not None}


def _standardize_common(*, sport: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    sport = (sport or "").lower().strip()
    if sport == "nfl":
        return _standardize_nfl(raw)
    if sport == "nba":
        return _standardize_nba(raw)
    return {}


async def fetch_espn_summary(*, sport: str, event_id: str) -> Dict[str, Any]:
    sport = (sport or "").lower().strip()
    base = SPORT_TO_SUMMARY_URL.get(sport)
    if not base:
        raise ValueError(f"Unsupported sport for ESPN summary: {sport}")

    url = base
    if "{event_id}" in base:
        url = base.format(event_id=event_id)

    if "event=" not in url:
        joiner = "&" if "?" in url else "?"
        url = f"{url}{joiner}event={event_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


def parse_team_boxscore_stats(payload: Dict[str, Any], *, sport: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    teams = _extract_team_rows(payload)

    for t in teams:
        team = t.get("team") or {}
        team_code = (team.get("abbreviation") or "").strip().upper()
        if not team_code:
            continue

        raw: Dict[str, Any] = {}

        stats_node = t.get("statistics")
        for s in _iter_stat_entries(stats_node):
            if not isinstance(s, dict):
                continue

            name = (s.get("name") or "").strip() or (s.get("label") or "").strip()
            abbr = (s.get("abbreviation") or "").strip()

            value = s.get("displayValue")
            if value is None:
                value = s.get("value")

            if name:
                raw[_snake(name)] = value
            if abbr:
                raw[_snake(abbr)] = value

        # NFL-only fallback: pull C/ATT from players totals if missing
        if sport.lower().strip() == "nfl":
            if not any(k in raw for k in ("c_att", "cmp_att", "comp_att", "completions_attempts", "completion_attempts")):
                raw.update(_find_players_totals_nfl(payload, team_code))

        standard = _standardize_common(sport=sport, raw=raw)

        out[team_code] = {
            **standard,
            "raw_stats": raw,
            "meta": {"sport": sport, "provider": "espn_summary"},
        }

    return out