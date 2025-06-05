import tweepy
import datetime
import pymongo
import logging
import time
import random
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('twitter_scraper')

class TwitterScraper:
    def __init__(self, bearer_token: str, mongo_uri: str, db_name: str = "harcelement", collection_name: str = "posts"):
        """Initialize the Twitter scraper with bearer token authentication."""
        self.client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
        self.mongo_client = pymongo.MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        self.collection = self.db[collection_name]
        self.collection.create_index("post_id", unique=True)
        logger.info("Twitter scraper initialized")

    def scrape_keyword(self, keyword: str, limit: int = 50, language: str = None) -> List[Dict[Any, Any]]:
        """
        Scrape tweets containing a specific keyword or hashtag using pagination to reach desired limit.
        """
        logger.info(f"Scraping up to {limit} tweets containing '{keyword}'")
        tweets = []
        
        try:
            # Build query
            query = keyword
            if language:
                query += f" lang:{language}"
            
            # Add filter to exclude retweets for more original content
            query += " -is:retweet"
                
            # Use a reasonable batch size that respects rate limits
            batch_size = 10  # Request 10 tweets per API call
            
            tweet_fields = ['created_at', 'public_metrics', 'entities']
            user_fields = ['username']
            expansions = ['author_id']

            # Use Paginator to make multiple requests until we reach the limit
            paginator = tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                max_results=batch_size,
                tweet_fields=tweet_fields,
                user_fields=user_fields,
                expansions=expansions,
                limit=10  # Maximum 10 pages (could return up to 100 tweets)
            )
            
            # Process paginated responses
            for i, response in enumerate(paginator):
                # Add delay between pagination requests (except first request)
                if i > 0:
                    wait_time = random.uniform(3, 5)
                    logger.info(f"Waiting {wait_time:.1f} seconds between pagination requests...")
                    time.sleep(wait_time)
                
                if not hasattr(response, 'data') or not response.data:
                    logger.warning(f"No more tweets found for query: {query}")
                    break

                users = {user.id: user for user in response.includes['users']} if 'users' in response.includes else {}
                
                for tweet in response.data:
                    # Stop if we've reached the limit
                    if len(tweets) >= limit:
                        break
                        
                    author = users.get(tweet.author_id, {}).username or "unknown"
                    hashtags = [tag['tag'] for tag in tweet.entities.get('hashtags', [])] if hasattr(tweet, 'entities') and tweet.entities and 'hashtags' in tweet.entities else []
                    
                    post = {
                        "title": "",
                        "content": tweet.text,
                        "author": author,
                        "date": tweet.created_at,
                        "url": f"https://twitter.com/{author}/status/{tweet.id}",
                        "source": "twitter",
                        "post_id": str(tweet.id),
                        "scraped_at": datetime.datetime.now(),
                        "hashtags": hashtags,
                        "retweet_count": tweet.public_metrics.get('retweet_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                        "like_count": tweet.public_metrics.get('like_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                        "keyword": keyword
                    }

                    try:
                        self.collection.insert_one(post)
                        tweets.append(post)
                        logger.debug(f"Added tweet {len(tweets)}/{limit} from @{author}")
                    except pymongo.errors.DuplicateKeyError:
                        logger.debug(f"Duplicate tweet: {post['url']}")
                    except Exception as e:
                        logger.error(f"Error inserting tweet: {e}")
                
                # Stop pagination if we've reached the limit
                if len(tweets) >= limit:
                    logger.info(f"Reached target of {limit} tweets, stopping pagination")
                    break
                    
                # Log progress
                logger.info(f"Retrieved {len(tweets)}/{limit} tweets so far...")

            logger.info(f"Successfully scraped {len(tweets)} tweets containing '{keyword}'")
            return tweets

        except tweepy.TooManyRequests:
            logger.warning(f"Rate limit exceeded. Collected {len(tweets)} tweets so far.")
            return tweets
        except Exception as e:
            logger.error(f"Error scraping tweets for '{keyword}': {e}")
            return tweets

    def scrape_multiple_keywords(self, keywords: List[str], limit: int = 50, language: str = None) -> Dict[str, List[Dict[Any, Any]]]:
        """
        Scrape tweets for multiple keywords one at a time.
        """
        results = {}
        
        for keyword in keywords:
            results[keyword] = []
            
            logger.info(f"Processing keyword: {keyword}")
            
            # Add delay between keywords
            if len(results) > 1:  # Skip delay for first keyword
                wait_time = random.uniform(10, 15)
                logger.info(f"Waiting {wait_time:.1f} seconds before next keyword...")
                time.sleep(wait_time)
            
            # Get tweets for this keyword
            tweets = self.scrape_keyword(keyword, limit, language)
            results[keyword] = tweets
                
        return results

    def close(self):
        """Close the MongoDB connection."""
        self.mongo_client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    mongo_uri = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")

    scraper = TwitterScraper(bearer_token, mongo_uri)
    keywords = ["#harassment"]
    results = scraper.scrape_multiple_keywords(keywords, limit=50, language="en")
    for keyword, tweets in results.items():
        print(f"Scraped {len(tweets)} tweets containing '{keyword}'")
    scraper.close()