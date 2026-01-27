import os

# Set test-friendly rate limits BEFORE importing the app anywhere
os.environ.setdefault("REDIRECT_LIMIT", "3")
os.environ.setdefault("REDIRECT_WINDOW", "60")