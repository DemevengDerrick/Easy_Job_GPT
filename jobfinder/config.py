"""Settings come from environment variables.

Streamlit Cloud exposes root-level secrets as environment variables, and app.py copies a
local .streamlit/secrets.toml into the environment, so this works the same everywhere
(including worker threads and GitHub Actions).
"""
import os


def get(name, default=None):
    return os.environ.get(name) or default


def database_url():
    return get("DATABASE_URL", "sqlite:///jobfinder.db")


def app_url():
    return get("APP_URL", "http://localhost:8501").rstrip("/")
