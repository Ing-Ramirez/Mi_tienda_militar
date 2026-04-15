import os
import random
import time

import requests

BASE_URL = "http://localhost:80"
API_PREFIX = "/api/v1"
REGISTER_URL = f"{BASE_URL}{API_PREFIX}/auth/register/"
LOGIN_URL = f"{BASE_URL}{API_PREFIX}/auth/login/"
MY_CART_URL = f"{BASE_URL}{API_PREFIX}/orders/cart/my_cart/"

def test_get_api_v1_orders_cart_my_cart():
    session = requests.Session()
    unique_email = f"user_{int(time.time())}_{random.randint(1000,9999)}@test.com"
    password = os.environ.get("TEST_USER_PASSWORD", "Xq7!mZ2#vL9")

    # Register user
    register_payload = {
        "email": unique_email,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "password2": password
    }
    try:
        reg_resp = session.post(REGISTER_URL, json=register_payload, timeout=30)
        assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
        reg_json = reg_resp.json()
        assert "access" in reg_json and "user" in reg_json, "Missing access token or user in registration response"

        # Login user
        login_payload = {
            "email": unique_email,
            "password": password
        }
        login_resp = session.post(LOGIN_URL, json=login_payload, timeout=30)
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        login_json = login_resp.json()
        assert "access" in login_json and "user" in login_json, "Missing access token or user in login response"
        access_token = login_json["access"]

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # Fetch current user's cart
        cart_resp = session.get(MY_CART_URL, headers=headers, timeout=30)
        assert cart_resp.status_code == 200, f"Fetching cart failed: {cart_resp.text}"

        cart_json = cart_resp.json()
        # Validate that cart contains expected keys: cart and items
        # The PRD states: 200 with cart and items
        # So we check for keys in returned JSON
        assert isinstance(cart_json, dict), "Cart response is not a JSON object"
        # Commonly, cart and items keys. Depending on schema, might be 'items' list inside cart or at root.
        # We assert at least 'items' key exists and is a list
        assert "items" in cart_json, "Missing 'items' in cart response"
        assert isinstance(cart_json["items"], list), "'items' is not a list in cart response"

    finally:
        # Cleanup: logout to clear session cookies
        try:
            logout_url = f"{BASE_URL}{API_PREFIX}/auth/logout/"
            session.post(logout_url, timeout=30)
        except Exception:
            pass

test_get_api_v1_orders_cart_my_cart()