import os
import logging
import asyncio
from dotenv import load_dotenv
from scrapers.reddit_scraper import RedditScraper
from scrapers.twitter_scraper import TwitterScraper
from scrapers.telegram_scraper import TelegramScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('main_scraper')

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
DB_NAME = "harcelement"
COLLECTION_NAME = "posts"

async def validate_credentials() -> bool:
    """Validate environment variables."""
    required = {
        "Reddit": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"],
        "Twitter": ["TWITTER_BEARER_TOKEN"],
        "Telegram": ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE"]
    }
    valid = True
    for platform, vars in required.items():
        if not all(os.getenv(var) for var in vars):
            logger.warning(f"{platform} credentials missing: {', '.join(vars)}")
            valid = False
    return valid

async def main():
    logger.info("Starting scraping process")
    if not await validate_credentials():
        logger.error("Missing credentials, aborting")
        return


      # Telegram scraping
    # try:
    #     telegram_scraper = TelegramScraper(
    #         os.getenv("TELEGRAM_API_ID"),
    #         os.getenv("TELEGRAM_API_HASH"),
    #         os.getenv("TELEGRAM_PHONE"),
    #         MONGO_URI
    #     )
    #     groups = ["StopBullying", "HarassmentHelp", "MeTooMovement", "DomesticAbuseSupport", "MentalHealthSupport", "OnlineSafety", "SexualHarassmentAwareness", "HumanRightsWatch", "CyberbullyingAwareness" ]
        
    #     telegram_results = await telegram_scraper.scrape_multiple_groups(groups, limit=50)
    #     total_telegram_posts = sum(len(messages) for messages in telegram_results.values())
    #     logger.info(f"Scraped {total_telegram_posts} messages from Telegram")
    #     await telegram_scraper.close()
    # except Exception as e:
    #     logger.error(f"Error during Telegram scraping: {e}")
    
    # # Twitter scraping
    # try:
    #     twitter_scraper = TwitterScraper(os.getenv("TWITTER_BEARER_TOKEN"), MONGO_URI)
    #     keywords = ["#harassment"]
    #     twitter_results = twitter_scraper.scrape_multiple_keywords(keywords, limit=50, language="en")
    #     total_twitter_posts = sum(len(tweets) for tweets in twitter_results.values())
    #     logger.info(f"Scraped {total_twitter_posts} tweets from Twitter")
    #     twitter_scraper.close()
    # except Exception as e:
    #     logger.error(f"Error during Twitter scraping: {e}")

  


    # # Reddit scraping
    # try:
    #     reddit_scraper = RedditScraper(
    #         os.getenv("REDDIT_CLIENT_ID"),
    #         os.getenv("REDDIT_CLIENT_SECRET"),
    #         os.getenv("REDDIT_USER_AGENT", "Mozilla/5.0"),
    #         MONGO_URI
    #     )
    #     subreddits = ["bullying", "TrueOffMyChest", "WorkplaceBullying", "cyberbullying"]
    #     reddit_results = await reddit_scraper.scrape_multiple_subreddits(subreddits, limit=50, sort_by="hot")
    #     total_reddit_posts = sum(len(posts) for posts in reddit_results.values())
    #     logger.info(f"Scraped {total_reddit_posts} posts from Reddit")
    #     reddit_scraper.close()
    # except Exception as e:
    #     logger.error(f"Error during Reddit scraping: {e}")


    logger.info("Scraping process completed")

if __name__ == "__main__":
    asyncio.run(main())