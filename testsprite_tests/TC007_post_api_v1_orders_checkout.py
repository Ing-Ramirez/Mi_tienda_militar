import requests
import time
import io

BASE_URL = "http://localhost:80/api/v1"

def test_post_api_v1_orders_checkout():
    session = requests.Session()
    timeout = 30

    # Step 1: Register a new user with unique email and strong password
    timestamp = int(time.time() * 1000)
    email = f"user_{timestamp}@test.com"
    password = "Xq7!mZ2#vL9"
    register_data = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "password2": password
    }
    register_resp = session.post(f"{BASE_URL}/auth/register/", json=register_data, timeout=timeout)
    assert register_resp.status_code == 201, f"Registration failed: {register_resp.text}"
    access_token = register_resp.json().get("access")
    assert access_token, "No access token returned on registration"

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    try:
        # Step 2: Get products list and select first product's id
        products_resp = requests.get(f"{BASE_URL}/products/", timeout=timeout)
        assert products_resp.status_code == 200, f"Failed fetching products: {products_resp.text}"
        results = products_resp.json().get("results")
        assert results and len(results) > 0, "No products found"
        product_id = results[0]["id"]

        # Step 3: Add item to cart
        add_item_payload = {
            "product_id": product_id,
            "quantity": 1,
            "talla": "M",
            "bordado": "TestName",
            "rh": "O+"
        }
        add_item_resp = session.post(f"{BASE_URL}/orders/cart/add_item/", json=add_item_payload, headers=auth_headers, timeout=timeout)
        assert add_item_resp.status_code == 201, f"Add item to cart failed: {add_item_resp.text}"

        # Step 4: Prepare multipart/form-data for checkout with shipping info and payment_proof file
        shipping_data = {
            "shipping_full_name": "Test User",
            "shipping_phone": "1234567890",
            "shipping_department": "Antioquia",
            "shipping_city": "Medellin",
            "shipping_address_line1": "123 Test St",
            "email": email,
        }
        # Minimal valid JPEG header bytes for payment_proof
        payment_proof_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
        payment_proof_file = ('payment_proof.jpg', io.BytesIO(payment_proof_content), 'image/jpeg')

        # multipart/form-data requires 'files' param to include files
        files = {
            "payment_proof": payment_proof_file
        }
        multipart_data = {}
        multipart_data.update(shipping_data)

        checkout_resp = session.post(f"{BASE_URL}/orders/checkout/", headers=auth_headers,
                                     data=multipart_data, files=files, timeout=timeout)
        assert checkout_resp.status_code == 201, f"Checkout with payment_proof failed: {checkout_resp.text}"

        order = checkout_resp.json()
        # Verify expected fields in order object
        expected_fields = {"id", "order_number", "total_amount", "status", "manual_payment_status", "payment_method"}
        assert expected_fields.issubset(order.keys()), f"Missing expected fields in order: {order.keys()}"

        # Step 5: Attempt checkout without payment_proof - expect 400
        checkout_missing_file_resp = session.post(f"{BASE_URL}/orders/checkout/", headers=auth_headers,
                                                  data=shipping_data, timeout=timeout)
        assert checkout_missing_file_resp.status_code == 400, f"Checkout missing payment_proof should fail: {checkout_missing_file_resp.text}"
    finally:
        pass

test_post_api_v1_orders_checkout()
