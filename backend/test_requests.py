import requests

# Test that the requests library was auto-installed
print("requests version:", requests.__version__)

# Try a simple GET request (note: network is enabled during dep install,
# but this will fail if network is disabled after — that's expected)
try:
    res = requests.get("https://httpbin.org/get", timeout=3)
    print("Status:", res.status_code)
except Exception as e:
    print("Network blocked (expected):", type(e).__name__)

print("requests auto-install test complete!")
