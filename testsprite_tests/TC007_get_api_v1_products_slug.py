import requests
import time

BASE_URL = "http://localhost:80/api/v1"
TIMEOUT = 30

def test_get_api_v1_products_slug():
    session = requests.Session()
    try:
        # Step 1: Get featured products to find a valid slug (public endpoint, no auth needed)
        featured_url = f"{BASE_URL}/products/featured/"
        resp_featured = session.get(featured_url, timeout=TIMEOUT)
        assert resp_featured.status_code == 200, f"Expected 200 from featured products, got {resp_featured.status_code}"
        featured_products = resp_featured.json()
        assert isinstance(featured_products, list), "Featured products response is not a list"
        assert len(featured_products) > 0, "No featured products found to test valid slug"

        valid_slug = featured_products[0].get("slug")
        assert valid_slug, "Featured product does not have a slug"

        # Step 2: Get product details by valid slug
        product_url = f"{BASE_URL}/products/{valid_slug}/"
        resp_product = session.get(product_url, timeout=TIMEOUT)
        assert resp_product.status_code == 200, f"Expected 200 for product details, got {resp_product.status_code}"
        product_obj = resp_product.json()
        assert isinstance(product_obj, dict), "Product detail response is not a JSON object"
        assert product_obj.get("slug") == valid_slug, f"Returned product slug does not match requested slug {valid_slug}"

        # Step 3: Get product by invalid slug - expect 404
        invalid_slug = f"invalid-slug-{int(time.time())}"
        invalid_product_url = f"{BASE_URL}/products/{invalid_slug}/"
        resp_invalid = session.get(invalid_product_url, timeout=TIMEOUT)
        assert resp_invalid.status_code == 404, f"Expected 404 for invalid slug, got {resp_invalid.status_code}"

    finally:
        session.close()

test_get_api_v1_products_slug()