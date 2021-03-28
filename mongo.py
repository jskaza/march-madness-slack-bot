import time
import pymongo

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
