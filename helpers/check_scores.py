import pymongo
from pymongo import MongoClient
import requests
import json
import time
import os
from urllib.parse import quote_plus

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

def close_games(games: pymongo.collection.Collection, pt_diff: int, time_remaining: float) -> list:
    return list(games.find(
        # constraints
        {"$and": [{"status.in_progress": True},{"status.period": 2},
                 {"status.time_remaining": {"$lte": time_remaining}},
                 {"difference": {"$lte": pt_diff}}]},
        # return
        {"_id": 1,"home.team": 1,"home.score": 1,"away.team": 1,"away.score": 1,
         "home.probability": 1, "away.probability": 1, "status.display_clock": 1}
        )
                )
                
def completed_games(games: pymongo.collection.Collection) -> list:
     return list(games.find(
         # constraints
         {"status.state": "Final"},
         # return
         {"_id": 1,"status.state":1,"home.team": 1,"home.score": 1,"away.team": 1,"away.score": 1}
         )
                 )

def check_scores(username, password, cluster, webhook_url):
    db = "march_madness_2022"
    uri = ("mongodb+srv://" + username + ":" + password + '@' + cluster + ".mongodb.net/" +
    db + "?retryWrites=true&w=majority")

    client =  MongoClient(uri)
    db = client.march_madness_2022
    games = db.games
    notifs = db.notifications
    errors = db.errors

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
            games.find_one_and_replace(filter = {"$and": [{"date":date},{"matchup":matchup}]},
                                    replacement = doc,
                                    upsert = True)

        # extract close games
        close_games = close_games(games, 6, 5*60)
        # extract completed games
        completed_games = completed_games(games)

        for game in close_games:
            if notifs.count_documents({"game": game["_id"]}) > 0:
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
                notifs.insert_one(make_notif_document(game, "Close Game", text))

        for game in completed_games:
            if notifs.count_documents({"$and": [{"game": game["_id"]}, {"type": "Final"}]}) > 0:
                continue
            else:
                teams = sorted([(game["home"]["team"], game["home"]["score"]),(game["away"]["team"], game["away"]["score"])], key = lambda x: x[1])
                text = f"FINAL: {teams[1][0]} {teams[1][1]} - {teams[0][0]} {teams[0][1]}"
                response = requests.post(
                    webhook_url,
                    data = json.dumps({"text":text}),
                    headers = {"Content-Type": "application/json"}
                )
                notifs.insert_one(make_notif_document(game, "Final", text))
    except Exception as e:
        errors.insert_one(make_error_document(repr(e)))