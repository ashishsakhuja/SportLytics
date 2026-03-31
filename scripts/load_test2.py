import requests

TEST_CASES = [
    {
        "name": "Invalid team code",
        "url": "https://api.sportlytics.net/analytics/teams/nfl/INVALIDTEAM/form?season=2025&season_type=REG&last=16"
    },
    {
        "name": "Invalid sport",
        "url": "https://api.sportlytics.net/analytics/teams/soccer/BUF/form?season=2025&season_type=REG&last=16"
    },
    {
        "name": "Huge last parameter",
        "url": "https://api.sportlytics.net/analytics/teams/nfl/BUF/form?season=2025&season_type=REG&last=100000"
    },
    {
        "name": "Negative last parameter",
        "url": "https://api.sportlytics.net/analytics/teams/nfl/BUF/form?season=2025&season_type=REG&last=-5"
    },
    {
        "name": "Non-numeric season",
        "url": "https://api.sportlytics.net/analytics/teams/nfl/BUF/form?season=hello&season_type=REG&last=16"
    },
    {
        "name": "Invalid season_type",
        "url": "https://api.sportlytics.net/analytics/teams/nfl/BUF/form?season=2025&season_type=FAKE&last=16"
    },
    {
        "name": "Missing query params",
        "url": "https://api.sportlytics.net/analytics/teams/nfl/BUF/form"
    },
]

TIMEOUT = 15

for i, test in enumerate(TEST_CASES, start=1):
    print(f"\n=== Test {i}: {test['name']} ===")
    print(f"URL: {test['url']}")
    try:
        response = requests.get(test["url"], timeout=TIMEOUT)
        print(f"Status Code: {response.status_code}")
        print("Response Preview:")
        print(response.text[:500])
    except Exception as e:
        print(f"FAILED TO CONNECT: {e}")