TRENDING_CATALOG_ID = "trending"
LIBRARY_CATALOG_ID = "library"

MANIFEST = {
    "id": "StremBox-Plugin/Philamand/org.codeberg",
    "version": "1.0.0",
    "name": "StremBox-Plugin",
    "description": "Sample addon made with FastAPI providing a few public domain movies",
    "types": ["movie", "series"],
    "catalogs": [
        {
            "type": "movie",
            "id": "library",
            "name": "Librairie",
        },
        {
            "type": "series",
            "id": "library",
            "name": "Librairie",
        },
        {
            "type": "movie",
            "id": "trending",
            "name": "Tendances",
            "extra": [{"name": "search", "isRequired": False}],
        },
        {
            "type": "series",
            "id": "trending",
            "name": "Tendances",
            "extra": [{"name": "search", "isRequired": False}],
        },
    ],
    "resources": [
        {
            "name": "stream",
            "types": ["movie", "series"],
            "idPrefixes": ["tt", "hpy"],
        },
        {
            "name": "catalog",
            "types": ["movie", "series"],
            "idPrefixes": ["tt"],
        },
        {
            "name": "meta",
            "types": ["movie", "series"],
            "idPrefixes": ["tt"],
        },
    ],
}
