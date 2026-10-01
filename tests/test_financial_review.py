from ssm.models import Dilution
from ssm.financial_review import financial_note_hits, conservative_merge_dilution, cover_page_common_shares

def test_financial_note_hits():
    text = """
    Note 7 Warrants and Pre-Funded Warrants.
    The Company evaluated substantial doubt about its ability to continue as a going concern.
    Subsequent Events include an at-the-market offering.
    """
    hits = set(financial_note_hits(text))
    assert {"WARRANTS","PRE_FUNDED","GOING_CONCERN","SUBSEQUENT_EVENTS","ATM_EQUITY_LINE"} <= hits

def test_conservative_merge_uses_max_not_sum():
    event = Dilution(
        common_shares=10_000_000,
        pre_funded_shares=4_000_000,
        warrants_itm_shares=2_000_000,
        source="8-K",
        confidence="medium",
    )
    fin = Dilution(
        common_shares=10_000_000,
        pre_funded_shares=4_000_000,
        warrants_itm_shares=3_000_000,
        converts_shares=1_000_000,
        source="10-Q",
        confidence="medium",
    )
    merged = conservative_merge_dilution(event, fin)
    assert merged.pre_funded_shares == 4_000_000
    assert merged.warrants_itm_shares == 3_000_000
    assert merged.converts_shares == 1_000_000
    assert merged.strict_fd_shares == 18_000_000


def test_cover_page_common_shares_generic():
    text="As of August 10, 2026, there were 12,345,678 shares of common stock outstanding."
    assert cover_page_common_shares(text)==12_345_678

def test_cover_page_common_shares_sums_classes():
    text="As of August 10, 2026, 10,000,000 shares of Class A common stock and 2,000,000 shares of Class B common stock were outstanding."
    assert cover_page_common_shares(text)==12_000_000
