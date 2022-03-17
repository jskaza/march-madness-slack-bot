# march-madness-slack-bot

## Description
- Send messages to a Slack Channel for close games and final scores from the NCAAM tournament
- Data pulled from ESPN API: http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard
- Run as a `cron` job every 10 minutes
- Environment variables:
    - `SLACK_WEBHOOK`: Slack weebhook URL

## Architecture
- App code connected to Google Cloud using Cloud Source Repository
- `execute_check_scores` in `main.py` hosted as a Google Cloud Function
    - Scores, Notifications, Errors stored in a Google Firestore Database
- Function executions scheduled using Google Cloud Scheduler
    - `*/10 * * * *`

