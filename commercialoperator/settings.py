#!/usr/bin/env python

import hashlib
import logging
import os

import confy
from confy import env

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists(BASE_DIR + "/.env"):
    confy.read_environment_file(BASE_DIR + "/.env")
os.environ.setdefault("BASE_DIR", BASE_DIR)

from ledger_api_client.settings_base import *

ROOT_URLCONF = "commercialoperator.urls"
COMMERCIALOPERATOR_EXTERNAL_URL = env("COMMERCIALOPERATOR_EXTERNAL_URL", "")
SITE_ID = 1
DEPT_DOMAINS = env("DEPT_DOMAINS", ["dpaw.wa.gov.au", "dbca.wa.gov.au"])
SYSTEM_MAINTENANCE_WARNING = env("SYSTEM_MAINTENANCE_WARNING", 24)  # hours
SHOW_TESTS_URL = env("SHOW_TESTS_URL", False)
SHOW_DEBUG_TOOLBAR = env("SHOW_DEBUG_TOOLBAR", False)

FILE_UPLOAD_PERMISSIONS = None
PRIVATE_MEDIA_DIR_NAME = env("PRIVATE_MEDIA_DIR_NAME", "private-media")
PRIVATE_MEDIA_STORAGE_LOCATION = os.path.join(BASE_DIR, PRIVATE_MEDIA_DIR_NAME)
PRIVATE_MEDIA_BASE_URL = f"/{PRIVATE_MEDIA_DIR_NAME}/"
SESSION_ENGINE = "django.contrib.sessions.backends.file"
SESSION_FILE_PATH = env("SESSION_FILE_PATH", default="/app/session_store/")

BUILD_TAG = env(
    "BUILD_TAG", hashlib.md5(os.urandom(32)).hexdigest()
)  # URL of the Dev app.js served by webpack & express
VERSION_NO = "1.0.1"

if env("CONSOLE_EMAIL_BACKEND", False):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SHOW_ROOT_API = env("SHOW_ROOT_API", False)
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", True)

TEMPLATE_TITLE = "Commercial Operator Licensing"
TEMPLATE_HEADER_LOGO = "/static/commercialoperator/img/logo-park-stay-trunc.gif"
TEMPLATE_GROUP = "parkswildlife"

LEDGER_TEMPLATE = "bootstrap5"
GDAL_LIBRARY_PATH = os.environ.get(
    "GDAL_LIBRARY_PATH",
)
GEOS_LIBRARY_PATH = os.environ.get(
    "GEOS_LIBRARY_PATH",
)
# Use git commit hash for purging cache in browser for deployment changes
GIT_COMMIT_HASH = os.popen(f"cd {BASE_DIR}; git log -1 --format=%H").read()
GIT_COMMIT_DATE = os.popen(f"cd {BASE_DIR}; git log -1 --format=%cd").read()
if len(GIT_COMMIT_HASH) == 0:
    GIT_COMMIT_HASH = os.popen("cat /app/git_hash").read()
    if len(GIT_COMMIT_HASH) == 0:
        logger.error("No git hash available to tag urls for pinned caching")
APPLICATION_VERSION = env("APPLICATION_VERSION", "1.0.0") + "-" + GIT_COMMIT_HASH[:7]

if SHOW_DEBUG_TOOLBAR:

    def show_toolbar(request):
        return True

    MIDDLEWARE_CLASSES += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]
    INSTALLED_APPS += ("debug_toolbar",)
    # INTERNAL_IPS = ('127.0.0.1', 'localhost', get_ip())
    INTERNAL_IPS = ("127.0.0.1", "localhost")

    # this dict removes check to dtermine if toolbar should display --> works for rks docker container
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": show_toolbar,
        "INTERCEPT_REDIRECTS": False,
    }

STATIC_URL = "/static/"


INSTALLED_APPS += [
    "reversion",
    "reversion_compare",
    "webtemplate_dbca",
    "ledger_api_client",
    "django_cron",
    "commercialoperator",
    "commercialoperator.components.approvals",
    "commercialoperator.components.bookings",
    "commercialoperator.components.compliances",
    "commercialoperator.components.main",
    "commercialoperator.components.organisations",
    "commercialoperator.components.segregation",
    "commercialoperator.components.permission",
    "commercialoperator.components.proposals",
    "commercialoperator.components.users",
    "taggit",
    "rest_framework",
    "rest_framework_datatables",
    "rest_framework_gis",
    "reset_migrations",
    "multiselectfield",
    "appmonitor_client",
    "django_vite",
    "wagov_utils.components.sri_utils",
]

# Not using django cron
INSTALLED_APPS.pop(INSTALLED_APPS.index("django_cron"))

ADD_REVERSION_ADMIN = True

# maximum number of days allowed for a booking
WSGI_APPLICATION = "commercialoperator.wsgi.application"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
        "rest_framework_datatables.renderers.DatatablesRenderer",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}


MIDDLEWARE_CLASSES += [
    "commercialoperator.middleware.BookingTimerMiddleware",
    "commercialoperator.middleware.FirstTimeNagScreenMiddleware",
    "commercialoperator.middleware.PaymentSessionMiddleware",
    "commercialoperator.middleware.RevisionOverrideMiddleware",
    "commercialoperator.middleware.ManagementCommandQueueMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]
MIDDLEWARE = MIDDLEWARE_CLASSES
MIDDLEWARE_CLASSES = None

TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "commercialoperator", "templates"))
TEMPLATES[0]["DIRS"].append(
    os.path.join(
        BASE_DIR, "commercialoperator", "components", "organisations", "templates"
    )
)
TEMPLATES[0]["DIRS"].append(
    os.path.join(BASE_DIR, "commercialoperator", "components", "emails", "templates")
)
TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "commercialoperator.context_processors.commercialoperator_url"
)

USE_DUMMY_CACHE = env("USE_DUMMY_CACHE", False)
if USE_DUMMY_CACHE:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        },
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": os.path.join(BASE_DIR, "commercialoperator", "cache"),
            "OPTIONS": {"MAX_ENTRIES": 10000},
        }
    }

CACHE_TIMEOUT_2_HOURS = 60 * 60 * 2
CACHE_KEY_FILE_EXTENSION_WHITELIST = "file-extension-whitelist"
FILE_SIZE_LIMIT_BYTES = env("FILE_SIZE_LIMIT_BYTES", 128000000)

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
STATICFILES_DIRS.append(
    os.path.join(os.path.join(BASE_DIR, "commercialoperator", "static"))
)
STATICFILES_DIRS.append(
    os.path.join(
        os.path.join(BASE_DIR, "commercialoperator", "static", "commercialoperator_vue")
    )
)

DATA_UPLOAD_MAX_NUMBER_FIELDS = None

# Department details
SYSTEM_NAME = env("SYSTEM_NAME", "Commercial Operator Licensing")
SYSTEM_NAME_SHORT = env("SYSTEM_NAME_SHORT", "COLS")
SITE_PREFIX = env("SITE_PREFIX")
SITE_DOMAIN = env("SITE_DOMAIN")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", "licensing@" + SITE_DOMAIN).lower()
SUPPORT_EMAIL_FILMING = env("SUPPORT_EMAIL_FILMING", "filming@" + SITE_DOMAIN).lower()
DEP_URL = env("DEP_URL", "www." + SITE_DOMAIN)
DEP_PHONE = env("DEP_PHONE", "(08) 9219 9978")
DEP_PHONE_FILMING = env("DEP_PHONE_FILMING", "(08) 9219 8411")
DEP_PHONE_SUPPORT = env("DEP_PHONE_SUPPORT", "(08) 9219 9000")
DEP_FAX = env("DEP_FAX", "(08) 9423 8242")
DEP_POSTAL = env(
    "DEP_POSTAL", "Locked Bag 104, Bentley Delivery Centre, Western Australia 6983"
)
DEP_NAME = env("DEP_NAME", "Department of Biodiversity, Conservation and Attractions")
DEP_NAME_SHORT = env("DEP_NAME_SHORT", "DBCA")
BRANCH_NAME = env("BRANCH_NAME", "Tourism and Concessions Branch")
DEP_ADDRESS = env("DEP_ADDRESS", "17 Dick Perry Avenue, Kensington WA 6151")
SITE_URL = env("SITE_URL", "https://" + SITE_PREFIX + "." + SITE_DOMAIN)
PUBLIC_URL = env("PUBLIC_URL", SITE_URL)
PUBLIC_URL = PUBLIC_URL if PUBLIC_URL.endswith(os.sep) else PUBLIC_URL + os.sep
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@" + SITE_DOMAIN).lower()
MEDIA_APP_DIR = env("MEDIA_APP_DIR", "cols")
ADMIN_GROUP = env("ADMIN_GROUP", "COLS Admin")

GROUP_NAME_ORGANISATION_ACCESS = env(
    "GROUP_NAME_ORGANISATION_ACCESS", "organisation_access_group"
)
GROUP_FINANCE = env("GROUP_FINANCE", "finance")
LEDGER_UI_CARDS_MANAGEMENT = True
LEDGER_UI_ACCOUNTS_MANAGEMENT = [
    {"first_name": {"options": {"view": True, "edit": True}}},
    {"last_name": {"options": {"view": True, "edit": True}}},
    {"residential_address": {"options": {"view": True, "edit": True}}},
    {"postal_same_as_residential": {"options": {"view": True, "edit": True}}},
    {"postal_address": {"options": {"view": True, "edit": True}}},
    {"phone_number": {"options": {"view": True, "edit": True}}},
    {"mobile_number": {"options": {"view": True, "edit": True}}},
]

COLS_EVENT_USERGUIDE_URL = env(
    "COLS_EVENT_USERGUIDE_URL", "https://parks.dpaw.wa.gov.au/for-business/how-apply-0"
)
COLS_HANDBOOK_URL = env(
    "COLS_HANDBOOK_URL",
    "https://parks.dpaw.wa.gov.au/know/commercial-operator-handbook",
)
COLS_FILMING_HANDBOOK_URL = env(
    "COLS_FILMING_HANDBOOK_URL",
    "https://parks.dpaw.wa.gov.au/know/commercial-filming-and-photography-handbook",
)
CRON_RUN_AT_TIMES = env("CRON_RUN_AT_TIMES", "04:05")
CRON_EMAIL = env("CRON_EMAIL", "cron@" + SITE_DOMAIN).lower()
# for ORACLE Job Notification - override settings_base.py
EMAIL_FROM = DEFAULT_FROM_EMAIL
OTHER_PAYMENT_ALLOWED = env("OTHER_PAYMENT_ALLOWED", False)  # Cash/Cheque

OSCAR_BASKET_COOKIE_OPEN = "cols_basket"
PAYMENT_SYSTEM_ID = env("PAYMENT_SYSTEM_ID", "S557")
PS_PAYMENT_SYSTEM_ID = PAYMENT_SYSTEM_ID
PAYMENT_SYSTEM_PREFIX = env(
    "PAYMENT_SYSTEM_PREFIX", PAYMENT_SYSTEM_ID.replace("S", "0")
)  # '0557'
os.environ["LEDGER_PRODUCT_CUSTOM_FIELDS"] = (
    "('ledger_description','quantity','price_incl_tax','price_excl_tax','oracle_code')"
)
CRON_NOTIFICATION_EMAIL = env("CRON_NOTIFICATION_EMAIL", NOTIFICATION_EMAIL).lower()
VERSION_NO = "1.0.1"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

TIME_ZONE = "Australia/Perth"
USE_TZ = True

if not VALID_SYSTEMS:
    VALID_SYSTEMS = [PAYMENT_SYSTEM_ID]

CRON_CLASSES = [
    "commercialoperator.cron.OracleIntegrationCronJob",
    "appmonitor_client.cron.CronJobAppMonitorClient",
]


BASE_URL = env("BASE_URL")

customColorPalette = [
    {"color": "hsl(4, 90%, 58%)", "label": "Red"},
    {"color": "hsl(340, 82%, 52%)", "label": "Pink"},
    {"color": "hsl(291, 64%, 42%)", "label": "Purple"},
    {"color": "hsl(262, 52%, 47%)", "label": "Deep Purple"},
    {"color": "hsl(231, 48%, 48%)", "label": "Indigo"},
    {"color": "hsl(207, 90%, 54%)", "label": "Blue"},
]

# Additional logging for commercialoperator
LOGGING["handlers"]["payment_checkout"] = {
    "level": "INFO",
    "class": "logging.handlers.RotatingFileHandler",
    "filename": os.path.join(BASE_DIR, "logs", "cols_payment_checkout.log"),
    "formatter": "verbose",
    "maxBytes": 5242880,
}
LOGGING["loggers"]["payment_checkout"] = {
    "handlers": ["payment_checkout"],
    "level": "INFO",
}

LOGGING["loggers"]["commercialoperator"] = {"handlers": ["file"], "level": "INFO"}

if DEBUG:
    LOGGING["formatters"]["verbose"] = {
        "format": "%(levelname)s %(asctime)s %(name)s [Line:%(lineno)s][%(funcName)s] %(message)s"
    }
    LOGGING["formatters"]["simple"] = {
        "format": "[Line:%(lineno)s][%(funcName)s] %(levelname)s %(message)s"
    }

    LOGGING["handlers"]["console"]["level"] = "DEBUG"
    LOGGING["handlers"]["console"]["formatter"] = "verbose"

    LOGGING["loggers"]["commercialoperator"] = {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    }

    LOGGING["loggers"][""] = {
        "handlers": ["console"],
        "level": "DEBUG",
    }

    LOGGING["loggers"]["django.server"] = {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    }

    LOGGING["loggers"]["asyncio"] = {
        "level": "WARNING",
    }

# Reporting limits
MAX_NUM_ROWS_MODEL_EXPORT = 100000
NUMBER_OF_QUEUE_JOBS = 5

# Cache timeouts
CACHE_TIMEOUT_5_SECONDS = 5
CACHE_TIMEOUT_10_SECONDS = 10
CACHE_TIMEOUT_1_MINUTE = 60
CACHE_TIMEOUT_5_MINUTES = 60 * 5
CACHE_TIMEOUT_2_HOURS = 60 * 60 * 2
CACHE_TIMEOUT_24_HOURS = 60 * 60 * 24
CACHE_TIMEOUT_NEVER = None

# Cache keys
CACHE_KEY_LEDGER_ORGANISATION = "ledger-organisation-{}"
CACHE_KEY_LEDGER_EMAIL_USER = "ledger-emailuser-{}"
CACHE_KEY_LEDGER_EMAIL_USER_BY_EMAIL = "ledger-emailuser-by-email-{}"
CACHE_KEY_LEDGER_USER_INFO = "ledger-user-info-{}"
CACHE_KEY_COUNTRY_LIST = "country-list"
CACHE_KEY_AMENDMENT_REQUEST_REASON_CHOICES = "amendment-request-reason-choices"
CACHE_KEY_COMPLIANCE_AMENDMENT_REASON_CHOICES = "compliance-amendment-reason-choices"
CACHE_KEY_ACCREDITATION_CHOICES = "accreditation-choices"
CACHE_KEY_LICENCE_PERIOD_CHOICES = "licence-period-choices"
CACHE_KEY_FILMING_LICENCE_CHARGE_CHOICES = "filming-licence-charge-choices"
CACHE_KEY_APPLICATION_TYPES = "application-types"
CACHE_KEY_PROPOSAL_SUBMITTERS = "proposal-submitters-{}"
CACHE_KEY_PROPOSAL_PROCESSING_STATUS = "proposal-processing-status-{}"
CACHE_KEY_PROPOSAL_KEYWORD_SEARCH = "proposal-keyword-search-{id}-{lodgement_number}"

# Error messages
INVOICE_NOT_FOUND = "Invoice not found"
ROUND_INVOICE_TOTALS = env("ROUND_INVOICE_TOTALS", False)

# API Exception message
# When debug is False, the following message will be sent to the user
# The real exception will be logged
API_EXCEPTION_MESSAGE = (
    "An error occurred while processing your request, "
    f"please try again and if the problem persists contact {SUPPORT_EMAIL}"
)

# CSRF token
CSRF_TRUSTED_ORIGINS_STRING = decouple.config("CSRF_TRUSTED_ORIGINS", default="[]")
CSRF_TRUSTED_ORIGINS = json.loads(str(CSRF_TRUSTED_ORIGINS_STRING))

# Ledger organisations interface
ORGANISATION_PERMISSION_MODULE = "commercialoperator.components.permission.permission"

LEDGER_UI_ORGANISATION_MANAGEMENT = [
    {"organisation_name": {"options": {"view": True, "edit": True}}},
    {"organisation_abn": {"options": {"view": True, "edit": True}}},
    {"organisation_trading_name": {"options": {"view": True, "edit": True}}},
    {"organisation_email": {"options": {"view": True, "edit": True}}},
    {"billing_address": {"options": {"view": True, "edit": True}}},
    {"postal_address": {"options": {"view": True, "edit": True}}},
]

DJANGO_VITE_DEV_MODE = env("DJANGO_VITE_DEV_MODE", False)
if DEBUG and not DJANGO_VITE_DEV_MODE:
    print(
        "\nServer running in DEBUG mode, frontend hot module reloading is OFF. Set env var DJANGO_VITE_DEV_MODE to True to enable hot module reloading.\n"
    )
else:
    print(
        "\nServer running in DEBUG mode, frontend hot module reloading is ON. Set env var DJANGO_VITE_DEV_MODE to False to disable hot module reloading.\n"
    )

STATIC_URL_PREFIX = (
    "/static/commercialoperator_vue/"
    if DJANGO_VITE_DEV_MODE
    else "commercialoperator_vue/"
)

DJANGO_VITE = {
    "default": {
        "dev_mode": DJANGO_VITE_DEV_MODE,
        "manifest_path": os.path.join(
            BASE_DIR,
            "commercialoperator",
            "static",
            "commercialoperator_vue",
            "manifest.json",
        ),
        "dev_server_host": "localhost",  # Default host for vite (can change if needed)
        "dev_server_port": env(
            "DJANGO_VITE_DEV_SERVER_PORT", 5173
        ),  # Default port for vite (can change if needed)
        "static_url_prefix": STATIC_URL_PREFIX,
    }
}


VUE3_ENTRY_SCRIPT = env(
    "VUE3_ENTRY_SCRIPT",
    default="src/main.js",  # This path will be auto prefixed with the       static_url_prefix from DJANGO_VITE above
)  # Path of the vue3 entry point script served by vite
