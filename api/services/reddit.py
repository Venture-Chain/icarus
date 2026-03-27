"""Reddit data service via PRAW. Retail sentiment from investing subreddits."""
import praw

from config import settings


class RedditService:
    SUBREDDITS = ["wallstreetbets", "stocks", "investing", "options"]

    def __init__(self):
        self.reddit = None

    def _connect(self):
        if not self.reddit:
            self.reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )

    def get_mentions(self, ticker: str, subreddit: str = "wallstreetbets", limit: int = 50) -> list:
        self._connect()
        sub = self.reddit.subreddit(subreddit)
        posts = []
        for post in sub.search(ticker, limit=limit, sort="new"):
            posts.append({
                "title": post.title,
                "score": post.score,
                "num_comments": post.num_comments,
                "created_utc": post.created_utc,
                "selftext": post.selftext[:500] if post.selftext else "",
                "url": post.url,
            })
        return posts
