"""Offline tests for the EDGAR client: CIK lookup + cache-only behavior.

Ported from the thesis project's test scaffolding (monkeypatched fake
``requests``, no real network) and retargeted to the SNPS/ANSS fixtures. These
never touch the network: they exercise the cache path and the offline-guard that
turns a missing fixture into a loud error.
"""

from __future__ import annotations

import json
import sys
import types

import pytest
from config import settings
from src.edgar import EdgarClient


def test_lookup_cik_from_cached_tickers():
    client = EdgarClient(offline=True)
    assert client.lookup_cik("SNPS") == "0000883241"
    # Case-insensitive.
    assert client.lookup_cik("snps") == "0000883241"
    # Zero-padded to 10 digits.
    assert len(client.lookup_cik("SNPS")) == 10


def test_lookup_cik_deal_target_falls_back_to_settings():
    # ANSS is not in the committed company_tickers.json (it dropped from the SEC
    # ticker feed around the merger). The client falls back to the frozen deal
    # CIK constant in settings — a sourced constant, not a guessed value.
    client = EdgarClient(offline=True)
    assert "ANSS" not in client._load_ticker_index()
    assert client.lookup_cik("ANSS") == settings.TARGET_CIK == "0001013462"


def test_company_name_lookup():
    client = EdgarClient(offline=True)
    assert "SYNOPSYS" in client.company_name("SNPS").upper()


def test_unknown_ticker_raises():
    client = EdgarClient(offline=True)
    with pytest.raises(KeyError):
        client.lookup_cik("NOTATICKER")


def test_offline_loads_cached_companyfacts():
    client = EdgarClient(offline=True)
    facts = client.get_company_facts("SNPS")
    assert facts["cik"] == 883241
    assert "us-gaap" in facts["facts"]


def test_offline_loads_cached_submissions():
    client = EdgarClient(offline=True)
    subs = client.get_submissions("ANSS")
    assert isinstance(subs, dict)
    assert subs  # non-empty
    assert "filings" in subs


def test_offline_missing_concept_raises_not_network():
    # A ticker whose companyfacts IS cached, but a concept file that is NOT:
    # offline mode must raise FileNotFoundError, never attempt a live call.
    client = EdgarClient(offline=True)
    with pytest.raises(FileNotFoundError):
        client.get_company_concept("SNPS", "us-gaap", "Revenues")


def test_offline_missing_ticker_file_raises(tmp_path):
    # Point the client at an empty cache dir: even a known ticker's file is
    # absent, so the lookup itself fails (no company_tickers.json to read).
    client = EdgarClient(offline=True, cache_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        client.get_company_facts("SNPS")


def test_rate_limit_spacing_is_configured():
    # Guard the fair-access contract constants the client relies on.
    assert settings.SEC_REQ_SPACING_SEC >= 0.1
    assert "proforma-research" in settings.SEC_USER_AGENT


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _install_fake_requests(monkeypatch, payload, calls):
    """Install a fake ``requests`` module so the live path never hits the net."""
    fake = types.ModuleType("requests")

    def _get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return _FakeResponse(payload)

    fake.get = _get
    monkeypatch.setitem(sys.modules, "requests", fake)


def test_live_fetch_writes_cache_and_sends_user_agent(monkeypatch, tmp_path):
    # Online mode, empty cache: the client fetches (mocked), sends the required
    # User-Agent, and writes the response into the cache for reuse.
    tickers = {"0": {"cik_str": 883241, "ticker": "SNPS", "title": "SYNOPSYS INC"}}
    (tmp_path / "company_tickers.json").write_text(json.dumps(tickers), encoding="utf-8")

    calls: list[dict] = []
    payload = {"cik": 883241, "facts": {}}
    _install_fake_requests(monkeypatch, payload, calls)

    client = EdgarClient(offline=False, cache_dir=tmp_path)
    got = client.get_company_facts("SNPS")
    assert got == payload
    # User-Agent contract enforced on the live call.
    assert calls and calls[0]["headers"]["User-Agent"] == settings.SEC_USER_AGENT
    # Response cached to disk.
    cached = tmp_path / "companyfacts_SNPS_0000883241.json"
    assert cached.exists()

    # Second call is served from cache — no additional live request.
    again = client.get_company_facts("SNPS")
    assert again == payload
    assert len(calls) == 1


def test_respect_rate_limit_sleeps_between_requests(monkeypatch):
    # The spacing guard must sleep when two live requests happen back-to-back.
    client = EdgarClient(offline=False)
    slept: list[float] = []
    monkeypatch.setattr("src.edgar.client.time.sleep", lambda s: slept.append(s))
    monkeypatch.setattr("src.edgar.client.time.monotonic", lambda: 100.0)
    client._respect_rate_limit()
    # Second call immediately after: elapsed ~0, so it must sleep ~spacing.
    client._respect_rate_limit()
    assert slept, "expected a sleep on the back-to-back request"
    assert slept[-1] <= settings.SEC_REQ_SPACING_SEC


def test_fetch_live_refuses_in_offline_mode():
    client = EdgarClient(offline=True)
    with pytest.raises(RuntimeError):
        client._fetch_live("https://data.sec.gov/whatever.json")
