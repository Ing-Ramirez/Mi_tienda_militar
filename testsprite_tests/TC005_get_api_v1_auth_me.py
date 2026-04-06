import requests
import time
from datetime import datetime

BASE_URL = "http://localhost:80/api/v1"
REGISTER_URL = f"{BASE_URL}/auth/register/"
LOGIN_URL = f"{BASE_URL}/auth/login/"
ME_URL = f"{BASE_URL}/auth/me/"

def test_get_api_v1_auth_me():
    session = requests.Session()
    timeout = 30
    timestamp = int(time.time())
    # Unique user email per test run
    email = f"user_{timestamp}@test.com"
    password = "Xq7!mZ2#vL9"

    # Register new user to obtain access token
    register_payload = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "password2": password,
    }

    resp = session.post(REGISTER_URL, json=register_payload, timeout=timeout)
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    resp_json = resp.json()
    access_token = resp_json.get("access")
    assert isinstance(access_token, str) and access_token, "No access token in register response"

    headers_auth = {"Authorization": f"Bearer {access_token}"}

    try:
        # Test: GET /auth/me with valid token returns 200 and user object
        resp_me = session.get(ME_URL, headers=headers_auth, timeout=timeout)
        assert resp_me.status_code == 200, f"GET /auth/me with valid token failed: {resp_me.text}"
        user_obj = resp_me.json()
        assert isinstance(user_obj, dict), "User profile response is not a dict"
        assert user_obj.get("email") == email, "Returned user email mismatch"

        # Test: GET /auth/me with no Authorization header returns 401 Unauthorized
        resp_no_auth = session.get(ME_URL, timeout=timeout)
        assert resp_no_auth.status_code == 401, f"GET /auth/me without token should be 401 but got {resp_no_auth.status_code}"

        # Test: GET /auth/me with invalid token returns 401 Unauthorized
        headers_invalid_auth = {"Authorization": "Bearer invalidtoken12345"}
        resp_invalid = session.get(ME_URL, headers=headers_invalid_auth, timeout=timeout)
        assert resp_invalid.status_code == 401, f"GET /auth/me with invalid token should be 401 but got {resp_invalid.status_code}"
    finally:
        # Cleanup: delete created user if API had delete user endpoint (not specified)
        # No delete endpoint is given, so skip cleanup
        session.close()

test_get_api_v1_auth_me()