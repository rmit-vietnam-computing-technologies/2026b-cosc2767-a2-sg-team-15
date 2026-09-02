# RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Vo Hoang Khanh
# ID: s3926310
# Created  date: 02/09/2026
# Last modified: 02/09/2026
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

# Django forces DEBUG off during tests regardless; stated explicitly so nobody
# reads this file and assumes otherwise.
DEBUG = False

# [T15-BE-HOSTHDR][REQ-5] DRF's APIClient sends Host: testserver. Omit it and
# every request fails with DisallowedHost before reaching a view — which is
# also exactly how ALLOWED_HOSTS misconfiguration fails behind a load
# balancer. The Step 5 tests assert that behaviour deliberately by overriding
# this list per-test.
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# [T15-BE-TEST] Weak hashing, on purpose and only here.
#
# The default PBKDF2 hasher runs hundreds of thousands of iterations per call.
# With a fixture creating four users per test, password hashing dominates the
# suite — this is typically a 3-5x speedup across a few hundred tests. It must
# never appear in base.py.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Captures outgoing mail in django.core.mail.outbox instead of printing it, so
# tests can assert that a password reset or merchant invitation was sent.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# [T15-BE-TEST][REQ-5] Throttling off.
#
# base.py throttles auth at 20/min. The authorisation matrix in Step 4 fires
# far more than 20 requests, so with throttling on the suite fails
# intermittently and in an order-dependent way — the worst kind of flake,
# because it looks like a permissions bug. Throttle behaviour gets its own
# test that re-enables the rate explicitly.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    scope: None for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
}

# [T15-BE-STATIC] Manifest storage requires collectstatic to have run, or any
# view rendering a static asset raises "Missing staticfiles manifest entry".
# That would make the admin and browsable-API tests fail for a reason that has
# nothing to do with what they assert.
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

# [T15-BE-MEDIA] Uploads go to a throwaway directory, never server/media/.
# conftest.py narrows this to a per-test tmp_path; this is the backstop for
# anything that runs outside a fixture.
MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="rmit-test-media-"))

# Never reach S3 from a test, whatever happens to be in the environment.
USE_S3 = False

# [T15-BE-DB] Persistent connections confuse pytest-django's transaction
# rollback between tests and can leave a connection pinned to a dropped test
# database at teardown.
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Keep failure output readable. A real failure still prints its traceback.
LOGGING["root"]["level"] = "CRITICAL"
LOGGING["loggers"]["django"]["level"] = "CRITICAL"
