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

def _parse_made_attempts(s: str) -> Tuple[Optional[int], Optional[int]]:
    if not s:
        return None, None
    m = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*$", str(s))
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))

def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(float(str(x).strip()))
    except Exception:
        return None

def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip().replace("%", "")
        return float(s)
    except Exception:
        return None

async def fetch_espn_summary(*, sport: str, event_id: str) -> Dict[str, Any]:
    sport = (sport or "").lower().strip()
    url = SPORT_TO_SUMMARY_URL.get(sport)
    if not url:
        raise ValueError(f"Unsupported sport: {sport}")
    async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": "SportLytics/1.0"}) as client:
        r = await client.get(url, params={"event": event_id})
        r.raise_for_status()
        return r.json()

def _extract_team_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    box = payload.get("boxscore") or {}
    teams = box.get("teams") or []
    return teams if isinstance(teams, list) else []

def _standardize_common_stats(*, sport: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    def g(*keys: str) -> Any:
        for k in keys:
            if k in raw:
                return raw.get(k)
        return None

    out: Dict[str, Any] = {}
    sport = sport.lower().strip()

    if sport == "nfl":
        ca = g("completions_attempts", "completionsattempts")
        if ca:
            cmp_, att_ = _parse_made_attempts(str(ca))
            if cmp_ is not None: out["pass_cmp"] = cmp_
            if att_ is not None: out["pass_att"] = att_
            if cmp_ is not None and att_: out["completion_pct"] = round((cmp_ / att_) * 100.0, 3)

        out["pass_yds"] = _safe_int(g("passing_yards", "passingyards"))
        out["rush_yds"] = _safe_int(g("rushing_yards", "rushingyards"))
        out["total_yds"] = _safe_int(g("total_yards", "totalyards"))
        out["turnovers"] = _safe_int(g("turnovers"))

        td = g("third_down_eff", "thirddowneff")
        if td:
            made, att = _parse_made_attempts(str(td))
            if made is not None and att and att > 0:
                out["third_down_pct"] = round((made / att) * 100.0, 3)

        rz = g("red_zone_eff", "redzoneeff")
        if rz:
            made, att = _parse_made_attempts(str(rz))
            if made is not None and att and att > 0:
                out["red_zone_td_pct"] = round((made / att) * 100.0, 3)

    if sport == "nba":
        fg = g("field_goals_made_field_goals_attempted")
        if fg:
            m,a = _parse_made_attempts(str(fg))
            out["fgm"], out["fga"] = m, a

        tp = g("three_point_field_goals_made_three_point_field_goals_attempted")
        if tp:
            m,a = _parse_made_attempts(str(tp))
            out["tpm"], out["tpa"] = m, a

        ft = g("free_throws_made_free_throws_attempted")
        if ft:
            m,a = _parse_made_attempts(str(ft))
            out["ftm"], out["fta"] = m, a

        out["reb"] = _safe_int(g("rebounds"))
        out["oreb"] = _safe_int(g("offensive_rebounds"))
        out["ast"] = _safe_int(g("assists"))
        out["tov"] = _safe_int(g("turnovers"))

        out["fg_pct"] = _safe_float(g("field_goal_percentage"))
        out["tp_pct"] = _safe_float(g("three_point_percentage"))
        out["ft_pct"] = _safe_float(g("free_throw_percentage"))

    if sport == "nhl":
        out["shots_for"] = _safe_int(g("shots"))
        out["hits"] = _safe_int(g("hits"))
        out["blocks"] = _safe_int(g("blocked_shots", "blockedshots"))
        out["pim"] = _safe_int(g("penalty_minutes", "penaltyminutes"))
        out["faceoff_pct"] = _safe_float(g("faceoff_win_percentage", "faceoffwinpercentage"))

    if sport == "mlb":
        out["hits"] = _safe_int(g("hits"))
        out["errors"] = _safe_int(g("errors"))
        out["walks"] = _safe_int(g("walks"))
        out["strikeouts"] = _safe_int(g("strikeouts"))

    return {k:v for k,v in out.items() if v is not None}

def parse_team_boxscore_stats(payload: Dict[str, Any], *, sport: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for t in _extract_team_rows(payload):
        team = t.get("team") or {}
        team_code = (team.get("abbreviation") or "").strip().upper()
        if not team_code:
            continue

        raw: Dict[str, Any] = {}
        for s in (t.get("statistics") or []):
            name = s.get("name") or s.get("abbreviation") or ""
            key = _snake(name)
            if not key:
                continue
            v = s.get("value")
            if v is None:
                v = s.get("displayValue")
            raw[key] = v

        standard = _standardize_common_stats(sport=sport, raw=raw)
        out[team_code] = {**standard, "raw_stats": raw, "meta": {"sport": sport, "provider": "espn_summary"}}
    return out