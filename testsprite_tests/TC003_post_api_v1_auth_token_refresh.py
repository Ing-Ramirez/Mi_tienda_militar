import requests
import time
from datetime import datetime

BASE_URL = "http://localhost:80/api/v1"
TIMEOUT = 30

def test_post_api_v1_auth_token_refresh():
    session = requests.Session()
    try:
        # Step 1: Register a new user to get refresh_token cookie set
        timestamp = int(time.time() * 1000)
        email = f"user_{timestamp}@test.com"
        password = "Xq7!mZ2#vL9"
        register_url = f"{BASE_URL}/auth/register/"
        register_payload = {
            "email": email,
            "first_name": "Test",
            "last_name": "User",
            "password": password,
            "password2": password
        }
        register_resp = session.post(register_url, json=register_payload, timeout=TIMEOUT)
        assert register_resp.status_code == 201, f"Register failed: {register_resp.text}"
        register_data = register_resp.json()
        assert "access" in register_data, "Access token missing in register response"
        # The session now should contain the refresh_token cookie set by the server

        # Step 2: Call token refresh endpoint with refresh_token cookie present
        refresh_url = f"{BASE_URL}/auth/token/refresh/"
        refresh_resp = session.post(refresh_url, timeout=TIMEOUT)
        assert refresh_resp.status_code == 200, f"Token refresh with cookie failed: {refresh_resp.text}"
        refresh_data = refresh_resp.json()
        assert "access" in refresh_data, "Access token missing in token refresh response"

        # Step 3: Call token refresh endpoint without any cookies (new session) -> expect 401 and Spanish message
        session_no_cookie = requests.Session()
        no_cookie_resp = session_no_cookie.post(refresh_url, timeout=TIMEOUT)
        assert no_cookie_resp.status_code == 401, f"Expected 401 on token refresh without cookie, got {no_cookie_resp.status_code}"
        error_json = no_cookie_resp.json()
        detail = error_json.get("detail", "")
        detail_lower = detail.lower()
        assert "no hay" in detail_lower or "sesi" in detail_lower, \
            f"Spanish error message expected 'no hay' or 'sesi', got: {detail}"

    finally:
        # Cleanup: There is no documented delete user endpoint, so no cleanup for the registered user.
        # If an admin API were available, we would delete the created user here.
        session.close()
        session_no_cookie.close()

test_post_api_v1_auth_token_refresh()