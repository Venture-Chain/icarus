"""SEC EDGAR service. Filings and insider trades via EFTS full-text search API."""
import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# SEC requires a descriptive User-Agent with contact info
USER_AGENT = "Icarus/1.0 (venture-chain; contact@venturechain.co)"


class SECEdgarService:
    EFTS_BASE = "https://efts.sec.gov/LATEST"
    EDGAR_DATA = "https://data.sec.gov"

    def __init__(self) -> None:
        self._headers: dict[str, str] = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

    async def get_filings(self, ticker: str, filing_type: str = "8-K", count: int = 20) -> list[dict]:
        """Search filings via EFTS full-text search."""
        try:
            async with httpx.AsyncClient(timeout=15, headers=self._headers) as client:
                params = {
                    "q": f"\"{ticker}\"",
                    "dateRange": "custom",
                    "forms": filing_type,
                    "from": 0,
                    "size": count,
                }
                resp = await client.get(f"{self.EFTS_BASE}/search-index", params=params)
                resp.raise_for_status()
                data = resp.json()

                filings = []
                for hit in data.get("hits", {}).get("hits", []):
                    source = hit.get("_source", {})
                    filings.append({
                        "title": source.get("display_names", [ticker])[0] if source.get("display_names") else ticker,
                        "form_type": source.get("form_type", filing_type),
                        "filed": source.get("file_date", ""),
                        "link": f"https://www.sec.gov/Archives/edgar/data/{source.get('entity_id', '')}/{source.get('file_num', '')}",
                        "entity": source.get("entity_name", ""),
                    })
                return filings
        except httpx.HTTPStatusError as e:
            logger.error("SEC EDGAR HTTP %d: %s", e.response.status_code, e.response.text[:200])
            return []
        except Exception as e:
            logger.error("SEC EDGAR filings failed for %s: %s", ticker, str(e))
            return []

    async def get_insider_trades(self, ticker: str, count: int = 30) -> list[dict]:
        """Get insider trading filings (Form 4) for a ticker."""
        try:
            cik = await self._resolve_cik(ticker)
            if not cik:
                logger.warning("Could not resolve CIK for %s", ticker)
                return []

            async with httpx.AsyncClient(timeout=15, headers=self._headers) as client:
                url = f"{self.EDGAR_DATA}/submissions/CIK{cik}.json"
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                recent = data.get("filings", {}).get("recent", {})
                forms = recent.get("form", [])
                dates = recent.get("filingDate", [])
                accessions = recent.get("accessionNumber", [])
                primary_docs = recent.get("primaryDocument", [])

                trades = []
                for i, form in enumerate(forms):
                    if form != "4":
                        continue
                    if len(trades) >= count:
                        break

                    accession_clean = accessions[i].replace("-", "")
                    trades.append({
                        "form": form,
                        "filed": dates[i] if i < len(dates) else "",
                        "accession": accessions[i] if i < len(accessions) else "",
                        "link": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{primary_docs[i]}" if i < len(primary_docs) else "",
                    })

                return trades
        except Exception as e:
            logger.error("SEC EDGAR insider trades failed for %s: %s", ticker, str(e))
            return []

    async def _resolve_cik(self, ticker: str) -> str | None:
        """Resolve ticker to zero-padded CIK using SEC company tickers JSON."""
        try:
            async with httpx.AsyncClient(timeout=10, headers=self._headers) as client:
                resp = await client.get(f"{self.EDGAR_DATA}/submissions/CIK{ticker.upper()}.json")
                if resp.status_code == 200:
                    data = resp.json()
                    cik = str(data.get("cik", ""))
                    return cik.zfill(10) if cik else None

                # Fallback: search the company tickers file
                resp = await client.get("https://www.sec.gov/files/company_tickers.json")
                resp.raise_for_status()
                tickers_data = resp.json()
                for entry in tickers_data.values():
                    if entry.get("ticker", "").upper() == ticker.upper():
                        return str(entry["cik_str"]).zfill(10)
                return None
        except Exception as e:
            logger.error("CIK resolution failed for %s: %s", ticker, str(e))
            return None
