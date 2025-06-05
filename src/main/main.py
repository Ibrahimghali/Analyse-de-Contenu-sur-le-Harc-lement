import os
import logging
import asyncio
import time
from dotenv import load_dotenv
from datetime import datetime

# Create logs directory before configuring logging
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/harcelement_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('main')

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
DB_NAME = "harcelement"
COLLECTION_NAME = "posts"

# Import existing scraper
from scrapers.scraper import main as run_scraper

# Import processing modules
from processeing.preprocessing import TextPreprocessor
from processeing.nlp_pipeline import NLPProcessor

# Import Elasticsearch indexer
from migration.es_ingest import ElasticsearchIndexer

def preprocess_data():
    """Preprocess scraped data."""
    logger.info("Starting data preprocessing phase")
    
    try:
        preprocessor = TextPreprocessor(MONGO_URI)
        processed_docs = preprocessor.process_documents()
        inserted_count = preprocessor.save_to_mongodb(processed_docs)
        
        logger.info(f"Data preprocessing phase completed. Processed {len(processed_docs)} documents, inserted {inserted_count}.")
        preprocessor.close()
        return len(processed_docs)
    except Exception as e:
        logger.error(f"Error during data preprocessing: {e}")
        return 0

def process_nlp():
    """Apply NLP processing to preprocessed data."""
    logger.info("Starting NLP processing phase")
    
    try:
        processor = NLPProcessor(MONGO_URI)
        processed_count = processor.process_documents()
        
        logger.info(f"NLP processing phase completed. Processed {processed_count} documents.")
        processor.close()
        return processed_count
    except Exception as e:
        logger.error(f"Error during NLP processing: {e}")
        return 0

def migrate_to_elasticsearch():
    """Migrate processed data to Elasticsearch."""
    logger.info("Starting Elasticsearch migration phase")
    
    try:
        es_host = os.getenv("ES_HOST", "localhost")
        es_port = int(os.getenv("ES_PORT", "9200"))
        
        indexer = ElasticsearchIndexer(
            mongo_uri=MONGO_URI,
            es_host=es_host,
            es_port=es_port,
            collection_name="enriched_posts"
        )
        
        # Create the index
        indexer.create_index()
        
        # Index the documents
        indexer.index_documents()
        
        logger.info("Elasticsearch migration phase completed")
        indexer.close()
        return True
    except Exception as e:
        logger.error(f"Error during Elasticsearch migration: {e}")
        return False

async def main():
    """Main execution flow."""
    start_time = time.time()
    logger.info("Starting harassment data pipeline")
    
    # Step 1: Run existing scraper
    logger.info("Starting data collection phase")
    try:
        await run_scraper()  # Call the main function from your existing scraper.py
        logger.info("Data collection phase completed")
    except Exception as e:
        logger.error(f"Error during data collection: {e}")
    
    # Step 2: Preprocess data
    preprocess_data()
    
    # Step 3: Process with NLP
    process_nlp()
    
    # Step 4: Migrate to Elasticsearch
    migrate_to_elasticsearch()
    
    elapsed_time = time.time() - start_time
    logger.info(f"Pipeline completed in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())