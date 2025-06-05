from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
import datetime
import pymongo
import logging
import asyncio
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('telegram_scraper')

class TelegramScraper:
    def __init__(self, api_id: str, api_hash: str, phone: str, mongo_uri: str, 
                 db_name: str = "harcelement", collection_name: str = "posts"):
        """
        Initialize the Telegram scraper.
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.client = None
        self.mongo_client = pymongo.MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        self.collection = self.db[collection_name]
        self.collection.create_index([("source", 1), ("post_id", 1)], unique=True)
        logger.info("Telegram scraper initialized")

    async def connect(self):
        """Connect to Telegram."""
        try:
            self.client = TelegramClient('session_name', self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            logger.info("Connected to Telegram")
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            raise

    async def scrape_group(self, group_username: str, limit: int = 50) -> List[Dict[Any, Any]]:
        """
        Scrape messages from a Telegram group.
        """
        if not self.client:
            await self.connect()

        logger.info(f"Scraping up to {limit} messages from {group_username}")
        messages = []

        try:
            entity = await self.client.get_entity(group_username)
            history = await self.client(GetHistoryRequest(
                peer=entity,
                limit=limit,
                offset_date=None,
                offset_id=0,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0
            ))

            for message in history.messages:
                if not message.message:
                    continue

                post = {
                    "title": "",
                    "content": message.message,
                    "author": f"user_{message.from_id.user_id}" if hasattr(message.from_id, 'user_id') else "unknown",
                    "date": message.date,
                    "url": f"https://t.me/{group_username}/{message.id}",
                    "source": "telegram",
                    "post_id": str(message.id),
                    "group": group_username,
                    "scraped_at": datetime.datetime.now()
                }

                try:
                    self.collection.insert_one(post)
                    messages.append(post)
                    logger.debug(f"Inserted message: {post['content'][:50]}...")
                except pymongo.errors.DuplicateKeyError:
                    logger.debug(f"Duplicate message: {post['url']}")
                except Exception as e:
                    logger.error(f"Error inserting message into MongoDB: {e}")
                
                await asyncio.sleep(0.1)  # Avoid server-side throttling

            logger.info(f"Successfully scraped {len(messages)} messages from {group_username}")
            return messages

        except Exception as e:
            logger.error(f"Error scraping group {group_username}: {e}")
            return []

    async def scrape_multiple_groups(self, group_usernames: List[str], limit: int = 50) -> Dict[str, List[Dict[Any, Any]]]:
        """
        Scrape messages from multiple Telegram groups.
        """
        if not self.client:
            await self.connect()

        results = {}
        for group_username in group_usernames:
            logger.info(f"Scraping group: {group_username}")
            messages = await self.scrape_group(group_username, limit)
            results[group_username] = messages
            await asyncio.sleep(1)  # Avoid overwhelming Telegram servers
        return results

    async def close(self):
        """Disconnect from Telegram and close MongoDB connection."""
        if self.client:
            await self.client.disconnect()
        self.mongo_client.close()
        logger.info("Telegram and MongoDB connections closed")
