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
    """A season pack yields the title and is flagged as a pack."""
    result = extract_title_info(
        "Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG"
    )
    assert result.title == "Kaamelott"
    assert result.year is None
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
    assert result.type == "movie"
    assert result.is_season_pack is False


def test_extract_title_info_single_episode():
    """SxxEyy is recognised as a series targeting specific episodes."""
    result = extract_title_info("Show.Name.S01E02.FRENCH.1080p.WEB.x264-GROUP")
    assert result.title == "Show Name"
    assert result.type == "series"
    assert result.is_season_pack is False


def test_extract_title_info_french_season_word():
    """Saison N and cross notation (1x02) are recognised as series."""
    result = extract_title_info("Kaamelott.Saison.3.VOSTFR.1080p.WEB.x264")
    assert result.title == "Kaamelott"
    assert result.type == "series"
    assert result.is_season_pack is True

    result = extract_title_info("Old.Show.1x02.FRENCH.DVDRip.DivX")
    assert result.title == "Old Show"
    assert result.type == "series"
    assert result.is_season_pack is False


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


def test_extract_title_info_integrale_series_set():
    """INTEGRALE marks a full-series pack: not part of the title, type series."""
    result = extract_title_info(
        "Malcolm.INTEGRALE.MULTi.1080p.WEBLight.AAC.2.0.H265-SahKelPlaisir"
    )
    assert result.title == "Malcolm"
    assert result.type == "series"
    assert result.is_season_pack is True


def test_extract_title_info_non_video_file():
    """A non-video file (pdf, zip, music, ...) yields an empty result."""
    result = extract_title_info("Investir - 10 Octobre 2026.pdf")
    assert result.title is None
    assert result.year is None
    assert result.type is None
    assert result.is_season_pack is False

    result = extract_title_info("Discographie.Complete.2020.FLAC.zip")
    assert result.title is None

    result = extract_title_info("Vacances.2024.jpg")
    assert result.title is None


def test_extract_title_info_video_game_repack():
    """Video game repacks (FitGirl, crack groups) are not movies or shows."""
    result = extract_title_info("Divinity - Original Sin 2 [FitGirl Repack]")
    assert result.title is None
    assert result.type is None

    result = extract_title_info("Elden.Ring.v1.02.CrackOnly-CODEX")
    assert result.title is None

    result = extract_title_info("Cyberpunk.2077.Phantom.Liberty.MULTi13-GOG")
    assert result.title is None


def test_torrent_is_video():
    """The content check filters non-video folders that look like titles."""
    from utils.stremio import torrent_is_video

    # RPG book collections: names look like titles, files are all PDFs.
    assert torrent_is_video("D&D 5", ["D&D 5/Players Handbook.pdf"]) is False
    assert torrent_is_video("pathfinder2e_collection_fr", ["core-rulebook.pdf"]) is False

    # No file list: fall back to trusting the name.
    assert torrent_is_video("D&D 5", []) is True

    # Regular movies/shows with video files.
    assert torrent_is_video("Some.Movie.2023.FRENCH.1080p.WEB.x264", ["Some.Movie.2023.mkv"]) is True
    assert torrent_is_video("Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG", []) is True

    # A video file inside a folder that also contains other files is video.
    assert torrent_is_video("Movie.Pack", ["Movie.Pack/movie.mkv", "Movie.Pack/cover.jpg"]) is True


def test_normalize_poster_url():
    """Scheme-less URLs get https://; full URLs and None pass through."""
    from utils.stremio import normalize_poster_url

    assert (
        normalize_poster_url("media.trakt.tv/images/posters/medium/7d648ba4cb.jpg.webp")
        == "https://media.trakt.tv/images/posters/medium/7d648ba4cb.jpg.webp"
    )
    assert (
        normalize_poster_url("https://pictures.betaseries.com/films/140245.jpg")
        == "https://pictures.betaseries.com/films/140245.jpg"
    )
    assert normalize_poster_url("http://example.com/a.jpg") == "http://example.com/a.jpg"
    assert normalize_poster_url(None) is None
    assert normalize_poster_url("") is None
