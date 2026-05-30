import os

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "change-this-in-env")

MAPBOX_API_KEY = ""

DECKGL_BASE_MAP = [
    ["https://tile.openstreetmap.org/{z}/{x}/{y}.png", "Streets (OSM)"],
    ["https://c.tile.openstreetmap.org/{z}/{x}/{y}.png", "OpenStreetMap"],
]
