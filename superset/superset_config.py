"""
MR. Health -- Apache Superset Configuration
=============================================
Production configuration with BigQuery backend and security hardening.
"""

import os

# SECRET_KEY must be set via SUPERSET_SECRET_KEY environment variable.
# No fallback -- fails loudly if missing to prevent insecure defaults.
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"

WEBSERVER_THREADS = 8

FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": False,
}

EXTRA_CATEGORICAL_COLOR_SCHEMES = [
    {
        "id": "mrhealth",
        "description": "MR. Health brand palette",
        "label": "MR. Health",
        "isDefault": True,
        "colors": [
            "#4285F4",
            "#2f9e44",
            "#FBBC04",
            "#fa5252",
            "#868e96",
            "#7950f2",
            "#20c997",
            "#fd7e14",
        ],
    }
]

CACHE_CONFIG = {
    "CACHE_TYPE": "NullCache",
}

ENABLE_PROXY_FIX = True
WTF_CSRF_ENABLED = True
