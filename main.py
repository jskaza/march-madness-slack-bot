from distutils.command import check
from urllib.parse import quote_plus
import os
import requests
import json
import time
import firebase_admin
from firebase_admin import credentials, firestore

def make_game_document(game:list) -> dict:
    entry = {}
    entry["status"] = {}
    entry["status"]["last_updated"] = time.time()
    entry["status"]["period"] = game["competitions"][0]["status"]["period"]
    entry["status"]["time_remaining"] = game["competitions"][0]["status"]["clock"]
    entry["status"]["display_clock"] = game["competitions"][0]["status"]["displayClock"]
    entry["status"]["in_progress"] = game["competitions"][0]["status"]["type"]["state"] == "in"
    entry["status"]["state"] = game["competitions"][0]["status"]["type"]["shortDetail"]
    entry["date"] = game["competitions"][0]["date"]
    entry["matchup"] = game["name"]
    entry["short_name"] = game["shortName"]
    for team in game["competitions"][0]["competitors"]:
        home_away = team["homeAway"]
        entry[home_away] = {}
        entry[home_away]["team"] = team["team"]["shortDisplayName"]
        entry[home_away]["score"] = int(team["score"])
        if entry["status"]["in_progress"]:
            probs = game["competitions"][0]["situation"]["lastPlay"]["probability"]
            if home_away == "home":
                entry[home_away]["probability"] = probs["homeWinPercentage"]
            if home_away == "away":
                entry[home_away]["probability"] = probs["awayWinPercentage"]
    entry["difference"] = abs(entry["home"]["score"] - entry["away"]["score"])
    return(entry)

def make_notif_document(game: dict, type: str, message: str) -> dict:
    entry = {}
    entry["game"] = game["_id"]
    entry["time_sent"] = time.time()
    entry["type"] = type
    entry["message"] = message
    return(entry)

def make_error_document(error: str) -> dict:
    entry = {}
    entry["time"] = time.time()
    entry["error"] = error
    return(entry)

def close_games(games, pt_diff: int) -> list:
    docs = games.where("status.in_progress", "==", True).where("status.period", "==", 2).where("difference", "<", pt_diff).stream()
    res = []
    for doc in docs:
        d = doc.to_dict()
        d["_id"]= doc.id
        res.append(d)
    return(res)
       
def completed_games(games) -> list:
    docs = games.where("status.state", "==", "Final").stream()
    res = []
    for doc in docs:
        d = doc.to_dict()
        d["_id"]= doc.id
        res.append(d)
    return(res)

def check_scores(creds, games_collection, notifs_collection, errors_collection, webhook_url):
    # try:
    firebase_admin.initialize_app(creds)
    db = firestore.client()
    games = db.collection(games_collection)
    notifs = db.collection(notifs_collection)
    errors = db.collection(errors_collection)

    # espn api
    URL = "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

    try:
        # dict_keys(['leagues', 'groups', 'events', 'eventsDate'])
        scores = requests.get(URL).json()

        # list of games
        # each game:
        # dict_keys(['id', 'uid', 'date', 'name', 'shortName', 'season', 'competitions', 'links', 'status'])
        espn_games = scores["events"]

        documents = [make_game_document(game) for game in espn_games]
        for doc in documents:
            date = doc["date"]
            matchup = doc["matchup"]
            games.document(f"{date}_{matchup}").set(doc)

        # extract close games
        close_games_list = close_games(games, 6)
        # extract completed games
        completed_games_list = completed_games(games)

        for game in close_games_list:
            if len(notifs.where("game", "==", game["_id"]).get()) > 0:
                continue
            else:
                teams = sorted([(game["home"]["team"], game["home"]["score"], game["home"]["probability"]),
                                (game["away"]["team"], game["away"]["score"], game["away"]["probability"])],
                                key = lambda x: x[1])
                text = (f"CLOSE GAME: {teams[1][0]} {teams[1][1]} - {teams[0][0]} {teams[0][1]}\n"
                        f'{game["status"]["display_clock"]} remaining\n'
                        f"{teams[1][0]} has a {round(100*teams[1][2], 1)}% chance of winning"
                        )
                response = requests.post(
                    webhook_url,
                    data = json.dumps({"text":text}),
                    headers = {"Content-Type": "application/json"}
                )
                notifs.document().set(make_notif_document(game, "Close Game", text))

        for game in completed_games_list:
            if len(notifs.where("game", "==", game["_id"]).where("type", "==", "Final").get()) > 0:
                continue
            else:
                teams = sorted([(game["home"]["team"], game["home"]["score"]),(game["away"]["team"], game["away"]["score"])], key = lambda x: x[1])
                text = f"FINAL: {teams[1][0]} {teams[1][1]} - {teams[0][0]} {teams[0][1]}"
                response = requests.post(
                    webhook_url,
                    data = json.dumps({"text":text}),
                    headers = {"Content-Type": "application/json"}
                )
                notifs.document().set(make_notif_document(game, "Final", text))
    except Exception as e:
        errors.document().set(make_error_document(repr(e)))



creds = credentials.Certificate("service_account_key.json")

def execute_check_scores(event, context):
    check_scores(creds, "games", "notifs", "errors", os.environ.get("SLACK_WEBHOOK"))
