"""SEC EDGAR RSS feed service. Filings and insider trades."""
import feedparser


class SECEdgarService:
    RSS_BASE = "https://www.sec.gov/cgi-bin/browse-edgar"
    FULL_TEXT_SEARCH = "https://efts.sec.gov/LATEST/search-index"

    def get_filings(self, ticker: str, filing_type: str = "8-K") -> list:
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type={filing_type}&dateb=&owner=include&count=20&search_text=&action=getcompany&output=atom"
        feed = feedparser.parse(url)
        return [
            {
                "title": entry.title,
                "filed": entry.get("filed", ""),
                "link": entry.link,
                "summary": entry.get("summary", ""),
            }
            for entry in feed.entries
        ]
