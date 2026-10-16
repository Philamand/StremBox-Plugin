TRENDING_CATALOG_ID = "trending"

MANIFEST = {
    "id": "StremBox-Plugin/Philamand/org.codeberg",
    "version": "1.0.0",
    "name": "StremBox-Plugin",
    "description": "Sample addon made with FastAPI providing a few public domain movies",
    "types": ["movie", "series"],
    "catalogs": [
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
