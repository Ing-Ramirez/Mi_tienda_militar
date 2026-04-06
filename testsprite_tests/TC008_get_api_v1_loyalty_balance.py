import requests
import time

BASE_URL = "http://localhost:80/api/v1"
REGISTER_URL = f"{BASE_URL}/auth/register/"
LOGIN_URL = f"{BASE_URL}/auth/login/"
LOYALTY_BALANCE_URL = f"{BASE_URL}/loyalty/balance/"

def test_get_api_v1_loyalty_balance():
    session = requests.Session()
    timestamp = int(time.time() * 1000)
    email = f"user_{timestamp}@test.com"
    password = "Xq7!mZ2#vL9"

    # Register
    register_data = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "password2": password,
    }
    try:
        reg_resp = session.post(REGISTER_URL, json=register_data, timeout=30)
        assert reg_resp.status_code == 201, f"Register failed: {reg_resp.text}"
        reg_json = reg_resp.json()
        assert "access" in reg_json and "user" in reg_json
        access_token = reg_json["access"]
    except Exception as e:
        session.close()
        raise

    # Use access token to get loyalty balance
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        balance_resp = session.get(LOYALTY_BALANCE_URL, headers=headers, timeout=30)
        assert balance_resp.status_code == 200, f"Loyalty balance request failed: {balance_resp.text}"
        balance_json = balance_resp.json()
        # Assert required fields
        expected_fields = ["points_balance", "balance_in_cop", "point_value_cop", "points_per_cop"]
        for field in expected_fields:
            assert field in balance_json, f"Missing field '{field}' in loyalty balance response"
            # Optionally assert the type
            assert isinstance(balance_json[field], (int, float)), f"Field '{field}' must be number"
    finally:
        # Cleanup: There is no delete user endpoint specified, so just close session
        session.close()

test_get_api_v1_loyalty_balance()