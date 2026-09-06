import os

os.environ["AUTH_MODE"] = "local"
os.environ["LOCAL_AUTH_SECRET"] = "testing-only-key-with-at-least-32-characters"
os.environ["LOCAL_PASSWORD"] = "cornell-local"
