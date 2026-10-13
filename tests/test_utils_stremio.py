# This file is AI-generated
"""Tests for ``utils.stremio.check_title_match``."""

from schemas.torrents import TorrentTitleInfo
from utils.stremio import check_title_match, extract_title_info


def test_check_title_match_series_season_pack():
    """A season pack of the target series matches on the English title."""
    result = check_title_match(
        torrent_name="Kaamelott.S04.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG",
        title_fr=None,
        title_en="kaamelott",
    )
    assert result is True


def test_check_title_match_different_movie_same_root():
    """A different movie sharing the same root word does not match."""
    result = check_title_match(
        torrent_name=(
            "Kaamelott.Deuxieme.Volet.Partie.1.2025.FRENCH.AD.1080p."
            "WEBrip.10.bits.EAC3.5.1.x265-TyHD.mkv"
        ),
        title_fr=None,
        title_en="kaamelott",
    )
    assert result is False


def test_check_title_match_movie_french_title_with_accents():
    """A movie matches on the French title even with accents and punctuation."""
    result = check_title_match(
        torrent_name=(
            "28.Ans.Plus.Tard.Le.Temple.Des.Morts.2026.Multi.VFF.2160p."
            "Webrip.DV.HDR10Plus.EAC3.5.1.x265-Neostark.mkv"
        ),
        title_fr="28 Ans plus tard : Le Temple des morts",
        title_en="28 Years Later: The Bone Temple",
    )
    assert result is True


def test_check_title_match_series_apostrophe_in_title():
    """A series with an apostrophe in the English title matches the torrent.

    The torrent name uses ``Gabbys`` (no apostrophe) while the English title
    is ``Gabby's Dollhouse``. Normalisation turns the apostrophe into a space
    (``gabby s dollhouse``) which no longer matches ``gabbys dollhouse``.
    """
    result = check_title_match(
        torrent_name="Gabbys.Dollhouse.S01.MULTi.1080p.WEB.x264-FW",
        title_fr="Gabby et la maison magique",
        title_en="Gabby's Dollhouse",
    )
    assert result is True


# ---------------------------------------------------------------------------
# extract_title_info
# ---------------------------------------------------------------------------


def test_extract_title_info_series_season_pack():
    """A season pack yields the title and season with no episode."""
    result = extract_title_info(
        "Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG"
    )
    assert result.title == "Kaamelott"
    assert result.year is None
    assert result.season == 5
    assert result.episode_start is None
    assert result.type == "series"
    assert result.is_season_pack is True


def test_extract_title_info_movie_with_year():
    """A movie name yields title and year."""
    result = extract_title_info(
        "28.Ans.Plus.Tard.Le.Temple.Des.Morts.2026.Multi.VFF.2160p."
        "Webrip.DV.HDR10Plus.EAC3.5.1.x265-Neostark.mkv"
    )
    assert result.title == "28 Ans Plus Tard Le Temple Des Morts"
    assert result.year == 2026
    assert result.season is None
    assert result.type == "movie"
    assert result.is_season_pack is False


def test_extract_title_info_single_episode():
    """SxxEyy yields season and episode numbers."""
    result = extract_title_info("Show.Name.S01E02.FRENCH.1080p.WEB.x264-GROUP")
    assert result.title == "Show Name"
    assert result.season == 1
    assert result.episode_start == 2
    assert result.episode_end is None
    assert result.type == "series"
    assert result.is_season_pack is False


def test_extract_title_info_episode_range():
    """SxxEyy-Ezz yields an episode range."""
    result = extract_title_info("Show.Name.S01E02-E04.720p.WEB-DL.x264")
    assert result.title == "Show Name"
    assert result.season == 1
    assert result.episode_start == 2
    assert result.episode_end == 4


def test_extract_title_info_french_season_word():
    """Saison N and cross notation (1x02) are recognised."""
    result = extract_title_info("Kaamelott.Saison.3.VOSTFR.1080p.WEB.x264")
    assert result.title == "Kaamelott"
    assert result.season == 3

    result = extract_title_info("Old.Show.1x02.FRENCH.DVDRip.DivX")
    assert result.title == "Old Show"
    assert result.season == 1
    assert result.episode_start == 2


def test_extract_title_info_stops_at_first_tag():
    """Tokens after the first tag are not part of the title."""
    result = extract_title_info("Gabbys.Dollhouse.S01.MULTi.1080p.WEB.x264-FW")
    assert result.title == "Gabbys Dollhouse"


def test_extract_title_info_unknown_tokens_kept_in_title():
    """Unknown leading tokens (e.g. subtitle tags) stay in the title."""
    result = extract_title_info("Kaamelott.Deuxieme.Volet.Partie.1.2025.FRENCH.AD.1080p.WEBrip")
    assert result.title == "Kaamelott Deuxieme Volet Partie 1"
    assert result.year == 2025
    assert result.type == "movie"


def test_extract_title_info_empty_name():
    """An empty name returns all-None fields."""
    result = extract_title_info("")
    assert result.title is None
    assert result.type is None


def test_extract_title_info_returns_schema():
    """The parser returns a TorrentTitleInfo instance."""
    result = extract_title_info("Movie.Name.2020.FRENCH.1080p.WEB.x264-GROUP")
    assert isinstance(result, TorrentTitleInfo)
    assert result.title == "Movie Name"
    assert result.year == 2020
