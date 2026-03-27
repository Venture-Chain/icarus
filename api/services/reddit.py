"""Reddit data service via PRAW. Retail sentiment from investing subreddits."""
import logging
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import praw

from config import settings

logger = logging.getLogger(__name__)

# Common words that look like tickers but are not
FALSE_TICKERS = {
    "I", "A", "IT", "IS", "AM", "PM", "CEO", "CFO", "IPO", "ETF", "DD",
    "EPS", "PE", "ATH", "ATL", "IMO", "YOLO", "FOMO", "FD", "OTM", "ITM",
    "GDP", "CPI", "SEC", "FBI", "USA", "UK", "EU", "USD", "THE", "FOR",
    "ARE", "AND", "NOT", "BUT", "ALL", "ANY", "CAN", "HAS", "HER", "HIS",
    "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "OUR", "OWN", "SAY", "SHE",
    "TOO", "USE", "WAY", "WHO", "BOY", "DID", "GET", "HIM", "LET", "PUT",
    "RUN", "TOP", "BIG", "END", "FAR", "LOW", "MAN", "TRY", "ASK", "MEN",
}

TICKER_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")


class RedditService:
    SUBREDDITS = ["wallstreetbets", "stocks", "investing", "options"]

    def __init__(self) -> None:
        self.reddit: praw.Reddit | None = None

    def _connect(self) -> None:
        if not self.reddit:
            self.reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )

    def get_mentions(self, ticker: str, subreddit: str = "wallstreetbets", limit: int = 50) -> list[dict]:
        """Search for posts mentioning a ticker."""
        self._connect()
        sub = self.reddit.subreddit(subreddit)
        posts = []
        try:
            for post in sub.search(ticker, limit=limit, sort="new"):
                posts.append({
                    "title": post.title,
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "created_utc": post.created_utc,
                    "selftext": post.selftext[:500] if post.selftext else "",
                    "url": post.url,
                })
        except Exception as e:
            logger.error("Reddit mentions search failed for %s: %s", ticker, str(e))
        return posts

    def get_trending_tickers(self, subreddit: str = "wallstreetbets", limit: int = 100) -> list[dict]:
        """Extract $TICKER mentions from hot posts. Returns ranked list of tickers."""
        self._connect()
        sub = self.reddit.subreddit(subreddit)
        ticker_counts: Counter = Counter()

        try:
            for post in sub.hot(limit=limit):
                text = f"{post.title} {post.selftext or ''}"
                matches = TICKER_PATTERN.findall(text)
                for match in matches:
                    if match not in FALSE_TICKERS and len(match) >= 1:
                        ticker_counts[match] += 1
        except Exception as e:
            logger.error("Reddit trending tickers failed: %s", str(e))
            return []

        return [
            {"ticker": ticker, "mentions": count}
            for ticker, count in ticker_counts.most_common(25)
        ]

    def get_daily_sentiment(self, ticker: str, subreddit: str = "wallstreetbets", limit: int = 50) -> dict:
        """Aggregate recent post sentiment for a ticker based on score and engagement."""
        self._connect()
        sub = self.reddit.subreddit(subreddit)

        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        posts_analyzed = 0
        total_score = 0
        total_comments = 0
        positive_posts = 0
        negative_posts = 0

        try:
            for post in sub.search(f"${ticker}", limit=limit, sort="new"):
                post_time = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                if post_time < cutoff:
                    continue

                posts_analyzed += 1
                total_score += post.score
                total_comments += post.num_comments

                # Simple heuristic: upvote ratio > 0.6 is positive sentiment
                if hasattr(post, "upvote_ratio") and post.upvote_ratio > 0.6:
                    positive_posts += 1
                elif hasattr(post, "upvote_ratio") and post.upvote_ratio < 0.4:
                    negative_posts += 1
        except Exception as e:
            logger.error("Reddit daily sentiment failed for %s: %s", ticker, str(e))

        total_scored = positive_posts + negative_posts
        return {
            "ticker": ticker,
            "subreddit": subreddit,
            "posts_analyzed": posts_analyzed,
            "total_score": total_score,
            "total_comments": total_comments,
            "positive": positive_posts,
            "negative": negative_posts,
            "sentiment_ratio": positive_posts / total_scored if total_scored > 0 else 0.5,
        }
