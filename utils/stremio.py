import re
import unicodedata
from urllib.parse import urlparse

import aiohttp

from http_client import get_session
from schemas.bauxite import DownloadRequest


def extract_download_params(url) -> DownloadRequest:
    """Extract download parameters from a URL."""
    if "?" in url:
        path, query = url.split("?", 1)
    else:
        path, query = url, ""

    torrent_hash: str | None = (
        path.strip("/").split("/")[-1] if path.strip("/") else None
    )

    params: dict[str, str] = {}
    if query:
        for param in query.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value

    tracker = params.get("tracker")
    api_key = params.get("api_key")
    torrent_id_str = params.get("torrent_id")

    if torrent_hash is None or tracker is None or api_key is None:
        raise ValueError("Missing required parameters")

    torrent_id: int | None = int(torrent_id_str) if torrent_id_str else None

    return DownloadRequest(
        torrent_hash=torrent_hash,
        tracker=tracker,
        api_key=api_key,
        torrent_id=torrent_id,
    )


def merge_result_into(
    results: list[dict],
    r: dict,
    *,
    update_only_if_low_seeders: bool = False,
) -> bool:
    """Try to merge *r* into an existing entry in *results* with the same size.

    When a matching entry is found the tracker name and torrent list are always
    extended. The primary fields (seeders, name, info_hash, …) are updated only
    when *r* has more seeders than the existing entry; if *update_only_if_low_seeders*
    is ``True`` the update also requires the existing entry to have fewer than 10
    seeders (useful for series where we avoid demoting a well-seeded source).

    Returns ``True`` when *r* was merged, ``False`` when no matching entry was
    found (caller should append *r* to *results* instead).
    """
    for existing in results:
        if existing["size"] == r["size"]:
            can_update = r["seeders"] > existing["seeders"]
            if update_only_if_low_seeders:
                can_update = can_update and existing["seeders"] < 10
            if can_update:
                existing["seeders"] = r["seeders"]
                existing["leechers"] = r["leechers"]
                existing["name"] = r["name"]
                existing["info_hash"] = r["info_hash"]
                existing["link"] = r["link"]
            existing["tracker_name"] += " / " + r["tracker_name"]
            existing["torrents"].append(
                {"hash": r["info_hash"], "name": r["name"], "link": r["link"]}
            )
            return True
    return False


def sort_dicts_by_seeders_desc(items: list[dict]) -> list[dict]:
    """Return dictionaries sorted by the ``seeders`` key in descending order.

    Args:
        items: A list of dictionaries, each containing a ``seeders`` key.

    Returns:
        A new list sorted from largest to smallest ``seeders`` value.

    Raises:
        KeyError: If at least one dictionary does not contain the ``seeders`` key.
        TypeError: If ``seeders`` values cannot be compared with each other.
    """
    return sorted(items, key=lambda my_dict: my_dict["seeders"], reverse=True)


def check_season_episode(name, target_season, target_episode):
    """Check if the torrent corresponds to the target season/episode.

    Args:
        name (str): The torrent name.
        target_season (int): The target season number.
        target_episode (int): The target episode number.

    Returns:
        bool: True if the torrent matches the target season/episode, False otherwise.

    Source: https://github.com/aymene69/frenchio
    """
    if target_season is None:
        return True

    basename = re.split(r"[/\\]", name)[-1]
    name_upper = basename.upper()

    se_pattern = re.compile(
        r"(?:S|SAISON|SEASON)[ ._-]?(\d{1,2})(?:[ ._-]?E(\d{1,2}))(?:(?:[ ._-]*(?:E|-|~)[ ._-]*)(\d{1,2}))?",
        re.IGNORECASE,
    )
    matches = se_pattern.findall(name_upper)

    if not matches:
        x_pattern = re.compile(r"(\d{1,2})x(\d{1,2})", re.IGNORECASE)
        matches = [(m[0], m[1], None) for m in x_pattern.findall(name_upper)]

    if not matches:
        s_only_pattern = re.compile(
            r"(?:S|SAISON|SEASON)[ ._-]?(\d{1,2})", re.IGNORECASE
        )
        matches = [(m, None, None) for m in s_only_pattern.findall(name_upper)]

    if not matches:
        return False

    for s, e_start, e_end in matches:
        try:
            season = int(s)
            if season != target_season:
                continue

            if e_start is None:
                return True

            start = int(e_start)
            end = int(e_end) if e_end else start

            if start <= target_episode <= end:
                return True

        except ValueError:
            continue

    return False


async def get_torrent_name(imdb_id: str, media_type: str):
    """Fetch the torrent name and year for a given IMDb ID and media type.

    Args:
        imdb_id (str): The IMDb ID of the media.
        media_type (str): The media type (e.g., "movie", "series").

    Returns:
        tuple: A tuple containing the torrent name (str) and year (int or None).
    """
    session = get_session()
    try:
        async with session.get(
            f"https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
        ) as response:
            data = await response.json()
            name = data.get("meta", {}).get("name")
            year = (
                int(data.get("meta", {}).get("year").split("–")[0])
                if data.get("meta", {}).get("year")
                else None
            )
            return name, year
    except (aiohttp.ClientError, KeyError, ValueError):
        return None, None


def normalize_title(title: str) -> str:
    """Normalize a title by removing accents, punctuation, and special characters, and converting to lowercase.

    Args:
        title (str): The title to normalize.

    Returns:
        str: The normalized title.
    """
    if not title:
        return ""

    title = (
        unicodedata.normalize("NFD", title).encode("ascii", "ignore").decode("utf-8")
    )

    # Strip apostrophes so that "Gabby's" and "Gabbys" normalise identically.
    title = title.replace("'", "")

    title = re.sub(r"[^\w\s]", " ", title)

    return " ".join(title.lower().split())


def check_title_match(torrent_name, title_fr, title_en, year=None, is_movie=False):
    """Check if the torrent name matches the title (French or English).

    Args:
        torrent_name (str): The name of the torrent.
        title_fr (str): The French title of the media.
        title_en (str): The English title of the media.
        year (int, optional): The year of the media. Defaults to None.
        is_movie (bool, optional): Whether the media is a movie. Defaults to False.

    Returns:
        bool: True if a match is found, False otherwise.
    """
    if not title_fr and not title_en:
        return True

    norm_torrent = normalize_title(torrent_name)
    norm_fr = normalize_title(title_fr)
    norm_en = normalize_title(title_en)

    tech_tags = {
        "1080p",
        "720p",
        "4k",
        "2160p",
        "uhd",
        "dvd",
        "sd",
        "bluray",
        "brrip",
        "bdrip",
        "webrip",
        "web",
        "webdl",
        "dvdrip",
        "cam",
        "ts",
        "vff",
        "vf",
        "vfq",
        "vf2",
        "vostfr",
        "multi",
        "truefrench",
        "french",
        "eng",
        "english",
        "en",
        "vo",
        "fr",
        "x264",
        "x265",
        "hevc",
        "h264",
        "h265",
        "av1",
        "hdr",
        "dv",
        "dolby",
        "vision",
        "10bit",
        "light",
        "repack",
        "proper",
        "internal",
        "extended",
        "uncut",
        "subfrench",
        "subforced",
        "nf",
        "netflix",
        "amzn",
        "amazon",
        "dnp",
        "dsnp",
        "hmax",
        "ac3",
        "dts",
        "dd5",
        "dd2",
        "aac",
        "mkv",
        "mp4",
        "avi",
        "tv",
        "show",
        "complete",
        "integrale",
        "integra",
        "vol",
        "volume",
        "part",
        "party",
        "dual",
        "hdtv",
    }

    def is_strict_match(target, torrent):
        if not target:
            return False

        pattern = r"\b" + re.escape(target) + r"\b"
        match = re.search(pattern, torrent)
        if not match:
            return False

        end_idx = match.end()
        after_text = torrent[end_idx:].strip()
        if not after_text:
            return True

        next_word = after_text.split()[0]

        if re.match(r"^(19|20)\d{2}$", next_word):
            return True
        if re.match(r"^[sx]\d+$", next_word):
            return True
        if re.match(r"^s\d+e\d+$", next_word):
            return True
        if next_word in tech_tags:
            return True

        return next_word in norm_fr.split() or next_word in norm_en.split()

    title_match = is_strict_match(norm_fr, norm_torrent) or is_strict_match(
        norm_en, norm_torrent
    )

    if not title_match:
        return False
    if is_movie and year:
        try:
            y = int(year)

            if (
                str(y) not in norm_torrent
                and str(y - 1) not in norm_torrent
                and str(y + 1) not in norm_torrent
            ):
                return False
        except ValueError:
            if str(year) not in norm_torrent:
                return False

    return True


def parse_torrent_name(name: str):
    """Parse the torrent name to extract quality, codec, language, and release type."""
    if not name:
        return {
            "name": "",
            "quality": "",
            "codec": "",
            "language": "",
            "release_type": "",
        }

    name_upper = name.upper()

    quality = ""
    if any(q in name_upper for q in ["2160P", "4K", "UHD"]):
        quality = "4K"
    elif "1080P" in name_upper:
        quality = "1080p"
    elif "720P" in name_upper:
        quality = "720p"
    elif any(q in name_upper for q in ["480P", "SD", "DVD"]):
        quality = "SD"

    codec = ""
    if any(c in name_upper for c in ["X265", "HEVC", "H265"]):
        codec = "x265"
    elif any(c in name_upper for c in ["X264", "AVC", "H264"]):
        codec = "x264"
    elif "AV1" in name_upper:
        codec = "AV1"

    extras = []
    if "HDR" in name_upper:
        extras.append("HDR")
    if any(dv in name_upper for dv in ["DV", "DOLBY VISION"]):
        extras.append("DV")
    if "10BIT" in name_upper:
        extras.append("10bit")

    release_type = ""
    if "WEBRIP" in name_upper:
        release_type = "WebRIP"
    elif "WEB-DL" in name_upper or "WEBDL" in name_upper or "WEB" in name_upper:
        release_type = "WEB-DL"
    elif any(br in name_upper for br in ["BRRIP", "BDRIP", "BLURAY", "BDLIGHT"]):
        release_type = "BDRip"
    elif "DVDRIP" in name_upper:
        release_type = "DVDRip"
    elif "CAM" in name_upper or "TS" in name_upper:
        release_type = "CAM"

    languages = []
    if "MULTI" in name_upper:
        languages.append("Multi")
    if "VOSTFR" in name_upper:
        languages.append("VOSTFR")
    if "TRUEFRENCH" in name_upper or "VFF" in name_upper:
        languages.append("VFF")
    elif "VF2" in name_upper:
        languages.append("VF2")
    elif "VFQ" in name_upper:
        languages.append("VFQ")
    elif "FRENCH" in name_upper or "VF" in name_upper:
        languages.append("VF")

    if not languages and (
        "EN" in name_upper or "VO" in name_upper or "ENG" in name_upper
    ):
        languages.append("VO")

    display_langs = []
    for lang in languages:
        if lang == "Multi":
            display_langs.append("🇫🇷+🇺🇸 MULTI")
        elif lang == "VFF":
            display_langs.append("🇫🇷 VFF")
        elif lang == "VF":
            display_langs.append("🇫🇷 VF")
        elif lang == "VFQ":
            display_langs.append("🇨🇦 VFQ")
        elif lang == "VOSTFR":
            display_langs.append("🇫🇷🇺🇸 VOSTFR")
        elif lang == "VO":
            display_langs.append("🇺🇸 VO")

    title_parts = []
    if quality:
        title_parts.append(f"📺 {quality}")
    if release_type:
        title_parts.append(f"📦 {release_type}")
    if codec:
        title_parts.append(f"🎞️ {codec}")
    if extras:
        title_parts.append(f"✨ {' '.join(extras)}")
    if display_langs:
        title_parts.append(f"{' '.join(display_langs)}")

    return " | ".join(title_parts)


def get_torrent_tracker_and_id(link: str) -> tuple:
    """Extract the tracker and torrent ID from a torrent download link.

    Args:
        link (str): The torrent download link. Supports formats like:
                    - https://api.torr9.net/api/v1/torznab/torrents/183639/download?passkey=passkey
                    - https://c411.org/api?t=get&id=3cea3059a4ece9830bbcb240f1ec028f9e3ebef9&apikey=

    Returns:
        tuple: A tuple with (tracker, torrent_id).
              For c411, torrent_id will be None.
              Returns (None, None) if extraction fails.

    Example:
        >>> get_torrent_tracker_and_id("https://api.torr9.net/api/v1/torznab/torrents/183639/download?passkey=passkey")
        ('torr9', '183639')
        >>> get_torrent_tracker_and_id("https://c411.org/api?t=get&id=3cea3059a4ece9830bbcb240f1ec028f9e3ebef9&apikey=")
        ('c411', None)
    """
    try:
        parsed_url = urlparse(link)
        hostname = parsed_url.hostname or ""

        tracker = None
        if "torr9" in hostname:
            tracker = "torr9"
        elif "c411" in hostname:
            tracker = "c411"
        else:
            match = re.search(r"(?:api\.)?(\w+)\.", hostname)
            if match:
                tracker = match.group(1)

        torrent_id = None
        if tracker == "c411":
            torrent_id = None
        else:
            path = parsed_url.path
            match = re.search(r"/torrents/(\d+)/", path)
            if match:
                torrent_id = match.group(1)

        return tracker, torrent_id
    except (ValueError, AttributeError):
        return None, None


# Tokens that mark the end of the title part of a scene release name. Anything
# from the first matching token onward is a technical/language/release tag.
_TAG_TOKEN_PATTERN = re.compile(
    r"""^(?:
        (?P<season_marker>
            S\d{1,2}(?:E\d{1,3})?
            | SAISON[ ._-]?\d{1,2}
            | SEASON[ ._-]?\d{1,2}
            | E\d{1,3}
            | \d{1,2}x\d{1,2}
        )
        | (?P<resolution>2160P | 1080P | 720P | 480P | 4K | UHD)
        | (?P<source>DVD(?:RIP)? | BLU-?RAY | BRRIP | BDRIP | BDLIGHT | WEB(?:-?DL | DL | RIP)? | HDTV | CAM | TS | PDTV | SD)
        | (?P<codec>X26[45] | H26[45] | HEVC | AVC | AV1 | XVID | DIVX)
        | (?P<audio>AC3 | EAC3 | DDP(?:\.\d|\d)? | DTS(?:-HD)? | TRUEHD | ATMOS | AAC(?:\.\d|\d)? | FLAC | MP3)
        | (?P<language>MULTI(?:[FSHI])? | VOST(?:FR)? | VFF | VFQ | VF2 | VFI | VFA | TRUEFRENCH | FRENCH | VOF | VF | SUBFRENCH | ENGLISH | ENG | EN | DUAL)
        | (?P<misc>HDR10(?:PLUS)? | HDR | DV | DOLBY[ ._-]?VISION | 10BIT | 8BIT | 60FPS | PROPER | REPACK | REMUX | INTERNAL | LIMITED | EXTENDED | UNRATED | REMASTERED | COMPLETE | NOTAG | HYBRID)
    )$""",
    re.VERBOSE | re.IGNORECASE,
)

_YEAR_PATTERN = re.compile(r"^(19\d{2}|20\d{2})$")

# SEASON MARKER: S01, S01E02, Saison 3, E04, 1x02. Groups: season, episode,
# optional end episode of a range (S01E02-E04).
_SEASON_EPISODE_PATTERN = re.compile(
    r"(?<!\d)(S(?:AISON|EASON)?[ ._-]?(\d{1,2}))"
    r"(?:[ ._-]?E(\d{1,3}))?"
    r"(?:[ ._-]*(?:E|-|~)[ ._-]*(\d{1,3}))?"
    r"(?!\d)",
    re.IGNORECASE,
)

_EPISODE_ONLY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:E|EP)[ ._-]?(\d{1,3})(?!\d)", re.IGNORECASE
)

_SEASON_WORD_PATTERN = re.compile(r"^(?:SAISON|SEASON)$", re.IGNORECASE)

_CROSS_PATTERN = re.compile(r"(?<!\d)(\d{1,2})x(\d{1,3})(?!\d)", re.IGNORECASE)

_EXTENSION_PATTERN = re.compile(r"\.[a-z0-9]{2,4}$", re.IGNORECASE)


def extract_title_info(name: str) -> dict:
    """Extract the title, year, season and episode from a torrent name.

    The title is the leading part of the name, up to the first token that
    looks like a technical tag (resolution, source, codec, audio, language,
    release group) or a season/episode/year marker. Unknown tokens are kept
    as part of the title so unusual scene names do not truncate it.

    Args:
        name (str): The raw torrent name, e.g.
            ``"Movie.Name.2023.FRENCH.1080p.WEB.x264-GROUP"``.

    Returns:
        dict: With keys:

        - ``title`` (str | None): extracted title, separators replaced by
          spaces; ``None`` when nothing could be extracted.
        - ``year`` (int | None): release year.
        - ``season`` (int | None): season number.
        - ``episode_start`` (int | None): episode number, or first episode
          of a range.
        - ``episode_end`` (int | None): last episode when the name encodes a
          range, ``None`` otherwise.
        - ``type`` (str): ``"series"`` when season/episode markers were
          found, ``"movie"`` otherwise.
        - ``is_season_pack`` (bool): ``True`` when a season was found but
          no episode.

    Example:
        >>> extract_title_info("Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG")["title"]
        'Kaamelott'
    """
    empty = {
        "title": None,
        "year": None,
        "season": None,
        "episode_start": None,
        "episode_end": None,
        "type": None,
        "is_season_pack": False,
    }
    if not name:
        return empty

    basename = re.split(r"[/\\]", name)[-1].strip()

    # An extension (.mkv, .avi, ...) never contributes to the title.
    root = _EXTENSION_PATTERN.sub("", basename)
    tokens = re.split(r"[._ ]", root)

    title_tokens = []
    year = None
    season = None
    episode_start = None
    episode_end = None

    for token in tokens:
        if _YEAR_PATTERN.match(token):
            year = int(token)
            break

        if (
            _SEASON_EPISODE_PATTERN.search(token)
            or _SEASON_WORD_PATTERN.match(token)
            or _EPISODE_ONLY_PATTERN.search(token)
            or _CROSS_PATTERN.search(token)
        ):
            break

        if _TAG_TOKEN_PATTERN.match(token):
            break

        title_tokens.append(token)

    title = " ".join(t for t in title_tokens if t) or None

    season_match = _SEASON_EPISODE_PATTERN.search(root)
    if season_match:
        season = int(season_match.group(2))
        if season_match.group(3):
            episode_start = int(season_match.group(3))
            if season_match.group(4):
                episode_end = int(season_match.group(4))
    else:
        cross_match = _CROSS_PATTERN.search(root)
        if cross_match:
            season = int(cross_match.group(1))
            episode_start = int(cross_match.group(2))
        else:
            ep_match = _EPISODE_ONLY_PATTERN.search(root)
            if ep_match:
                episode_start = int(ep_match.group(1))

    media_type = "series" if season is not None or episode_start is not None else "movie"
    is_season_pack = media_type == "series" and episode_start is None

    return {
        "title": title,
        "year": year,
        "season": season,
        "episode_start": episode_start,
        "episode_end": episode_end,
        "type": media_type,
        "is_season_pack": is_season_pack,
    }
