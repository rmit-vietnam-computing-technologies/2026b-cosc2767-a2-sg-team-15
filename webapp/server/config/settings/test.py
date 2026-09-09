# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 09/09/2026
# Acknowledgement: Drafted with Claude (Anthropic) in a guided session; the
#   author reviewed, ran and adapted every override. The module occupies the
#   slot named by the docstring in config/settings/base.py, which lists
#   dev.py / prod.py / test.py as the three environment modules. Reference:
#   Django settings documentation, https://docs.djangoproject.com/en/5.1/topics/settings/

"""
Test settings.

Activate with:  DJANGO_SETTINGS_MODULE=config.settings.test  (pytest.ini does).

Read this next to dev.py and prod.py. Each override below exists because
something breaks or gets slow without it, and each one is noted.
"""

import tempfile
from pathlib import Path

from .base import *  # noqa: F401,F403
from .base import DATABASES, LOGGING, REST_FRAMEWORK, STORAGES

# Django forces this off during tests anyway.
DEBUG = False

# DRF's APIClient sends Host: testserver. The
# configuration tests override this list to reproduce the load-balancer 400.
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Weak hashing, only here: PBKDF2 would dominate a suite that
# creates four users per test.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Outgoing mail lands in django.core.mail.outbox for assertions.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Throttling off: the authorisation matrix exceeds the
# 20/min auth rate and would fail order-dependently.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    scope: None for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
}

# Manifest storage needs collectstatic to have run; plain
# storage does not.
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

# Uploads go to a throwaway directory; conftest narrows this per test.
MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="rmit-test-media-"))

# Never reach S3 from a test.
USE_S3 = False

# Persistent connections break pytest-django's per-test rollback.
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Keep failure output readable.
LOGGING["root"]["level"] = "CRITICAL"
LOGGING["loggers"]["django"]["level"] = "CRITICAL"
