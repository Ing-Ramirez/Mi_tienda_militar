import os
import uuid

import requests

BASE_URL = "http://localhost/api/v1"
TIMEOUT = 30

# Credentials for an existing user, or create/register before running this test
TEST_USER_EMAIL = "testuser@example.com"
TEST_USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "SecureP@ssw0rd!")


def register_user(email: str, password: str, first_name: str = "Test", last_name: str = "User") -> None:
    register_url = f"{BASE_URL}/auth/register/"
    data = {
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name
    }
    resp = requests.post(register_url, json=data, timeout=TIMEOUT)
    if resp.status_code == 201:
        return
    elif resp.status_code == 400 and "email" in resp.text.lower():
        # Possibly user already exists, ignore
        return
    else:
        resp.raise_for_status()


def get_access_token(email: str, password: str) -> str:
    login_url = f"{BASE_URL}/auth/login/"
    data = {"email": email, "password": password}
    try:
        resp = requests.post(login_url, json=data, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("access")
    except Exception as e:
        raise RuntimeError(f"Failed to obtain access token: {e}")


def create_test_order(access_token: str) -> str:
    # To create a new order, first add an item to cart, then checkout legacy JSON
    headers = {"Authorization": f"Bearer {access_token}"}
    cart_add_url = f"{BASE_URL}/orders/cart/add_item/"
    checkout_url = f"{BASE_URL}/orders/orders/checkout/"

    # Step 1: Get product list to find a product_id to add to cart
    products_url = f"{BASE_URL}/products/"
    resp = requests.get(products_url, timeout=TIMEOUT)
    resp.raise_for_status()
    products = resp.json().get("results") or resp.json()
    if not products:
        raise RuntimeError("No products available to add to cart for test order.")
    product = products[0]
    product_id = product.get("id") or product.get("uuid")
    if not product_id:
        # Try slug and get detailed
        slug = product.get("slug")
        if slug:
            product_detail = requests.get(f"{products_url}{slug}/", timeout=TIMEOUT)
            product_detail.raise_for_status()
            product_json = product_detail.json()
            product_id = product_json.get("id") or product_json.get("uuid")
    if not product_id:
        raise RuntimeError("Failed to determine product_id for test order creation.")

    # Add item to cart
    add_item_payload = {
        "product_id": product_id,
        "quantity": 1
    }
    resp = requests.post(cart_add_url, json=add_item_payload, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()

    # Checkout legacy JSON (required fields)
    checkout_payload = {
        "shipping_full_name": "Test User",
        "shipping_phone": "3001234567",
        "shipping_department": "Cundinamarca",
        "shipping_city": "Bogotá",
        "shipping_address_line1": "Test Street 123",
        "email": TEST_USER_EMAIL
    }
    resp = requests.post(checkout_url, json=checkout_payload, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    order_data = resp.json()
    order_number = order_data.get("order_number") or order_data.get("number") or order_data.get("id")
    if not order_number:
        raise RuntimeError("Order number not returned on order creation.")
    return str(order_number)


def delete_order_mock(access_token: str, order_number: str):
    # The PRD does not describe an order deletion endpoint.
    # So, no cleanup possible for orders. This is noted.
    pass


def test_post_api_v1_payments_stripe():
    register_user(TEST_USER_EMAIL, TEST_USER_PASSWORD)
    access_token = get_access_token(TEST_USER_EMAIL, TEST_USER_PASSWORD)
    headers = {"Authorization": f"Bearer {access_token}"}

    # Create a valid order to test with
    order_number = create_test_order(access_token)

    try:
        # Test valid order_number => 200 with client_secret
        url = f"{BASE_URL}/payments/stripe/"
        payload = {"order_number": order_number}
        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        assert resp.status_code == 200, f"Expected 200 response, got {resp.status_code}"
        json_resp = resp.json()
        client_secret = json_resp.get("client_secret")
        assert client_secret and isinstance(client_secret, str), "Missing or invalid client_secret in response"

        # Test unknown order_number => 404
        unknown_order_number = str(uuid.uuid4())
        payload = {"order_number": unknown_order_number}
        resp2 = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        assert resp2.status_code == 404, f"Expected 404 for unknown order_number, got {resp2.status_code}"

    finally:
        # No delete endpoint for orders, so no cleanup here.
        pass


test_post_api_v1_payments_stripe()
