import os
import time
from datetime import datetime

import requests

BASE_URL = "http://localhost:80/api/v1"
PASSWORD = os.environ.get("TEST_USER_PASSWORD", "Xq7!mZ2#vL9")


def test_post_api_v1_auth_logout():
    session = requests.Session()
    timestamp = int(time.time() * 1000)
    unique_email = f"user_{timestamp}@test.com"
    register_url = f"{BASE_URL}/auth/register/"
    login_url = f"{BASE_URL}/auth/login/"
    logout_url = f"{BASE_URL}/auth/logout/"

    # Register a new user to obtain tokens and set refresh_token cookie
    register_payload = {
        "email": unique_email,
        "first_name": "Test",
        "last_name": "User",
        "password": PASSWORD,
        "password2": PASSWORD
    }
    try:
        register_resp = session.post(register_url, json=register_payload, timeout=30)
        assert register_resp.status_code == 201, f"Registration failed: {register_resp.status_code} {register_resp.text}"
        reg_data = register_resp.json()
        assert "access" in reg_data, "Access token missing in registration response"
        assert reg_data.get("user", {}).get("email") == unique_email

        # Log in again to ensure session has refresh_token cookie (optional, session likely has it from register)
        login_payload = {
            "email": unique_email,
            "password": PASSWORD
        }
        login_resp = session.post(login_url, json=login_payload, timeout=30)
        assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code} {login_resp.text}"
        login_data = login_resp.json()
        assert "access" in login_data, "Access token missing in login response"
        assert login_data.get("user", {}).get("email") == unique_email

        # Call logout endpoint with refresh_token cookie present
        logout_resp = session.post(logout_url, timeout=30)
        assert logout_resp.status_code == 200, f"Logout failed: {logout_resp.status_code} {logout_resp.text}"
        logout_data = logout_resp.json()
        assert "detail" in logout_data and isinstance(logout_data["detail"], str) and len(logout_data["detail"]) > 0

        # Verify that the refresh_token cookie has been cleared/set to expire
        cookies = logout_resp.cookies or session.cookies
        refresh_token_cookie = cookies.get("refresh_token")
        # The cookie should be either absent or empty or expired
        # requests does not expose cookie expiry, so we check if cookie is missing or empty string
        assert refresh_token_cookie in (None, "", "deleted", "deleted;") or refresh_token_cookie is None
    finally:
        # Cleanup: no user deletion endpoint described, so nothing to do here
        session.close()


test_post_api_v1_auth_logout()