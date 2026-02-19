"""
MR. Health -- Apache Superset Configuration
=============================================
Custom configuration for local development with BigQuery backend.
"""

import os

SECRET_KEY = os.environ.get(
    "SUPERSET_SECRET_KEY",
    "mrhealth-superset-dev-key-change-in-production",
)

SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"

WEBSERVER_THREADS = 8

FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
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
WTF_CSRF_ENABLED = False
