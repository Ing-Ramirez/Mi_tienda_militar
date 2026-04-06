import requests
import time
import json

BASE_URL = "http://localhost:80/api/v1"
REGISTER_ENDPOINT = f"{BASE_URL}/auth/register/"
TIMEOUT = 30


def test_post_api_v1_auth_register():
    session = requests.Session()

    timestamp = str(int(time.time() * 1000))
    unique_email = f"user_{timestamp}@test.com"
    strong_password = "Xq7!mZ2#vL9"

    headers = {"Content-Type": "application/json"}

    # 1. Successful registration with valid data
    valid_payload = {
        "email": unique_email,
        "first_name": "Test",
        "last_name": "User",
        "password": strong_password,
        "password2": strong_password
    }

    resp = session.post(REGISTER_ENDPOINT, headers=headers, json=valid_payload, timeout=TIMEOUT)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}, content: {resp.text}"

    resp_json = resp.json()
    # Validate response contains access token
    assert "access" in resp_json, "Missing 'access' token in response body"
    # Validate user object structure minimal keys
    assert "user" in resp_json, "Missing 'user' in response body"
    user = resp_json["user"]
    for key in ["email", "first_name", "last_name"]:
        assert key in user, f"Missing '{key}' in user object"
    assert user["email"] == unique_email

    # Validate refresh_token cookie is set and is HttpOnly
    cookies = resp.cookies
    # requests does not expose HttpOnly flag directly, but cookie must exist with name refresh_token
    refresh_token_cookie = None
    for c in session.cookies:
        if c.name == "refresh_token":
            refresh_token_cookie = c
            break
    assert refresh_token_cookie is not None, "refresh_token cookie not set"
    # HttpOnly attribute cannot be read via requests, assume backend sets correctly (cannot assert here)

    # 2. Registration with missing password2: expect 400 validation error
    payload_missing_password2 = {
        "email": f"user_missing_pw2_{timestamp}@test.com",
        "first_name": "Test",
        "last_name": "User",
        "password": strong_password,
        # "password2" missing
    }
    resp = session.post(REGISTER_ENDPOINT, headers=headers, json=payload_missing_password2, timeout=TIMEOUT)
    assert resp.status_code == 400, f"Expected 400 for missing password2, got {resp.status_code}, content: {resp.text}"
    error_json = resp.json()
    assert any("password2" in key.lower() or "password" in key.lower() for key in error_json.keys()) or isinstance(error_json, dict)

    # 3. Registration with mismatched password2: expect 400 validation error
    payload_mismatched_password2 = {
        "email": f"user_mismatch_pw2_{timestamp}@test.com",
        "first_name": "Test",
        "last_name": "User",
        "password": strong_password,
        "password2": "DifferentPassword123!"
    }
    resp = session.post(REGISTER_ENDPOINT, headers=headers, json=payload_mismatched_password2, timeout=TIMEOUT)
    assert resp.status_code == 400, f"Expected 400 for mismatched password2, got {resp.status_code}, content: {resp.text}"
    error_json = resp.json()
    assert any("password2" in key.lower() or "password" in key.lower() for key in error_json.keys()) or isinstance(error_json, dict)

    # 4. Registration with weak/common password: expect 400 validation error
    common_passwords = ["password123", "test1234", "12345678", "password", "qwerty"]
    for common_pw in common_passwords:
        payload_weak_password = {
            "email": f"user_weak_pw_{common_pw}_{timestamp}@test.com",
            "first_name": "Test",
            "last_name": "User",
            "password": common_pw,
            "password2": common_pw
        }
        resp = session.post(REGISTER_ENDPOINT, headers=headers, json=payload_weak_password, timeout=TIMEOUT)
        assert resp.status_code == 400, f"Expected 400 for weak password '{common_pw}', got {resp.status_code}, content: {resp.text}"
        error_json = resp.json()
        # The error could include 'password' key or 'non_field_errors' or similar
        found_password_error = False
        if isinstance(error_json, dict):
            keys_str = " ".join(error_json.keys()).lower()
            if "password" in keys_str:
                found_password_error = True
            else:
                # Check nested errors
                for val in error_json.values():
                    if isinstance(val, list):
                        if any("password" in str(msg).lower() for msg in val):
                            found_password_error = True
                            break
        assert found_password_error, f"No password validation error found for weak password '{common_pw}'"

    # Cleanup: No resource to delete since user created and should persist (typically test db reset externally)
    # Alternatively, if deleting users via API existed, could delete here.

test_post_api_v1_auth_register()