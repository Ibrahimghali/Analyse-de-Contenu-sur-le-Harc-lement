import pytest
from unittest.mock import MagicMock, patch
import datetime
import pymongo
import pandas as pd
from src.processeing.nlp_pipeline import NLPProcessor

class TestNLPProcessor:
    @pytest.fixture
    def mock_mongo_client(self):
        """Create a mock MongoDB client and collections"""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_preprocessed_collection = MagicMock()
        mock_enriched_collection = MagicMock()
        
        # Configure mock database access
        mock_db.__getitem__.side_effect = lambda x: mock_preprocessed_collection if x == "preprocessed_posts" else mock_enriched_collection
        mock_client.__getitem__.return_value = mock_db
        
        # Set up test documents
        mock_preprocessed_collection.count_documents.return_value = 3
        mock_preprocessed_collection.find.return_value = [
            {
                "title": "English Post",
                "content": "This is a positive post about happiness and success.",
                "author": "user1",
                "date": datetime.datetime.now(),
                "url": "http://example.com/1"
            },
            {
                "title": "French Post",
                "content": "C'est un post négatif sur la tristesse et l'échec.",
                "author": "user2",
                "date": datetime.datetime.now(),
                "url": "http://example.com/2"
            },
            {
                "title": "Neutral Post",
                "content": "This is a factual statement without emotion.",
                "author": "user3",
                "date": datetime.datetime.now(),
                "url": "http://example.com/3"
            }
        ]
        
        # Configure enriched collection find
        mock_enriched_collection.find.return_value = [
            {
                "title": "English Post",
                "content": "This is a positive post about happiness and success.",
                "author": "user1",
                "date": datetime.datetime.now(),
                "url": "http://example.com/1",
                "language": "en",
                "sentiment": "positive",
                "polarity": 0.75
            }
        ]
        
        return mock_client
    
    @patch("pymongo.MongoClient")
    def test_init(self, mock_mongo):
        """Test NLPProcessor initialization"""
        mock_mongo.return_value = self.mock_mongo_client()
        
        processor = NLPProcessor("mongodb://test")
        
        assert processor.mongo_client is not None
        assert processor.db is not None
        assert processor.preprocessed_collection is not None
        assert processor.enriched_collection is not None
        processor.enriched_collection.create_index.assert_called_once()
    
    @patch("src.processeing.nlp_pipeline.detect")
    def test_detect_language(self, mock_detect):
        """Test language detection"""
        processor = NLPProcessor("mongodb://test")
        
        # Test successful detection
        mock_detect.return_value = "en"
        assert processor.detect_language("This is English text") == "en"
        
        # Test French detection
        mock_detect.return_value = "fr"
        assert processor.detect_language("C'est un texte français") == "fr"
        
        # Test with too short text
        assert processor.detect_language("Hi") == "unknown"
        
        # Test with empty text
        assert processor.detect_language("") == "unknown"
        
        # Test with exception
        mock_detect.side_effect = Exception("Detection error")
        assert processor.detect_language("Error text") == "unknown"
    
    @patch("src.processeing.nlp_pipeline.TextBlob")
    def test_analyze_sentiment(self, mock_textblob):
        """Test sentiment analysis"""
        processor = NLPProcessor("mongodb://test")
        
        # Test positive sentiment
        mock_blob = MagicMock()
        mock_blob.sentiment.polarity = 0.75
        mock_textblob.return_value = mock_blob
        
        result = processor.analyze_sentiment("I am very happy", "en")
        assert result["sentiment"] == "positive"
        assert result["polarity"] == 0.75
        
        # Test negative sentiment
        mock_blob.sentiment.polarity = -0.5
        result = processor.analyze_sentiment("I am very sad", "en")
        assert result["sentiment"] == "negative"
        assert result["polarity"] == -0.5
        
        # Test neutral sentiment
        mock_blob.sentiment.polarity = 0.0
        result = processor.analyze_sentiment("This is a fact", "en")
        assert result["sentiment"] == "neutral"
        assert result["polarity"] == 0.0
        
        # Test with empty text
        result = processor.analyze_sentiment("", "en")
        assert result["sentiment"] == "neutral"
        assert result["polarity"] == 0
    
    @patch("pymongo.MongoClient")
    def test_process_documents(self, mock_mongo):
        """Test document processing pipeline"""
        mock_mongo.return_value = self.mock_mongo_client()
        
        processor = NLPProcessor("mongodb://test")
        
        # Mock the language detection and sentiment analysis
        with patch.object(processor, "detect_language") as mock_detect_language, \
             patch.object(processor, "analyze_sentiment") as mock_analyze_sentiment:
            
            # Configure mocks
            mock_detect_language.side_effect = ["en", "fr", "en"]
            mock_analyze_sentiment.side_effect = [
                {"polarity": 0.75, "sentiment": "positive"},
                {"polarity": -0.5, "sentiment": "negative"},
                {"polarity": 0.0, "sentiment": "neutral"}
            ]
            
            # Process documents
            processed_count = processor.process_documents()
            
            # Check results
            assert processed_count == 3
            assert mock_detect_language.call_count == 3
            assert mock_analyze_sentiment.call_count == 3
            assert processor.enriched_collection.update_one.call_count == 3
    
    @patch("pymongo.MongoClient")
    @patch("pandas.DataFrame")
    def test_export_to_csv(self, mock_dataframe, mock_mongo):
        """Test exporting to CSV"""
        mock_client = self.mock_mongo_client()
        mock_mongo.return_value = mock_client
        
        processor = NLPProcessor("mongodb://test")
        
        # Mock DataFrame and to_csv
        mock_df = MagicMock()
        mock_dataframe.return_value = mock_df
        
        # Test export
        processor.export_to_csv("test_output.csv")
        
        # Verify CSV export
        mock_dataframe.assert_called_once()
        mock_df.to_csv.assert_called_once_with("test_output.csv", index=False, encoding='utf-8')
        
        # Test with no documents
        processor.enriched_collection.find.return_value = []
        processor.export_to_csv("empty.csv")
        # Should not call to_csv again
        assert mock_df.to_csv.call_count == 1
    
    @patch("pymongo.MongoClient")
    def test_process_documents_error(self, mock_mongo):
        """Test error handling in process_documents"""
        mock_client = self.mock_mongo_client()
        mock_mongo.return_value = mock_client
        
        processor = NLPProcessor("mongodb://test")
        
        # Set up error on update
        processor.enriched_collection.update_one.side_effect = pymongo.errors.PyMongoError("Test error")
        
        # Mock the language detection and sentiment analysis to avoid external calls
        with patch.object(processor, "detect_language", return_value="en"), \
             patch.object(processor, "analyze_sentiment", return_value={"polarity": 0, "sentiment": "neutral"}):
            
            # Process should continue despite errors
            processed_count = processor.process_documents()
            
            # Should have attempted all documents but counted none as successful
            assert processed_count == 0
            assert processor.enriched_collection.update_one.call_count == 3
    
    @patch("pymongo.MongoClient")
    def test_close(self, mock_mongo):
        """Test connection closing"""
        mock_client = self.mock_mongo_client()
        mock_mongo.return_value = mock_client
        
        processor = NLPProcessor("mongodb://test")
        processor.close()
        
        mock_client.close.assert_called_once()