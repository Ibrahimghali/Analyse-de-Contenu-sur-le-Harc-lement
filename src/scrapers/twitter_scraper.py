import tweepy
import datetime
import pymongo
import logging
import time
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('twitter_scraper')

class TwitterScraper:
    def __init__(self, bearer_token: str, mongo_uri: str, db_name: str = "harcelement", collection_name: str = "posts"):
        """Initialize the Twitter scraper with bearer token authentication."""
        # Set wait_on_rate_limit to True to automatically handle rate limits
        self.client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
        self.mongo_client = pymongo.MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        self.collection = self.db[collection_name]
        self.collection.create_index("post_id", unique=True)
        logger.info("Twitter scraper initialized")

    def scrape_keyword(self, keyword: str, limit: int = 50, language: str = None) -> List[Dict[Any, Any]]:
        """Scrape tweets containing a specific keyword or hashtag."""
        logger.info(f"Scraping up to {limit} tweets containing '{keyword}'")
        tweets = []
        
        try:
            # Build query
            query = keyword
            if language:
                query += f" lang:{language}"
            query += " -is:retweet"  # Exclude retweets
            
            # Configure fields to retrieve
            tweet_fields = ['created_at', 'public_metrics', 'entities']
            user_fields = ['username']
            expansions = ['author_id']

            # Use Paginator with a larger batch size to minimize API calls
            paginator = tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                max_results=100,  # Maximum allowed per request
                tweet_fields=tweet_fields,
                user_fields=user_fields,
                expansions=expansions,
                limit=1  # Just one page should be enough for 50 tweets
            )
            
            # Process tweets
            for response in paginator:
                if not hasattr(response, 'data') or not response.data:
                    logger.warning(f"No tweets found for query: {query}")
                    break
                
                users = {user.id: user for user in response.includes['users']} if 'users' in response.includes else {}
                
                for tweet in response.data:
                    # Stop if we've reached the limit
                    if len(tweets) >= limit:
                        break
                    
                    # Get author info
                    author = users.get(tweet.author_id, {}).username or "unknown"
                    
                    # Extract hashtags
                    hashtags = []
                    if hasattr(tweet, 'entities') and tweet.entities and 'hashtags' in tweet.entities:
                        hashtags = [tag['tag'] for tag in tweet.entities['hashtags']]
                    
                    # Create post document
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
                        "keyword": keyword
                    }
                    
                    # Add metrics if available
                    if hasattr(tweet, 'public_metrics'):
                        post["retweet_count"] = tweet.public_metrics.get('retweet_count', 0)
                        post["like_count"] = tweet.public_metrics.get('like_count', 0)

                    # Save to MongoDB
                    try:
                        self.collection.insert_one(post)
                        tweets.append(post)
                    except pymongo.errors.DuplicateKeyError:
                        logger.debug(f"Duplicate tweet: {post['url']}")
                    except Exception as e:
                        logger.error(f"Error inserting tweet: {e}")
            
            # Log final results
            logger.info(f"Successfully scraped {len(tweets)} tweets containing '{keyword}'")
            return tweets

        except Exception as e:
            logger.error(f"Error scraping tweets for '{keyword}': {e}")
            return tweets

    def scrape_multiple_keywords(self, keywords: List[str], limit: int = 50, language: str = None) -> Dict[str, List[Dict[Any, Any]]]:
        """Scrape tweets for multiple keywords."""
        results = {}
        
        for keyword in keywords:
            logger.info(f"Processing keyword: {keyword}")
            tweets = self.scrape_keyword(keyword, limit, language)
            results[keyword] = tweets
            
            # Add a short delay between keywords if more than one
            if len(keywords) > 1 and keywords.index(keyword) < len(keywords) - 1:
                time.sleep(2)  # 2 second delay between keywords
                
        return results

    def close(self):
        """Close the MongoDB connection."""
        self.mongo_client.close()
        logger.info("MongoDB connection closed")

