from ssm.dilution import heuristic_extract_dilution

def test_prefunded_quantity_is_parsed():
    d, _ = heuristic_extract_dilution(
        "Pre-funded warrants exercisable for 4,000,000 shares of common stock.",
        10_000_000,
    )
    assert d.pre_funded_shares == 4_000_000

def test_malformed_quantity_does_not_raise():
    d, warnings = heuristic_extract_dilution(
        "Warrants to purchase , shares of common stock.",
        10_000_000,
    )
    assert d.warrants_itm_shares == 0
    assert warnings
