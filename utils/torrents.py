import bencode2


def modify_info_hash(input_file: str, output_file: str) -> None:
    """
    Modify the info hash of a torrent file.

    Args:
        input_file (str): Path to the input torrent file.
        output_file (str): Path to the output torrent file.
    """
    with open(input_file, "rb") as f:
        torrent_data = f.read()

    torrent_dict = bencode2.bdecode(torrent_data)
    torrent_dict[b"announce"] = "udp://open.stealth.si:80/announce"
    torrent_dict[b"info"][b"modified_by"] = "StremBox-Plugin"
    torrent_dict[b"info"][b"modified_for"] = "user"

    with open(output_file, "wb") as f:
        f.write(bencode2.bencode(torrent_dict))
