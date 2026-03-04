import asyncio
from app.services.espn_summary import fetch_espn_summary

async def go():
    j = await fetch_espn_summary(sport="nfl", event_id="401772510")
    print("TOP KEYS:", list(j.keys()))
    box = j.get("boxscore")
    print("HAS BOXSCORE:", bool(box))
    if box:
        print("BOXSCORE KEYS:", list(box.keys()))
        print("TEAMS TYPE:", type(box.get("teams")))
        print("PLAYERS TYPE:", type(box.get("players")))
        teams = box.get("teams") or []
        players = box.get("players") or []
        print("TEAMS LEN:", len(teams))
        print("PLAYERS LEN:", len(players))
        if teams:
            print("FIRST TEAM KEYS:", list(teams[0].keys()))
            print("FIRST TEAM statistics len:", len((teams[0].get("statistics") or [])))
        if players:
            print("FIRST PLAYERS KEYS:", list(players[0].keys()))

asyncio.run(go())