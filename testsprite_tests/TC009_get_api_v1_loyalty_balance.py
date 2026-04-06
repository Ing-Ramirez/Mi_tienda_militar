import requests
import time
import uuid


BASE_URL = "http://localhost:80/api/v1"
REGISTER_URL = f"{BASE_URL}/auth/register/"
LOGIN_URL = f"{BASE_URL}/auth/login/"
LOYALTY_BALANCE_URL = f"{BASE_URL}/loyalty/balance/"


def test_get_api_v1_loyalty_balance():
    session = requests.Session()
    timestamp = int(time.time() * 1000)
    unique_email = f"user_{timestamp}@test.com"
    register_payload = {
        "email": unique_email,
        "first_name": "Test",
        "last_name": "User",
        "password": "Xq7!mZ2#vL9",
        "password2": "Xq7!mZ2#vL9"
    }
    access_token = None

    try:
        # Register new user
        resp = session.post(
            REGISTER_URL,
            json=register_payload,
            timeout=30
        )
        assert resp.status_code == 201, f"Register failed: {resp.text}"
        json_data = resp.json()
        assert "access" in json_data, "No access token in register response"
        access_token = json_data["access"]

        # Set Authorization header for subsequent requests
        headers = {"Authorization": f"Bearer {access_token}"}

        # Call loyalty balance endpoint
        resp = session.get(
            LOYALTY_BALANCE_URL,
            headers=headers,
            timeout=30
        )
        assert resp.status_code == 200, f"Loyalty balance failed: {resp.text}"
        data = resp.json()

        # Validate expected keys in response
        expected_keys = {"points_balance", "balance_in_cop", "point_value_cop", "points_per_cop"}
        assert expected_keys.issubset(data.keys()), f"Missing keys in loyalty balance response: {data.keys()}"

        # Validate that points_balance is a number (int or float)
        assert isinstance(data["points_balance"], (int, float)), "points_balance is not a number"

        # Validate that balance_in_cop is a number (int or float)
        assert isinstance(data["balance_in_cop"], (int, float)), "balance_in_cop is not a number"

        # Validate point_value_cop is a number
        assert isinstance(data["point_value_cop"], (int, float)), "point_value_cop is not a number"

        # Validate points_per_cop is a number
        assert isinstance(data["points_per_cop"], (int, float)), "points_per_cop is not a number"

    finally:
        # Clean up: delete user via API if such endpoint existed,
        # but since not defined in PRD, no delete endpoint available.
        # Alternatively, do nothing or log.
        pass


test_get_api_v1_loyalty_balance()