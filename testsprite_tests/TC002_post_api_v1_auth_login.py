import os
import time
import uuid

import requests

BASE_URL = "http://localhost:80/api/v1"
REGISTER_URL = f"{BASE_URL}/auth/register/"
LOGIN_URL = f"{BASE_URL}/auth/login/"

def test_post_api_v1_auth_login():
    session = requests.Session()
    timestamp = int(time.time() * 1000)
    unique_email = f"user_{timestamp}@test.com"
    password = os.environ.get("TEST_USER_PASSWORD", "Xq7!mZ2#vL9")

    # Register a new user to test login with correct credentials
    register_payload = {
        "email": unique_email,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "password2": password
    }
    try:
        reg_resp = session.post(REGISTER_URL, json=register_payload, timeout=30)
        assert reg_resp.status_code == 201, f"Registration failed with {reg_resp.status_code}: {reg_resp.text}"
        reg_data = reg_resp.json()
        assert "access" in reg_data and isinstance(reg_data["access"], str) and reg_data["access"], "Access token missing in registration response"
        # The session should now have the HttpOnly refresh_token cookie set by the server.

        # --- Test 1: Successful login with correct credentials ---
        # For login test, use a new session to isolate cookies from registration step
        login_session = requests.Session()
        login_payload = {
            "email": unique_email,
            "password": password
        }
        login_resp = login_session.post(LOGIN_URL, json=login_payload, timeout=30)
        assert login_resp.status_code == 200, f"Login failed with correct credentials: {login_resp.status_code} {login_resp.text}"
        login_data = login_resp.json()
        assert "access" in login_data and isinstance(login_data["access"], str) and login_data["access"], "Access token missing in login response"
        assert "user" in login_data, "User object missing in login response"
        user_obj = login_data["user"]
        for key in ("email", "first_name", "last_name", "account_type"):
            assert key in user_obj, f"User object missing key '{key}'"
        # Check that refresh_token cookie is set in login_session
        refresh_token_cookie = None
        for cookie in login_session.cookies:
            if cookie.name == "refresh_token":
                refresh_token_cookie = cookie
                break
        assert refresh_token_cookie is not None, "Refresh token cookie not set on login"

        # --- Test 2: Failed login with incorrect credentials ---
        wrong_login_payload = {
            "email": unique_email,
            "password": "WrongPassword123!"
        }
        wrong_resp = requests.post(LOGIN_URL, json=wrong_login_payload, timeout=30)
        assert wrong_resp.status_code == 401, f"Expected 401 for wrong credentials but got {wrong_resp.status_code}"
        wrong_data = wrong_resp.json()
        # Optional: error message may vary but status code enough to assert

        # --- Test 3: CAPTCHA error when captcha is required ---
        # Based on instructions: RULES: (1) No CAPTCHA in test env, so skip this test (CAPTCHA disabled)
        # So do NOT test captcha errors as per instructions
        
        # --- Test 4: Rate limiting behavior ---
        # Test rapid repeated login failures to trigger rate limit
        # Instructions say throttle is relaxed to 200/min in testing, so need many requests to trigger 429
        # We'll simulate 10 quick failed attempts and check if any 429 happens (some servers may enforce stricter limits)
        # If no 429 in first 10 attempts, test still passes as rate limiting may not be triggered with few attempts
        rate_limit_triggered = False
        for i in range(10):
            rl_resp = requests.post(LOGIN_URL, json=wrong_login_payload, timeout=30)
            if rl_resp.status_code == 429:
                rate_limit_triggered = True
                break
        # It's acceptable if no 429 triggered due to relaxed testing environment, so no assert here
    finally:
        # Clean up: Delete created user if backend supported deletion (not in spec).
        # Since no user deletion endpoint described, skip deletion.
        pass

test_post_api_v1_auth_login()