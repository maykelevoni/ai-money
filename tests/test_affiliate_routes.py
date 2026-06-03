"""Smoke tests for affiliate page serving and click-through routes."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

import src.db as db
from src.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    conn = getattr(db._local, "conn", None)
    if conn:
        conn.close()
    db._local.conn = None
    with TestClient(app) as c:
        yield c
    conn = getattr(db._local, "conn", None)
    if conn:
        conn.close()
    db._local.conn = None


def _seed_page(tmp_path, slug: str, product_id: str) -> None:
    """Insert product + page rows and write a real page file."""
    db.execute(
        "INSERT OR IGNORE INTO affiliate_products (product_id, status) VALUES (?, 'candidate')",
        (product_id,),
    )
    page_file = tmp_path / f"{slug}.html"
    page_file.write_text(f"<html><body>Test page for {slug}</body></html>", encoding="utf-8")
    db.execute(
        "INSERT INTO affiliate_pages (product_id, slug, file_path, status) VALUES (?, ?, ?, 'live')",
        (product_id, slug, str(page_file)),
    )


def test_app_boots(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_unknown_page_slug_returns_404(client):
    resp = client.get("/p/no-such-slug")
    assert resp.status_code == 404


def test_page_returns_200_and_content(client, tmp_path):
    _seed_page(tmp_path, "test-product", "11111")
    resp = client.get("/p/test-product")
    assert resp.status_code == 200
    assert "Test page for test-product" in resp.text


def test_page_view_count_increments(client, tmp_path):
    _seed_page(tmp_path, "view-counter", "22222")
    client.get("/p/view-counter")
    client.get("/p/view-counter")
    row = db.fetchone("SELECT views FROM affiliate_pages WHERE slug = 'view-counter'")
    assert row["views"] == 2


def test_aff_redirect_returns_302_to_promolink(client, tmp_path):
    _seed_page(tmp_path, "click-product", "33333")
    with patch("src.clients.digistore24.resolve_affiliate_name", return_value="testaffiliate"):
        resp = client.get("/aff/click-product", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "digistore24.com/redir/33333/testaffiliate/click-product" in location


def test_aff_redirect_increments_click_count(client, tmp_path):
    _seed_page(tmp_path, "click-count", "44444")
    with patch("src.clients.digistore24.resolve_affiliate_name", return_value="testaffiliate"):
        client.get("/aff/click-count", follow_redirects=False)
        client.get("/aff/click-count", follow_redirects=False)
    row = db.fetchone("SELECT clicks FROM affiliate_pages WHERE slug = 'click-count'")
    assert row["clicks"] == 2


def test_aff_unknown_slug_returns_404(client):
    resp = client.get("/aff/nonexistent", follow_redirects=False)
    assert resp.status_code == 404
