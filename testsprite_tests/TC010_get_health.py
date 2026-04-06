import requests
from datetime import datetime, timezone

def test_get_health():
    base_url = "http://localhost:80"
    url = f"{base_url}/health/"
    try:
        response = requests.get(url, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed: {e}"
    assert response.status_code == 200, f"Expected status 200, got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Check required keys
    for key in ("status", "service", "timestamp"):
        assert key in data, f"Response JSON missing key '{key}'"

    assert data["status"] == "ok", f"Expected status 'ok', got {data['status']}"
    assert data["service"] == "franja_pixelada", f"Expected service 'franja_pixelada', got {data['service']}"

    timestamp_str = data["timestamp"]
    # Validate ISO8601 UTC timestamp (e.g. '2024-06-28T15:22:39Z' or '2024-06-28T15:22:39+00:00')
    try:
        # Try to parse timestamp as ISO8601. Using fromisoformat but it does not parse 'Z', so handle it:
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(timestamp_str)
    except Exception:
        assert False, f"Timestamp is not valid ISO8601 UTC: {data['timestamp']}"

    # Confirm timestamp is timezone-aware and in UTC
    assert dt.tzinfo is not None, "Timestamp is not timezone aware"
    assert dt.utcoffset() == timezone.utc.utcoffset(dt), "Timestamp is not in UTC"


test_get_health()