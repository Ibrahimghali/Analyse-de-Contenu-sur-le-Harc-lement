import pytest
from unittest.mock import MagicMock, patch
import datetime
import pymongo
from src.processeing.preprocessing import TextPreprocessor

class TestTextPreprocessor:
    @pytest.fixture
    def mock_mongo_client(self):
        """Create a mock MongoDB client and collections"""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_processed_collection = MagicMock()
        
        # Configure mock database access
        mock_db.__getitem__.side_effect = lambda x: mock_collection if x == "posts" else mock_processed_collection
        mock_client.__getitem__.return_value = mock_db
        
        # Set up test documents
        mock_collection.count_documents.return_value = 2
        mock_collection.find.return_value = [
            {
                "title": "Test Title <b>HTML</b>",
                "content": "This is a test content with http://example.com URL and special chars !@#$%^&*().",
                "author": "testuser",
                "date": datetime.datetime.now(),
                "url": "http://example.com/1"
            },
            {
                "title": "Another Test",
                "content": "This is another test with stopwords like the and a.",
                "author": "anotheruser",
                "date": datetime.datetime.now(),
                "url": "http://example.com/2"
            }
        ]
        
        # Configure update_one mock behavior
        mock_update_result = MagicMock()
        mock_update_result.upserted_id = "new_id"
        mock_processed_collection.update_one.return_value = mock_update_result
        
        return mock_client
    
    @patch("pymongo.MongoClient")
    def test_init(self, mock_mongo):
        """Test TextPreprocessor initialization"""
        mock_mongo.return_value = self.mock_mongo_client()
        
        processor = TextPreprocessor("mongodb://test")
        
        assert processor.mongo_client is not None
        assert processor.db is not None
        assert processor.collection is not None
        assert processor.processed_collection is not None
        processor.processed_collection.create_index.assert_called_once()
    
    def test_remove_html(self):
        """Test HTML removal functionality"""
        processor = TextPreprocessor("mongodb://test")
        
        # Test HTML removal
        text = "<div>This is <b>bold</b> text</div>"
        result = processor.remove_html(text)
        assert result == "This is bold text"
        
        # Test with non-string input
        assert processor.remove_html(None) == ""
        assert processor.remove_html(123) == ""
    
    def test_remove_urls(self):
        """Test URL removal functionality"""
        processor = TextPreprocessor("mongodb://test")
        
        # Test URL removal
        text = "Visit http://example.com or https://github.com/test for more info"
        result = processor.remove_urls(text)
        assert result == "Visit  or  for more info"
        
        # Test with non-string input
        assert processor.remove_urls(None) == ""
    
    def test_remove_special_chars(self):
        """Test special character removal"""
        processor = TextPreprocessor("mongodb://test")
        
        # Test special character removal
        text = "Hello, world! This is a test. 123"
        result = processor.remove_special_chars(text)
        assert result == "Hello world This is a test "
    
    def test_preprocess_text(self):
        """Test the full text preprocessing pipeline"""
        processor = TextPreprocessor("mongodb://test")
        
        # Patch stop words and lemmatizer for controlled testing
        with patch.object(processor, "stop_words", {"am", "a", "the"}), \
             patch.object(processor, "lemmatizer") as mock_lemmatizer:
            
            mock_lemmatizer.lemmatize.side_effect = lambda x: "run" if x == "running" else x
            
            # Test full preprocessing
            text = "<p>Hello, world! I am running to the store.</p>"
            result = processor.preprocess_text(text)
            
            # Should be lowercase, no HTML, no special chars, no stopwords, lemmatized
            assert "hello world running store" in result
    
    @patch("pymongo.MongoClient")
    def test_process_documents(self, mock_mongo):
        """Test document processing pipeline"""
        mock_mongo.return_value = self.mock_mongo_client()
        
        processor = TextPreprocessor("mongodb://test")
        
        # Control the preprocessing output
        with patch.object(processor, "preprocess_text") as mock_preprocess:
            mock_preprocess.side_effect = lambda x: f"processed_{x}" if x else ""
            
            result = processor.process_documents()
            
            # Verify document processing
            assert len(result) == 2
            assert result[0]["title"] == "processed_Test Title <b>HTML</b>"
            assert result[0]["author"] == "testuser"
            assert processor.collection.find.call_count == 1
    
    @patch("pymongo.MongoClient")
    def test_save_to_mongodb(self, mock_mongo):
        """Test saving documents to MongoDB"""
        mock_mongo.return_value = self.mock_mongo_client()
        
        processor = TextPreprocessor("mongodb://test")
        
        # Test with documents
        docs = [
            {
                "title": "Processed Title",
                "content": "Processed Content",
                "author": "testuser",
                "date": datetime.datetime.now(),
                "url": "http://example.com/1"
            }
        ]
        
        # First document is inserted, second is updated
        processor.processed_collection.update_one.side_effect = [
            MagicMock(upserted_id="new_id"),
            MagicMock(upserted_id=None)
        ]
        
        inserted_count = processor.save_to_mongodb(docs)
        
        assert inserted_count == 1
        assert processor.processed_collection.update_one.call_count == 1
        
        # Test with empty list
        assert processor.save_to_mongodb([]) == 0
    
    @patch("pymongo.MongoClient")
    def test_save_to_mongodb_error(self, mock_mongo):
        """Test error handling when saving to MongoDB"""
        mock_mongo.return_value = self.mock_mongo_client()
        
        processor = TextPreprocessor("mongodb://test")
        
        # Set up an exception
        processor.processed_collection.update_one.side_effect = pymongo.errors.PyMongoError("Test error")
        
        docs = [{"url": "http://example.com/error", "content": "test"}]
        
        # Should handle the error gracefully
        inserted_count = processor.save_to_mongodb(docs)
        assert inserted_count == 0
    
    @patch("pymongo.MongoClient")
    def test_close(self, mock_mongo):
        """Test connection closing"""
        mock_client = self.mock_mongo_client()
        mock_mongo.return_value = mock_client
        
        processor = TextPreprocessor("mongodb://test")
        processor.close()
        
        mock_client.close.assert_called_once()