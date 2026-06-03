"""Unit tests for Digistore24 client parsing/link building and product intake."""
import pytest

import src.db as db
from src.clients.digistore24 import parse_product_id, build_promolink
from src import affiliate_research


# ── parse_product_id ──────────────────────────────────────────────────────────

def test_parse_bare_numeric_id():
    assert parse_product_id("12345") == "12345"


def test_parse_numeric_id_strips_whitespace():
    assert parse_product_id("  67890  ") == "67890"


def test_parse_redir_link_extracts_id():
    url = "https://www.digistore24.com/redir/98765/myaffiliate/campaign1"
    assert parse_product_id(url) == "98765"


def test_parse_redir_link_no_campaign_key():
    url = "https://www.digistore24.com/redir/54321/myaffiliate"
    assert parse_product_id(url) == "54321"


def test_parse_marketplace_url_five_digit_segment():
    url = "https://www.digistore24.com/product/54321/some-product-name"
    assert parse_product_id(url) == "54321"


def test_parse_blank_returns_none():
    assert parse_product_id("") is None


def test_parse_whitespace_only_returns_none():
    assert parse_product_id("   ") is None


def test_parse_alphabetic_garbage_returns_none():
    assert parse_product_id("not-a-product") is None


def test_parse_mixed_garbage_returns_none():
    assert parse_product_id("abc-xyz") is None


def test_parse_short_path_segment_ignored():
    # 3-digit segment is too short for the marketplace URL heuristic
    url = "https://www.digistore24.com/p/123/item"
    assert parse_product_id(url) is None


# ── build_promolink ───────────────────────────────────────────────────────────

def test_build_promolink_with_campaign_key():
    url = build_promolink("12345", "myaffiliate", "my-campaign")
    assert url == "https://www.digistore24.com/redir/12345/myaffiliate/my-campaign"


def test_build_promolink_without_campaign_key():
    url = build_promolink("12345", "myaffiliate")
    assert url == "https://www.digistore24.com/redir/12345/myaffiliate"


def test_build_promolink_empty_string_campaign_key_omitted():
    url = build_promolink("12345", "myaffiliate", "")
    assert url == "https://www.digistore24.com/redir/12345/myaffiliate"


def test_build_promolink_slug_as_campaign_key():
    url = build_promolink("99999", "paidrew", "my-product-slug")
    assert url == "https://www.digistore24.com/redir/99999/paidrew/my-product-slug"


# ── affiliate_research.add_products ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    conn = getattr(db._local, "conn", None)
    if conn:
        conn.close()
    db._local.conn = None
    db.init_db()
    yield
    conn = getattr(db._local, "conn", None)
    if conn:
        conn.close()
    db._local.conn = None


def test_add_products_counts_new_ids():
    result = affiliate_research.add_products("12345\n67890\n")
    assert result["added"] == 2
    assert result["skipped_existing"] == 0
    assert result["invalid"] == 0


def test_add_products_invalid_lines_counted():
    result = affiliate_research.add_products("12345\nnot-a-product\n  \n")
    assert result["added"] == 1
    assert result["invalid"] == 1


def test_add_products_blank_lines_not_counted_as_invalid():
    result = affiliate_research.add_products("  \n\n  \n")
    assert result["added"] == 0
    assert result["invalid"] == 0


def test_add_products_dedupe_skips_existing():
    affiliate_research.add_products("12345\n")
    result = affiliate_research.add_products("12345\n67890\n")
    assert result["added"] == 1
    assert result["skipped_existing"] == 1


def test_add_products_status_preserved_on_resubmit():
    affiliate_research.add_products("12345\n")
    db.execute("UPDATE affiliate_products SET status = 'testing' WHERE product_id = '12345'")
    # Re-submit same ID — existing row must be skipped, status untouched
    affiliate_research.add_products("12345\n")
    row = db.fetchone("SELECT status FROM affiliate_products WHERE product_id = '12345'")
    assert row["status"] == "testing"


def test_add_products_new_row_has_candidate_status():
    affiliate_research.add_products("12345\n")
    row = db.fetchone("SELECT status FROM affiliate_products WHERE product_id = '12345'")
    assert row["status"] == "candidate"


def test_add_products_accepts_redir_url():
    url = "https://www.digistore24.com/redir/99999/affiliate/campaign"
    result = affiliate_research.add_products(url)
    assert result["added"] == 1
    row = db.fetchone("SELECT product_id FROM affiliate_products WHERE product_id = '99999'")
    assert row is not None
