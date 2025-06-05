import asyncpraw
import datetime
import pymongo
import logging
import asyncio
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('reddit_scraper')

class RedditScraper:
    def __init__(self, client_id: str, client_secret: str, user_agent: str, mongo_uri: str, 
                 db_name: str = "harcelement", collection_name: str = "posts"):
        """
        Initialize the Reddit scraper with asyncpraw.
        """
        self.reddit = asyncpraw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.collection.create_index("url", unique=True)
        logger.info("Reddit scraper initialized")

    async def scrape_subreddit(self, subreddit_name: str, limit: int = 50, sort_by: str = "hot") -> List[Dict[Any, Any]]:
        """
        Scrape posts from a subreddit asynchronously.
        """
        logger.info(f"Scraping {limit} posts from r/{subreddit_name} sorted by {sort_by}")
        posts = []

        try:
            subreddit = await self.reddit.subreddit(subreddit_name)
            if sort_by == "hot":
                submissions = subreddit.hot(limit=limit)
            elif sort_by == "new":
                submissions = subreddit.new(limit=limit)
            elif sort_by == "top":
                submissions = subreddit.top(limit=limit)
            elif sort_by == "rising":
                submissions = subreddit.rising(limit=limit)
            else:
                logger.error(f"Invalid sort_by parameter: {sort_by}")
                return []

            async for submission in submissions:
                post = {
                    "title": submission.title,
                    "content": submission.selftext or "",
                    "author": str(submission.author) if submission.author else "unknown",
                    "date": datetime.datetime.fromtimestamp(submission.created_utc),
                    "url": f"https://www.reddit.com{submission.permalink}",
                    "subreddit": subreddit_name,
                    "score": submission.score,
                    "source": "reddit",
                    "post_id": submission.id,
                    "scraped_at": datetime.datetime.now()
                }

                try:
                    self.collection.insert_one(post)
                    posts.append(post)
                    logger.debug(f"Inserted post: {post['title'][:50]}...")
                except pymongo.errors.DuplicateKeyError:
                    logger.debug(f"Duplicate post: {post['url']}")
                except Exception as e:
                    logger.error(f"Error inserting post into MongoDB: {e}")
                
                await asyncio.sleep(0.5)  # Respect Reddit's 2 requests/second rate limit

            logger.info(f"Successfully scraped {len(posts)} posts from r/{subreddit_name}")
            return posts

        except Exception as e:
            logger.error(f"Error scraping subreddit {subreddit_name}: {e}")
            return []

    async def scrape_multiple_subreddits(self, subreddit_names: List[str], limit: int = 50, sort_by: str = "hot") -> Dict[str, List[Dict[Any, Any]]]:
        """
        Scrape posts from multiple subreddits.
        """
        results = {}
        for subreddit_name in subreddit_names:
            logger.info(f"Scraping subreddit: {subreddit_name}")
            posts = await self.scrape_subreddit(subreddit_name, limit, sort_by)
            results[subreddit_name] = posts
            await asyncio.sleep(1)  # Avoid overwhelming Reddit API
        return results

    def close(self):
        """Close the MongoDB connection."""
        self.client.close()
        logger.info("MongoDB connection closed")
        # Note: asyncpraw closes connections automatically

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "Mozilla/5.0")
    mongo_uri = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")

    async def main():
        scraper = RedditScraper(client_id, client_secret, user_agent, mongo_uri)
        subreddits = ["bullying", "TrueOffMyChest", "WorkplaceBullying", "cyberbullying"]  # Replaced 'harassment'
        results = await scraper.scrape_multiple_subreddits(subreddits, limit=50, sort_by="hot")
        for subreddit, posts in results.items():
            print(f"Scraped {len(posts)} posts from r/{subreddit}")
        scraper.close()

    asyncio.run(main())