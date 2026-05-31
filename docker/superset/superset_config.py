import os

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "SUPERSET_SECRET_KEY is not set. Add it to your local .env file before starting Superset."
    )

MAPBOX_API_KEY = ""

DECKGL_BASE_MAP = [
    ["https://tile.openstreetmap.org/{z}/{x}/{y}.png", "Streets (OSM)"],
    ["https://c.tile.openstreetmap.org/{z}/{x}/{y}.png", "OpenStreetMap"],
]

# Local portfolio dashboard only:
# allow iframe embeds in Markdown so the standalone Folium maps can be embedded.
HTML_SANITIZATION = True

HTML_SANITIZATION_SCHEMA_EXTENSIONS = {
    "attributes": {
        "*": [
            "style",
            "className",
            "src",
            "width",
            "height",
            "frameborder",
            "marginwidth",
            "marginheight",
            "scrolling",
            "target",
            "loading",
            "allow",
            "allowfullscreen",
            "referrerpolicy",
        ],
        "iframe": [
            "src",
            "width",
            "height",
            "style",
            "frameborder",
            "marginwidth",
            "marginheight",
            "scrolling",
            "loading",
            "allow",
            "allowfullscreen",
            "referrerpolicy",
        ],
    },
    "tagNames": ["style", "iframe"],
}

# Local portfolio dashboard only:
# allow embedding locally served Folium HTML maps in Superset Markdown iframes.
TALISMAN_CONFIG = {
    "content_security_policy": {
        "base-uri": ["'self'"],
        "default-src": ["'self'"],
        "img-src": [
            "'self'",
            "blob:",
            "data:",
            "https://apachesuperset.gateway.scarf.sh",
            "https://static.scarf.sh/",
            "ows.terrestris.de",
        ],
        "worker-src": ["'self'", "blob:"],
        "connect-src": [
            "'self'",
            "https://api.mapbox.com",
            "https://events.mapbox.com",
        ],
        "frame-src": [
            "'self'",
            "http://localhost:8090",
            "http://127.0.0.1:8090",
        ],
        "object-src": "'none'",
        "style-src": ["'self'", "'unsafe-inline'"],
        "script-src": ["'self'", "'strict-dynamic'"],
    },
    "content_security_policy_nonce_in": ["script-src"],
    "force_https": False,
    "session_cookie_secure": False,
}

TALISMAN_DEV_CONFIG = {
    "content_security_policy": {
        "base-uri": ["'self'"],
        "default-src": ["'self'"],
        "img-src": [
            "'self'",
            "blob:",
            "data:",
            "https://apachesuperset.gateway.scarf.sh",
            "https://static.scarf.sh/",
            "https://cdn.brandfolder.io",
            "ows.terrestris.de",
        ],
        "worker-src": ["'self'", "blob:"],
        "connect-src": [
            "'self'",
            "https://api.mapbox.com",
            "https://events.mapbox.com",
        ],
        "frame-src": [
            "'self'",
            "http://localhost:8090",
            "http://127.0.0.1:8090",
        ],
        "object-src": "'none'",
        "style-src": ["'self'", "'unsafe-inline'"],
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    },
    "content_security_policy_nonce_in": ["script-src"],
    "force_https": False,
    "session_cookie_secure": False,
}
