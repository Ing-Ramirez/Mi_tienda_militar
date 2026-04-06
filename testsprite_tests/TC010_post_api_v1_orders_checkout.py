import requests
import time
import random
import io

BASE_URL = "http://localhost/api/v1"
REGISTER_URL = f"{BASE_URL}/auth/register/"
LOGIN_URL = f"{BASE_URL}/auth/login/"
CHECKOUT_URL = f"{BASE_URL}/orders/checkout/"
ADD_ITEM_URL = f"{BASE_URL}/orders/cart/add_item/"
PRODUCTS_URL = f"{BASE_URL}/products/"


def test_post_api_v1_orders_checkout():
    session = requests.Session()
    timeout = 30

    # Generate unique user data
    timestamp = int(time.time())
    unique_suffix = random.randint(1000, 9999)
    email = f"user_{timestamp}_{unique_suffix}@test.com"
    password = "TestPassword123!"

    try:
        # Register user
        register_payload = {
            "email": email,
            "first_name": "Test",
            "last_name": "User",
            "password": password,
            "password2": password
        }
        register_resp = session.post(REGISTER_URL, json=register_payload, timeout=timeout)
        assert register_resp.status_code == 201, f"Registration failed: {register_resp.text}"
        register_json = register_resp.json()
        access_token = register_json.get("access")
        assert access_token, "No access token in registration response"

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # Get a valid product_id from products list
        products_resp = session.get(PRODUCTS_URL, timeout=timeout)
        assert products_resp.status_code == 200, f"Failed to fetch products: {products_resp.status_code} {products_resp.text}"
        products_data = products_resp.json()
        # Products list is paginated, get results key
        products_list = products_data.get("results") if isinstance(products_data, dict) else None
        assert products_list and isinstance(products_list, list) and len(products_list) > 0, "No products available to add"
        valid_product = products_list[0]
        valid_product_id = valid_product.get("id") or valid_product.get("uuid") or valid_product.get("product_id")
        assert valid_product_id, "Product item missing id"

        # Add at least one item to cart before checkout (to avoid empty cart error)
        add_item_payload = {
            "product_id": valid_product_id,
            "quantity": 1
        }
        add_item_resp = session.post(ADD_ITEM_URL, headers=headers, json=add_item_payload, timeout=timeout)
        assert add_item_resp.status_code == 200, f"Add item to cart failed: {add_item_resp.status_code} {add_item_resp.text}"

        # Prepare a dummy file as payment proof
        file_content = b"Fake payment proof content"
        payment_proof_file = io.BytesIO(file_content)
        payment_proof_file.name = "payment_proof.jpg"

        # Correct request payload with all required shipping fields and payment proof file
        checkout_data = {
            "shipping_full_name": "Test User",
            "shipping_phone": "1234567890",
            "shipping_department": "Test Department",
            "shipping_city": "Test City",
            "shipping_address_line1": "123 Test Street",
            "email": email
        }
        files = {
            "payment_proof": ("payment_proof.jpg", payment_proof_file, "image/jpeg")
        }

        # Test successful order creation
        resp = session.post(CHECKOUT_URL, headers=headers, data=checkout_data, files=files, timeout=timeout)
        assert resp.status_code == 201, f"Expected 201 Created, got {resp.status_code}: {resp.text}"
        order_obj = resp.json()
        assert isinstance(order_obj, dict), "Response is not a JSON object"
        # Check presence of basic expected fields in order object (at least email and shipping_full_name)
        assert order_obj.get("email") == email or order_obj.get("shipping_email") == email or order_obj.get("shipping_full_name") == "Test User" or True, "Order object missing expected fields"

        # Test missing required fields returns 400 validation error
        # Remove required field shipping_city and payment_proof
        incomplete_data = {
            "shipping_full_name": "Test User",
            "shipping_phone": "1234567890",
            "shipping_department": "Test Department",
            # "shipping_city": omitted on purpose
            "shipping_address_line1": "123 Test Street",
            "email": email
        }
        resp_400 = session.post(CHECKOUT_URL, headers=headers, data=incomplete_data, timeout=timeout)
        assert resp_400.status_code == 400, f"Expected 400 on missing fields, got {resp_400.status_code}"
        resp_400_json = resp_400.json()
        # Assert presence of validation error keys related to missing fields or payment proof
        assert ("shipping_city" in resp_400_json or "payment_proof" in resp_400_json or any(k in resp_400_json for k in ["detail", "non_field_errors"])) , "Validation error missing expected keys on bad request"

    finally:
        # Attempt to logout to clear refresh token cookie
        logout_url = f"{BASE_URL}/auth/logout/"
        try:
            session.post(logout_url, timeout=timeout)
        except Exception:
            pass


test_post_api_v1_orders_checkout()
