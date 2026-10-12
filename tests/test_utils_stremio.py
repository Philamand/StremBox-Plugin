# This file is AI-generated
"""Tests for ``utils.stremio.check_title_match``."""

from utils.stremio import check_title_match


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
