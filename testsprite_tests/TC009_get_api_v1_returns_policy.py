import requests
import json

def test_get_api_v1_returns_policy():
    base_url = "http://localhost/api/v1"
    url = f"{base_url}/returns/policy/"

    try:
        response = requests.get(url, timeout=30)
        assert response.status_code == 200, f"Expected status 200 but got {response.status_code}"
        data = response.json()
        assert isinstance(data, dict), "Response JSON is not a dictionary"
        assert "policy" in data, "'policy' key not in response JSON"
        assert isinstance(data["policy"], str), "'policy' is not a string"
        assert len(data["policy"].strip()) > 0, "'policy' string is empty"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"


test_get_api_v1_returns_policy()
