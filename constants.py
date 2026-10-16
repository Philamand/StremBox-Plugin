TRENDING_CATALOG_ID = "trending"
LIBRARY_CATALOG_ID = "library"

# Maximum certification rating a user can see, as a single unified scale
# shared by movies and series: each entry covers the equivalent movie and TV
# ratings (e.g. "r" matches both R and TV-MA). "Not Rated" is excluded.
CERTIFICATIONS = [
    {
        "name": "G",
        "slug": "g",
        "description": "All Ages (G, TV-Y, TV-G)",
    },
    {
        "name": "PG-7",
        "slug": "pg-7",
        "description": "Older Children - Ages 7+ Recommended (TV-Y7)",
    },
    {
        "name": "PG",
        "slug": "pg",
        "description": "Parental Guidance Suggested (PG, TV-PG)",
    },
    {
        "name": "PG-13",
        "slug": "pg-13",
        "description": "Parents Strongly Cautioned - Ages 13+ Recommended (PG-13, TV-14)",
    },
    {
        "name": "R",
        "slug": "r",
        "description": "Mature Audiences - Ages 17+ Recommended (R, TV-MA)",
    },
]

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
