"""One-shot rate-limited EDGAR fixture puller.

For a registered deal's two principals, fetches:
  * CompanyFacts (all XBRL facts) and submissions (filing index), and
  * the raw text of the deal documents — the merger proxy/prospectus (DEFM14A /
    S-4 + amendments), announcement/merger 8-Ks, and 425 communications —
    discovered by scanning the submissions index for the relevant forms filed
    on/after the announcement.

Deals are registered in ``DEALS``: the default ``snps_anss`` (Synopsys/ANSYS,
deal #1) and ``csco_splk`` (Cisco/Splunk, the P6 generality proof). All into
data/fixtures/. Respects SEC fair-access (User-Agent, 150ms spacing, https
only). Idempotent: skips files already cached. Writes a per-deal manifest so
the two pulls coexist.

Run:  PROFORMA_OFFLINE=0 .venv/bin/python scripts/pull_edgar_fixtures.py [--deal csco_splk]
"""

from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path

UA = "proforma-research billdmar@gmail.com"
SPACING = 0.15  # 150ms between requests (well under SEC's 10 req/s)
RAW = Path("data/fixtures/raw")
DOCS = Path("data/fixtures/documents")

# Deal registry — each entry is a self-contained set of principals + the
# announcement date used to scope the document scan. Deal #1 (Synopsys/ANSYS)
# is the default so a bare invocation reproduces it exactly; deal #2
# (Cisco/Splunk, the P6 generality proof) is pulled with `--deal csco_splk`.
# CIKs verified against EDGAR before pull.
DEALS = {
    "snps_anss": {
        "companies": {
            "SNPS": "0000883241",  # acquirer — Synopsys, Inc.
            "ANSS": "0001013462",  # target — ANSYS, Inc.
        },
        "announce_date": "2024-01-16",
    },
    "csco_splk": {
        "companies": {
            "CSCO": "0000858877",  # acquirer — Cisco Systems, Inc.
            "SPLK": "0001353283",  # target — Splunk Inc.
        },
        "announce_date": "2023-09-21",  # Cisco/Splunk announced 2023-09-21
    },
}

# Deal documents live in these forms; scan submissions from the announcement
# onward. DEFM14A/S-4 carry the fairness-opinion disclosures; 8-K/425 carry the
# announcement + merger-agreement exhibits.
DEAL_FORMS = {"DEFM14A", "DEF 14A", "DEFA14A", "S-4", "S-4/A", "425", "8-K", "8-K/A", "PREM14A"}
# Cap 8-K/425 volume: those two forms are noisy; keep only ones near the deal.
NOISY_FORMS = {"8-K", "8-K/A", "425", "DEFA14A"}
DOC_LIMIT_PER_FORM = 8


def _get(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (SEC https only)
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
    time.sleep(SPACING)
    return data


def fetch_to(url: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 0:
        return f"cached  {dest.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = _get(url)
    except Exception as e:  # noqa: BLE001 — bootstrap script: log and continue
        return f"ERROR   {dest.name}: {e}"
    dest.write_bytes(data)
    return f"pulled  {dest.name} ({len(data):,} bytes)"


def discover_deal_documents(
    ticker: str, cik: str, announce_date: str, log: list[str]
) -> list[dict]:
    """Scan a company's submissions index for deal-relevant filings and return
    document descriptors (form, date, accession, primary doc URL)."""
    subs_path = RAW / f"submissions_{ticker}_{cik}.json"
    if not subs_path.exists():
        return []
    m = json.loads(subs_path.read_text())
    recent = m.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])
    primary = recent.get("primaryDocument", [])
    docs: list[dict] = []
    per_form_count: dict[str, int] = {}
    cik_int = int(cik)
    for form, fdate, accn, doc in zip(forms, dates, accns, primary, strict=False):
        if form not in DEAL_FORMS or fdate < announce_date or not doc:
            continue
        if form in NOISY_FORMS:
            per_form_count[form] = per_form_count.get(form, 0) + 1
            if per_form_count[form] > DOC_LIMIT_PER_FORM:
                continue
        accn_nodash = accn.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_nodash}/{doc}"
        docs.append(
            {
                "ticker": ticker,
                "form": form,
                "filed": fdate,
                "accession": accn,
                "url": url,
                "doc": doc,
            }
        )
    log.append(f"  {ticker}: {len(docs)} deal documents discovered")
    return docs


def main(deal_key: str = "snps_anss") -> int:
    deal = DEALS[deal_key]
    companies = deal["companies"]
    announce_date = deal["announce_date"]
    RAW.mkdir(parents=True, exist_ok=True)
    log: list[str] = []

    # 1) company_tickers.json (CIK lookup table, reused by the client).
    log.append(
        fetch_to("https://www.sec.gov/files/company_tickers.json", RAW / "company_tickers.json")
    )

    # 2) CompanyFacts + submissions for both principals.
    for ticker, cik in companies.items():
        log.append(
            fetch_to(
                f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                RAW / f"companyfacts_{ticker}_{cik}.json",
            )
        )
        log.append(
            fetch_to(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                RAW / f"submissions_{ticker}_{cik}.json",
            )
        )

    # 3) Discover + pull the deal documents (needs submissions cached first).
    all_docs: list[dict] = []
    for ticker, cik in companies.items():
        all_docs.extend(discover_deal_documents(ticker, cik, announce_date, log))
    for d in all_docs:
        fname = f"{d['ticker']}_{d['form'].replace(' ', '').replace('/', '')}_{d['accession']}_{d['doc']}"
        # keep filenames sane
        fname = fname[:180]
        log.append(fetch_to(d["url"], DOCS / fname))

    # 4) Per-deal manifest with provenance (one file per deal so pulls coexist).
    errors = [ln for ln in log if ln.startswith("ERROR")]
    manifest = {
        "companies": companies,
        "user_agent": UA,
        "announce_date": announce_date,
        "documents": [
            {k: d[k] for k in ("ticker", "form", "filed", "accession", "url")} for d in all_docs
        ],
    }
    (RAW / f"manifest_{deal_key}.json").write_text(json.dumps(manifest, indent=2))

    print("\n".join(log))
    print(
        f"\nDONE ({deal_key}): {len(log)} operations, {len(errors)} errors, {len(all_docs)} deal docs"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Pull SEC EDGAR fixtures for a registered deal.")
    ap.add_argument("--deal", choices=sorted(DEALS), default="snps_anss")
    args = ap.parse_args()
    sys.exit(main(args.deal))
