import requests
import time
import random

BASE_URL = "http://localhost/api/v1"

def test_post_api_v1_products_slug_add_review():
    session = requests.Session()
    timeout = 30

    # Helper to register user and return access token
    def register_user():
        unique_email = f"user_{int(time.time())}_{random.randint(1000,9999)}@test.com"
        register_url = f"{BASE_URL}/auth/register/"
        register_payload = {
            "email": unique_email,
            "first_name": "Test",
            "last_name": "User",
            "password": "Password123!",
            "password2": "Password123!"
        }
        resp = session.post(register_url, json=register_payload, timeout=timeout)
        assert resp.status_code == 201, f"Registration failed: {resp.text}"
        data = resp.json()
        assert "access" in data, "No access token in registration response"
        return data["access"], unique_email

    # Helper to get a product slug from products list
    def get_any_product_slug():
        products_url = f"{BASE_URL}/products/"
        resp = session.get(products_url, timeout=timeout)
        assert resp.status_code == 200, f"Get products failed: {resp.text}"
        data = resp.json()
        # Expect paginated product list with key 'results'
        results = data.get("results") or data.get("products") or data
        assert isinstance(results, list), "Expected product list"
        assert len(results) > 0, "No products available to test"
        # get slug from first product with slug
        for p in results:
            slug = p.get("slug")
            if slug:
                return slug
        # fallback if no slug key
        raise AssertionError("No product slug found in product list")

    access_token, email = register_user()
    headers = {"Authorization": f"Bearer {access_token}"}

    product_slug = get_any_product_slug()
    add_review_url = f"{BASE_URL}/products/{product_slug}/add_review/"

    # Test valid rating (1-5) and comment, expect 201 with review object
    valid_review_payload = {"rating": 5, "comment": "Excellent product!"}
    try:
        resp = session.post(add_review_url, headers=headers, json=valid_review_payload, timeout=timeout)
        assert resp.status_code == 201, f"Valid review creation failed: {resp.text}"
        review = resp.json()
        assert "rating" in review and review["rating"] == 5, "Review rating mismatch"
        assert "comment" in review and review["comment"] == "Excellent product!", "Review comment mismatch"

        # Test invalid rating (e.g., 6) - expect 400 validation error
        invalid_rating_payload = {"rating": 6, "comment": "Invalid rating"}
        resp = session.post(add_review_url, headers=headers, json=invalid_rating_payload, timeout=timeout)
        assert resp.status_code == 400, f"Invalid rating should return 400, got {resp.status_code}: {resp.text}"

        # Test duplicate review (same user and product) - expect 400 duplicate review error
        resp = session.post(add_review_url, headers=headers, json=valid_review_payload, timeout=timeout)
        assert resp.status_code == 400, f"Duplicate review should return 400, got {resp.status_code}: {resp.text}"

    finally:
        # Cleanup: No endpoint for deleting review specified, so logout user to clear session
        logout_url = f"{BASE_URL}/auth/logout/"
        session.post(logout_url, timeout=timeout)


test_post_api_v1_products_slug_add_review()
