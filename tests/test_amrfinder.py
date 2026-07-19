from resistsense.amrfinder import parse_amrfinder_tsv


def test_amrfinder_parser_accepts_current_style_columns(tmp_path) -> None:
    path = tmp_path / "amr.tsv"
    path.write_text(
        "Gene symbol\tElement type\tElement subtype\t% Identity\t% Coverage of reference sequence\tClass\tSubclass\n"
        "blaCTX-M-15\tAMR\tAMR\t99.5\t100\tBETA-LACTAM\tCEPHALOSPORIN\n",
        encoding="utf-8",
    )
    markers = parse_amrfinder_tsv(path)
    assert markers[0].symbol == "blaCTX-M-15"
    assert markers[0].identity == 0.995
    assert markers[0].coverage == 1.0
