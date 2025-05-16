import time
from typing import Dict, List, Optional
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Query
import httpx
import os
import requests

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Autoriser les requêtes depuis le frontend (Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Remplace "*" par ton domaine exact en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://api.steampowered.com"
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "steam-stats-collector/2.0"})

class SteamAPIError(RuntimeError):
    pass

def steam_get(interface: str, method: str, version: str = "v1", **params) -> Dict:
    params["key"] = STEAM_API_KEY
    url = f"{BASE_URL}/{interface}/{method}/{version}/"
    print(f"→ Appel API : {method} ({interface})", flush=True)
    resp = SESSION.get(url, params=params, timeout=10)
    try:
        resp.raise_for_status()
        return resp.json()
    except (ValueError, requests.RequestException) as exc:
        raise SteamAPIError(f"Steam API call failed: {url}\n→ {exc}") from exc

def get_player_name(steam_id: str) -> str:
    data = steam_get("ISteamUser", "GetPlayerSummaries", "v2", steamids=steam_id)
    return data["response"]["players"][0]["personaname"]

def get_steam_level(steam_id: str) -> int:
    data = steam_get("IPlayerService", "GetSteamLevel", "v1", steamid=steam_id)
    return data["response"]["player_level"]

def get_owned_games(steam_id: str) -> List[Dict]:
    data = steam_get("IPlayerService", "GetOwnedGames", "v1",
                    steamid=steam_id,
                    include_appinfo=True,
                    include_played_free_games=True)
    return data["response"].get("games", [])

def get_achievement_schema(appid: int) -> Optional[List[Dict]]:
    try:
        data = steam_get("ISteamUserStats", "GetSchemaForGame", "v2", appid=appid)
        return data["game"]["availableGameStats"].get("achievements")
    except Exception:
        return None

def get_player_achievements(appid: int, steam_id: str) -> Optional[Dict[str, int]]:
    try:
        data = steam_get("ISteamUserStats", "GetPlayerAchievements", "v1",
                        appid=appid, steamid=steam_id)
        achievements = data["playerstats"].get("achievements")
        if not achievements:
            return None
        return {a["apiname"]: a["achieved"] for a in achievements}
    except Exception:
        return None

def aggregate_playtime_and_counts(games: List[Dict]) -> tuple[float, int]:
    total_minutes = sum(g.get("playtime_forever", 0) for g in games)
    played_games = sum(1 for g in games if g.get("playtime_forever", 0) > 0)
    return round(total_minutes / 60.0, 1), played_games

def completion_percentage(games: List[Dict], steam_id: str,
                          achievement_data: List[Dict]) -> Optional[float]:
    unlocked_total, total_achievements = 0, 0

    for game in games:
        appid = game["appid"]
        name  = game.get("name", f"App {appid}")
        print(f"  • Analyse des succès : {name}", flush=True)
        schema = get_achievement_schema(appid)
        player = get_player_achievements(appid, steam_id)
        if not schema or not player:
            continue
        total = len(schema)
        unlocked = sum(player.values())
        total_achievements += total
        unlocked_total += unlocked
        achievement_data.append({
            "appid": appid,
            "name": name,
            "total_achievements": total,
            "unlocked": unlocked,
            "completion_percent": round(unlocked / total * 100, 2)
        })
        time.sleep(0.3)

    if total_achievements == 0:
        return None
    return round(unlocked_total / total_achievements * 100, 2)

def gather_player_stats(steam_id: str) -> tuple[Dict, List[Dict]]:
    print("\n--- Récupération des données Steam ---\n", flush=True)
    games = get_owned_games(steam_id)
    print(f"Jeux détectés : {len(games)}", flush=True)
    total_hours, played_games = aggregate_playtime_and_counts(games)
    achievement_data: List[Dict] = []

    summary = {
        "player_name": get_player_name(steam_id),
        "steam_level": get_steam_level(steam_id),
        "total_hours": total_hours,
        "played_games": played_games,
        "completion_percent": completion_percentage(games, steam_id, achievement_data),
    }

    return summary, achievement_data


@app.get("/steam/achievements")
async def get_achievements(steamid: str = Query(...), appid: str = Query(...)):
    url = "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steamid,
        "appid": appid
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        return response.json()
    
@app.get("/steam/datas")
async def get_datas(steamid: str = Query(...)):
    url = "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steamid
    }
    

    async with httpx.AsyncClient() as client:
        #response = await client.get(url, params=params)
        summary, details = gather_player_stats(steamid)
        return summary,details
    
@app.get("/steam/profile")
async def get_profile(steamid: str = Query(...)):
    async with httpx.AsyncClient() as client:
        #response = await client.get(url, params=params)
        profile, games = gather_player_stats(steamid)
        
    
        # AXE 1 – Progression Style
        high_completion_games = [g for g in games if g["completion_percent"] >= 80.0]
        avg_completion = profile["completion_percent"]

        if len(high_completion_games) >= 3:
            axis1 = "C"
            reason1 = f"{len(high_completion_games)} jeux avec >80% de succès."
            value1 = 1.0
        elif avg_completion < 30:
            axis1 = "F"
            reason1 = f"Moyenne de succès <30% ({avg_completion}%)."
            value1 = 0.3
        else:
            axis1 = "-"
            reason1 = f"Rien de dominant (moyenne = {avg_completion}%)."
            value1 = 0.5

        # AXE 2 – Challenge Nature
        story_based = ["Life is Strange", "The Witcher 3", "Assassin's Creed", "Little Nightmares"]
        mechanical_based = ["Hades", "Celeste", "Dark Souls", "Monster Hunter"]
        explorer_based = ["Skyrim", "Subnautica", "No Man's Sky", "Zelda", "Hollow Knight"]

        S = any(any(key in g["name"] for key in story_based) and g["completion_percent"] > 20 for g in games)
        M = any(any(key in g["name"] for key in mechanical_based) and g["completion_percent"] > 20 for g in games)
        E = any(any(key in g["name"] for key in explorer_based) and g["completion_percent"] > 20 for g in games)

        if S:
            axis2 = "S"
            reason2 = "Succès significatifs dans des jeux narratifs."
            value2 = 0.6
        elif M:
            axis2 = "M"
            reason2 = "Succès dans des jeux de skill."
            value2 = 0.6
        elif E:
            axis2 = "E"
            reason2 = "Succès dans des jeux d'exploration."
            value2 = 0.6
        else:
            axis2 = "-"
            reason2 = "Pas de tendance claire détectée."
            value2 = 0.3

        # AXE 3 – Social Orientation
        coop_games = ["Left 4 Dead", "Warframe", "PAYDAY 2", "Deep Rock Galactic"]
        pvp_games = ["Counter-Strike", "Paladins", "PUBG", "Apex Legends", "Dota"]

        T = any(any(name in g["name"] for name in coop_games) and g["completion_percent"] > 10 for g in games)
        C = any(any(name in g["name"] for name in pvp_games) and g["completion_percent"] > 5 for g in games)
        L = not (T or C)

        if T:
            axis3 = "T"
            reason3 = "Succès coop dans jeux multijoueur."
            value3 = 0.7
        elif C:
            axis3 = "C"
            reason3 = "Succès en PvP ou compétitifs."
            value3 = 0.6
        elif L:
            axis3 = "L"
            reason3 = "Pas de succès multijoueur visibles."
            value3 = 0.2
        else:
            axis3 = "-"
            reason3 = "Données multijoueur non interprétables."
            value3 = 0.3

        # AXE 4 – Rhythm / Engagement
        high_play_games = [g for g in games if g["completion_percent"] > 30]

        if profile["total_hours"] > 2000 and len(high_play_games) >= 5:
            axis4 = "H"
            reason4 = f"{profile['total_hours']}h au total + succès réguliers sur {len(high_play_games)} jeux."
            value4 = 1.0
        elif profile["total_hours"] > 500:
            axis4 = "B"
            reason4 = f"Activité modérée ({profile['total_hours']}h jouées)."
            value4 = 0.7
        else:
            axis4 = "D"
            reason4 = f"Peu de jeux joués ou complétés."
            value4 = 0.3

        # Résultat sous forme d'objet dict
        pcsr_result = {
            "type": f"{axis1}{axis2}{axis3}{axis4}",
            "axes": {
                "Progression Style": {"code": axis1, "reason": reason1, "score": value1},
                "Challenge Nature": {"code": axis2, "reason": reason2, "score": value2},
                "Social Orientation": {"code": axis3, "reason": reason3, "score": value3},
                "Rhythm / Engagement": {"code": axis4, "reason": reason4, "score": value4},
            }
        }

        return pcsr_result