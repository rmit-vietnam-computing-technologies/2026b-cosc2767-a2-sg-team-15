# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 14/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author ran and adapted every override. Reference: Django settings,
#   https://docs.djangoproject.com/en/5.1/topics/settings/

"""Test settings. Selected by pytest.ini. Each override exists because something breaks or slows without it."""

import tempfile
from pathlib import Path

from .base import *  # noqa: F401,F403
from .base import DATABASES, LOGGING, REST_FRAMEWORK, STORAGES

DEBUG = False

# DRF's APIClient sends Host: testserver.
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# PBKDF2 would dominate a suite that creates users per test.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Outgoing mail lands in django.core.mail.outbox.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Throttles off, or repeated checkouts fail order-dependently.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    scope: None for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
}

# Manifest storage needs collectstatic to have run; plain storage does not.
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

# Uploads go to a throwaway directory; conftest narrows it per test.
MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="rmit-test-media-"))
USE_S3 = False

# Persistent connections break pytest-django's per-test rollback.
DATABASES["default"]["CONN_MAX_AGE"] = 0

LOGGING["root"]["level"] = "CRITICAL"
LOGGING["loggers"]["django"]["level"] = "CRITICAL"
