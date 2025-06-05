import pymongo
import logging
from elasticsearch import Elasticsearch, helpers
from datetime import datetime
from typing import Dict, Any, List
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('elasticsearch_indexer')

class ElasticsearchIndexer:
    def __init__(
        self, 
        mongo_uri: str, 
        es_host: str = "localhost", 
        es_port: int = 9200,
        db_name: str = "harcelement", 
        collection_name: str = "enriched_posts",
        index_name: str = "harcelement_posts"
    ):
        """Initialize connections to MongoDB and Elasticsearch."""
        # MongoDB connection
        self.mongo_client = pymongo.MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        self.collection = self.db[collection_name]
        
        # Elasticsearch connection - FIXED VERSION
        self.es = Elasticsearch([f"http://{es_host}:{es_port}"])
        self.index_name = index_name
        
        logger.info("Elasticsearch indexer initialized")
    
    def create_index(self):
        """Create Elasticsearch index with appropriate mappings."""
        # Define index mappings
        mappings = {
            "mappings": {
                "properties": {
                    "titre": {"type": "keyword"},
                    "contenu": {"type": "text", "analyzer": "standard"},
                    "auteur": {"type": "keyword"},
                    "date": {"type": "date"},
                    "url": {"type": "keyword"},
                    "langue": {"type": "keyword"},
                    "sentiment": {"type": "keyword"},
                    "score": {"type": "float"},
                    "indexed_at": {"type": "date"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        }
        
        # Check if index exists
        if self.es.indices.exists(index=self.index_name):
            logger.warning(f"Index {self.index_name} already exists. Deleting...")
            self.es.indices.delete(index=self.index_name)
        
        # Create index
        self.es.indices.create(index=self.index_name, body=mappings)
        logger.info(f"Created Elasticsearch index: {self.index_name}")
    
    def transform_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Transform MongoDB document to Elasticsearch document."""
        # Extract polarity for score
        score = doc.get("polarity", 0)
        
        # Create Elasticsearch document
        es_doc = {
            "titre": doc.get("title", ""),
            "contenu": doc.get("content", ""),
            "auteur": doc.get("author", "unknown"),
            "date": doc.get("date", datetime.now()),
            "url": doc.get("url", ""),
            "langue": doc.get("language", "unknown"),
            "sentiment": doc.get("sentiment", "neutral"),
            "score": score,
            "indexed_at": datetime.now()
        }
        
        return es_doc
    
    def index_documents(self):
        """Index all documents from MongoDB to Elasticsearch."""
        total_count = self.collection.count_documents({})
        logger.info(f"Indexing {total_count} documents to Elasticsearch")
        
        # Prepare bulk indexing
        actions = []
        for doc in self.collection.find():
            es_doc = self.transform_document(doc)
            
            # Create action for bulk indexing
            action = {
                "_index": self.index_name,
                "_source": es_doc
            }
            
            actions.append(action)
            
            # Bulk index in batches of 500
            if len(actions) >= 500:
                self._bulk_index(actions)
                actions = []
        
        # Index any remaining documents
        if actions:
            self._bulk_index(actions)
            
        logger.info(f"Completed indexing to Elasticsearch")
    
    def _bulk_index(self, actions: List[Dict[str, Any]]):
        """Perform bulk indexing to Elasticsearch."""
        try:
            success, errors = helpers.bulk(self.es, actions, stats_only=True)
            logger.info(f"Bulk indexed {success} documents to Elasticsearch")
            if errors:
                logger.error(f"Encountered {errors} errors during bulk indexing")
        except Exception as e:
            logger.error(f"Error during bulk indexing: {e}")
    
    def close(self):
        """Close connections."""
        self.mongo_client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    load_dotenv()
    
    # Get configuration from environment variables
    mongo_uri = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
    es_host = os.getenv("ES_HOST", "localhost")
    es_port = int(os.getenv("ES_PORT", "9200"))
    
    indexer = ElasticsearchIndexer(
        mongo_uri=mongo_uri,
        es_host=es_host,
        es_port=es_port
    )
    
    try:
        # Create index
        indexer.create_index()
        
        # Index documents
        indexer.index_documents()
    finally:
        indexer.close()