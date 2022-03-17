from helpers import check_scores
from urllib.parse import quote_plus

def execute_check_scores(event, context):
    username = quote_plus(os.environ.get("MONGO_USERNAME"))
    password = quote_plus(os.environ.get("MONGO_PASSWORD"))
    cluster = os.environ.get("MONGO_CLUSTER")
    webhook_url = os.environ.get("SLACK_WEBHOOK")
    check_scores(username, password, cluster, webhook_url)
