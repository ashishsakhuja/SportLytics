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


def _standardize_nfl(raw: Dict[str, Any]) -> Dict[str, Any]:
    def g(*keys: str) -> Any:
        for k in keys:
            if k in raw:
                return raw.get(k)
        return None

    out: Dict[str, Any] = {}

    # --------------------------
    # PASSING: cmp / att handling
    # ESPN may provide:
    #  - combined "C/ATT" style
    #  - OR separate "Completions" and "Attempts"
    # --------------------------

    # 1) Combined C/ATT
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

    # 2) Separate completions / attempts
    if out.get("pass_cmp") is None:
        out["pass_cmp"] = _safe_int(
            g(
                "completions",
                "passing_completions",
                "pass_completions",
                "cmp",
                "comp",
            )
        )
    if out.get("pass_att") is None:
        out["pass_att"] = _safe_int(
            g(
                "attempts",
                "passing_attempts",
                "pass_attempts",
                "att",
                "pass_att",
            )
        )

    # Completion %
    if out.get("completion_pct") is None and out.get("pass_cmp") is not None and out.get("pass_att"):
        att = out["pass_att"]
        if att and att > 0:
            out["completion_pct"] = round((out["pass_cmp"] / att) * 100.0, 6)

    # Pass yards
    out["pass_yds"] = _safe_int(
        g(
            "passing_yards",
            "passingyards",
            "net_passing_yards",
            "netpassingyards",
            "pass_yards",
            "passyds",
            "pass_yds",
        )
    )

    # Rush attempts / yards
    out["rush_att"] = _safe_int(g("rushing_attempts", "rushingattempts", "rush_attempts", "rushatt", "rush_att"))
    out["rush_yds"] = _safe_int(g("rushing_yards", "rushingyards", "rush_yards", "rushyds", "rush_yds"))

    # Total yards
    out["total_yds"] = _safe_int(g("total_yards", "totalyards", "yds", "totalyds"))

    # Turnovers
    out["turnovers"] = _safe_int(g("turnovers", "to", "total_turnovers", "turnover"))

    # Sacks + yards lost (often "2-14")
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

    # Third down efficiency:
    # could be "7-13" OR could be percent already
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

    # Red zone efficiency:
    # could be "3-4" OR could be percent already
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

    # --------------------------
    # Derived metrics (once enough inputs exist)
    # --------------------------
    pass_att = out.get("pass_att")
    pass_yds = out.get("pass_yds")
    rush_att = out.get("rush_att")
    rush_yds = out.get("rush_yds")
    sacks = out.get("sacks")
    total_yds = out.get("total_yds")

    # ypa
    if out.get("ypa") is None and pass_att and pass_att > 0 and pass_yds is not None:
        out["ypa"] = round(pass_yds / pass_att, 6)

    # rypa
    if out.get("rypa") is None and rush_att and rush_att > 0 and rush_yds is not None:
        out["rypa"] = round(rush_yds / rush_att, 6)

    # dropbacks / pass rate / sack rate
    # (approx: dropbacks = pass_att + sacks)
    if pass_att is not None and rush_att is not None:
        dropbacks = pass_att + (sacks or 0)
        denom = dropbacks + rush_att
        if denom > 0:
            out["pass_rate"] = round(dropbacks / denom, 6)
        if dropbacks > 0 and sacks is not None:
            out["sack_rate"] = round(sacks / dropbacks, 6)

    # plays / ypp (approx offensive plays)
    if out.get("plays") is None and pass_att is not None and rush_att is not None:
        out["plays"] = int(pass_att + rush_att + (sacks or 0))
    if out.get("ypp") is None and out.get("plays") and total_yds is not None:
        plays = out["plays"]
        if plays and plays > 0:
            out["ypp"] = round(total_yds / plays, 6)

    # drop Nones
    return {k: v for k, v in out.items() if v is not None}


def _standardize_common(*, sport: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    sport = (sport or "").lower().strip()
    if sport == "nfl":
        return _standardize_nfl(raw)
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

        stats_list = t.get("statistics") or []
        for s in stats_list:
            name = (s.get("name") or "").strip()
            abbr = (s.get("abbreviation") or "").strip()

            value = s.get("displayValue")
            if value is None:
                value = s.get("value")

            if name:
                raw[_snake(name)] = value
            if abbr:
                raw[_snake(abbr)] = value

        standard = _standardize_common(sport=sport, raw=raw)

        out[team_code] = {
            **standard,
            "raw_stats": raw,
            "meta": {"sport": sport, "provider": "espn_summary"},
        }

    return out