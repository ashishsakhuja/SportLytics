import threading
import time
import requests

URL = "https://api.sportlytics.net/analytics/teams/nfl/BUF/form?season=2025&season_type=REG&last=16"

TOTAL_REQUESTS = 200
TIMEOUT = 10

results = {
    "success": 0,
    "failed": 0,
    "status_codes": {}
}

lock = threading.Lock()


def hit_endpoint(request_number: int):
    try:
        response = requests.get(URL, timeout=TIMEOUT)
        with lock:
            results["success"] += 1
            code = response.status_code
            results["status_codes"][code] = results["status_codes"].get(code, 0) + 1
            print(f"[{request_number}] {code}")
    except Exception as e:
        with lock:
            results["failed"] += 1
            print(f"[{request_number}] FAILED: {e}")


def main():
    print(f"Starting load test on: {URL}")
    print(f"Sending {TOTAL_REQUESTS} concurrent requests...\n")

    start = time.time()
    threads = []

    for i in range(TOTAL_REQUESTS):
        t = threading.Thread(target=hit_endpoint, args=(i + 1,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    end = time.time()

    print("\n--- LOAD TEST COMPLETE ---")
    print(f"Elapsed time: {end - start:.2f} seconds")
    print(f"Successful requests: {results['success']}")
    print(f"Failed requests: {results['failed']}")
    print("Status codes:")
    for code, count in sorted(results["status_codes"].items()):
        print(f"  {code}: {count}")


if __name__ == "__main__":
    main()