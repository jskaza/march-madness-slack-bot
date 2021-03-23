import pymongo
from pymongo import MongoClient
import requests
import json
import time
import os
from mongo import *

# pymongo configuration
client = MongoClient(os.environ.get("MONGO_STRING"))
db = client.march_madness_2021
games = db.games
notifs = db.notifications
errors = db.errors

# slack webhook url
webhook_url = os.environ.get("SLACK_WEBHOOK")

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
    close_games = close_games(games, 10, 10*60)
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
                    f"{teams[1][0]} has a {round(100*teams[1][2], 3)}% chance of winning"
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
