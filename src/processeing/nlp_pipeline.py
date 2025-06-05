import pymongo
import logging
from datetime import datetime
from typing import Dict, Any, List
from textblob import TextBlob
from langdetect import detect, LangDetectException
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('nlp_pipeline')

class NLPProcessor:
    def __init__(self, mongo_uri: str, db_name: str = "harcelement", 
                 preprocessed_collection: str = "preprocessed_posts",
                 enriched_collection: str = "enriched_posts"):
        """Initialize the NLP processor with MongoDB connection."""
        self.mongo_client = pymongo.MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        self.preprocessed_collection = self.db[preprocessed_collection]
        self.enriched_collection = self.db[enriched_collection]
        
        # Create index for enriched collection
        self.enriched_collection.create_index("url", unique=True)
        
        logger.info("NLP processor initialized")
    
    def detect_language(self, text: str) -> str:
        """Detect language of text."""
        if not text or len(text) < 3:
            return "unknown"
            
        try:
            # Use the first 1000 characters for language detection
            return detect(text[:1000])
        except LangDetectException:
            return "unknown"
    
    def analyze_sentiment(self, text: str, language: str) -> Dict[str, Any]:
        """Analyze sentiment of text."""
        if not text:
            return {"polarity": 0, "sentiment": "neutral"}
            
        # TextBlob supports English natively and has some support for other languages
        blob = TextBlob(text)
        
        # Get polarity score (-1 to 1, where -1 is negative, 0 is neutral, 1 is positive)
        polarity = blob.sentiment.polarity
        
        # Determine sentiment category
        if polarity > 0.1:
            sentiment = "positive"
        elif polarity < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"
            
        return {
            "polarity": polarity,
            "sentiment": sentiment
        }
    
    def process_documents(self) -> int:
        """Process documents from preprocessed collection and add language and sentiment."""
        total_count = self.preprocessed_collection.count_documents({})
        logger.info(f"Processing {total_count} documents")
        
        processed_count = 0
        for doc in self.preprocessed_collection.find():
            # Get content for analysis
            content = doc.get('content', '')
            
            # Detect language
            language = self.detect_language(content)
            
            # Analyze sentiment
            sentiment_result = self.analyze_sentiment(content, language)
            
            # Create enriched document with language and sentiment
            enriched_doc = {
                "title": doc.get('title', ''),
                "content": content,
                "author": doc.get('author', 'unknown'),
                "date": doc.get('date'),
                "url": doc.get('url', ''),
                "language": language,
                "sentiment": sentiment_result["sentiment"],
                "polarity": sentiment_result["polarity"],
                "enriched_at": datetime.now()
            }
            
            # Save to enriched collection
            try:
                self.enriched_collection.update_one(
                    {"url": doc["url"]},
                    {"$set": enriched_doc},
                    upsert=True
                )
                processed_count += 1
                
                # Log progress
                if processed_count % 100 == 0 or processed_count == total_count:
                    logger.info(f"Processed {processed_count}/{total_count} documents")
                    
            except Exception as e:
                logger.error(f"Error saving document: {e}")
        
        logger.info(f"NLP processing completed. Processed {processed_count} documents")
        return processed_count
    
    def export_to_csv(self, filename: str = "enriched_data.csv"):
        """Export enriched documents to CSV."""
        docs = list(self.enriched_collection.find({}, {'_id': 0}))
        if not docs:
            logger.warning("No documents to export")
            return
            
        df = pd.DataFrame(docs)
        df.to_csv(filename, index=False, encoding='utf-8')
        logger.info(f"Exported {len(docs)} documents to {filename}")
    
    def close(self):
        """Close MongoDB connection."""
        self.mongo_client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
    
    processor = NLPProcessor(mongo_uri)
    try:
        # Process documents and add language/sentiment
        processor.process_documents()
        
        # Optionally export to CSV
        processor.export_to_csv()
    finally:
        processor.close()