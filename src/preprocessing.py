import pymongo
import re
import nltk
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Any
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('preprocessing')

# Download required NLTK resources - make sure they are properly downloaded
try:
    logger.info("Downloading required NLTK resources...")
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')
except Exception as e:
    logger.error(f"Error downloading NLTK resources: {e}")
    raise

class TextPreprocessor:
    def __init__(self, mongo_uri: str, db_name: str = "harcelement", collection_name: str = "posts", 
                 processed_collection_name: str = "preprocessed_posts"):
        """Initialize the text preprocessor with MongoDB connection."""
        self.mongo_client = pymongo.MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        self.collection = self.db[collection_name]
        self.processed_collection = self.db[processed_collection_name]
        
        # Create index for processed collection
        self.processed_collection.create_index("url", unique=True)
        
        # Initialize NLP tools
        self.stop_words = set(stopwords.words('english'))
        self.stop_words.update(set(stopwords.words('french')))  # Add French stopwords
        self.lemmatizer = WordNetLemmatizer()
        
        logger.info("Text preprocessor initialized")
    
    def remove_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not isinstance(text, str):
            return ""
        return re.sub(r'<.*?>', '', text)
    
    def remove_urls(self, text: str) -> str:
        """Remove URLs from text."""
        if not isinstance(text, str):
            return ""
        return re.sub(r'http\S+|www\S+|https\S+', '', text)
    
    def remove_special_chars(self, text: str) -> str:
        """Remove special characters, punctuation and numbers."""
        if not isinstance(text, str):
            return ""
        return re.sub(r'[^a-zA-Z\s]', '', text)
    
    def preprocess_text(self, text: str) -> str:
        """Apply all preprocessing steps to text."""
        if not isinstance(text, str) or not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove HTML tags
        text = self.remove_html(text)
        
        # Remove URLs
        text = self.remove_urls(text)
        
        # Remove special characters
        text = self.remove_special_chars(text)
        
        # Simple tokenization without using nltk.tokenize.word_tokenize to avoid punkt issues
        tokens = text.split()
        
        # Remove stopwords and lemmatize
        clean_tokens = [
            self.lemmatizer.lemmatize(token) 
            for token in tokens 
            if token not in self.stop_words and len(token) > 2
        ]
        
        # Join back into text
        clean_text = ' '.join(clean_tokens)
        
        return clean_text
    
    def process_documents(self) -> List[Dict[str, Any]]:
        """Extract and preprocess documents from MongoDB."""
        processed_docs = []
        total_count = self.collection.count_documents({})
        logger.info(f"Processing {total_count} documents")
        
        count = 0
        for doc in self.collection.find():
            # Extract required fields
            title = doc.get('title', '')
            content = doc.get('content', '')
            author = doc.get('author', 'unknown')
            date = doc.get('date')
            url = doc.get('url', '')
            
            # Preprocess text fields
            processed_title = self.preprocess_text(title)
            processed_content = self.preprocess_text(content)
            
            # Create processed document
            processed_doc = {
            
                'title': processed_title,
                'content': processed_content,
                'author': author,
                'date': date,
                'url': url
            }
            
            processed_docs.append(processed_doc)
            count += 1
            
            # Log progress
            if count % 100 == 0 or count == total_count:
                logger.info(f"Processed {count}/{total_count} documents")
        
        logger.info(f"Preprocessing completed. Processed {count} documents")
        return processed_docs
    
    def save_to_mongodb(self, processed_docs: List[Dict[str, Any]]) -> int:
        """Save preprocessed documents to MongoDB collection."""
        if not processed_docs:
            logger.warning("No documents to save to MongoDB")
            return 0
        
        inserted_count = 0
        skipped_count = 0
        
        for doc in processed_docs:
            try:
                # Use URL as a unique identifier to avoid duplicates
                result = self.processed_collection.update_one(
                    {"url": doc["url"]}, 
                    {"$set": doc}, 
                    upsert=True
                )
                
                if result.upserted_id:
                    inserted_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Error saving document to MongoDB: {e}")
        
        logger.info(f"MongoDB save completed. Inserted: {inserted_count}, Updated: {skipped_count}")
        return inserted_count
    
    def save_to_csv(self, processed_docs: List[Dict[str, Any]], filename: str = "preprocessed_data.csv"):
        """Save preprocessed documents to CSV file."""
        if not processed_docs:
            logger.warning("No documents to save")
            return
        
        df = pd.DataFrame(processed_docs)
        df.to_csv(filename, index=False, encoding='utf-8')
        logger.info(f"Saved {len(processed_docs)} preprocessed documents to {filename}")
    
    def close(self):
        """Close MongoDB connection."""
        self.mongo_client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
    
    preprocessor = TextPreprocessor(mongo_uri)
    try:
        # Process documents
        processed_docs = preprocessor.process_documents()
        
        # Save to MongoDB instead of CSV
        preprocessor.save_to_mongodb(processed_docs)
    finally:
        preprocessor.close()