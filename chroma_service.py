import os
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional # Added Optional
import json

# Get configuration from environment variables
CHROMA_PERSIST_DIR = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
COLLECTION_NAME = 'book_chunks'

# Global variables to hold the initialized client and collection
# They are initialized to None and loaded lazily (only once)
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None


# =============================================================================
# LAZY INITIALIZATION FUNCTIONS
# =============================================================================

def initialize_chroma():
    """
    Initializes the ChromaDB client and collection.
    This function must be called explicitly before accessing the database.
    It will only run the heavy loading/initialization steps once per worker.
    """
    global _client, _collection
    
    if _collection is not None:
        print("ℹ️  ChromaDB already initialized in this worker.")
        return

    print(f"🔄 Initializing ChromaDB client in: {CHROMA_PERSIST_DIR} (This loads the embedding model once...)")
    try:
        # 1. Initialize the Persistent Client (This step involves model loading)
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

        # 2. Get or create collection
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Curriculum text chunks with embeddings"},
            # Uses the default embedding function (SentenceTransformers('all-MiniLM-L6-v2'))
        )
        print(f"✓ ChromaDB client and collection '{COLLECTION_NAME}' ready.")
        
    except Exception as e:
        print(f"❌ Error initializing ChromaDB: {e}")
        # Reset globals to None if initialization fails
        _client = None
        _collection = None 
        raise

def _get_collection() -> chromadb.Collection:
    """Helper function to get the initialized collection, ensuring it is initialized first."""
    if _collection is None:
        # Attempt to initialize if it hasn't been done yet
        initialize_chroma() 
    
    if _collection is None:
        raise ConnectionError("ChromaDB collection failed to initialize. Check logs for model loading errors.")

    return _collection

# =============================================================================
# SERVICE FUNCTIONS (Refactored to use _get_collection)
# =============================================================================

def add_chunks(book_id: int, chunks: List[Dict[str, Any]]):
    """Adds chunks to the ChromaDB collection with automatic vectorization."""
    collection = _get_collection() # Use local collection reference
    
    if not chunks:
        print("Warning: No chunks to add")
        return 0
    
    ids = [c['id'] for c in chunks]
    documents = [c['text'] for c in chunks]
    metadatas = [c['metadata'] for c in chunks]
    
    print(f"\n📦 Adding {len(chunks)} chunks to ChromaDB...")
    print(f"   Book ID: {book_id}")
    
    try:
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        # Verify chunks were added
        count = collection.count()
        print(f"✓ Successfully added {len(chunks)} chunks")
        print(f"✓ Total chunks in database: {count}")
        
        return len(chunks)
        
    except Exception as e:
        print(f"✗ Error adding chunks: {e}")
        raise


def query(query_text: str, n_results: int = 6, book_id: int = None) -> Dict[str, Any]:
    """Queries the ChromaDB collection for relevant documents using semantic search."""
    collection = _get_collection() # Use local collection reference
    
    print(f"\n🔍 Querying ChromaDB for: '{query_text}'")
    print(f"   Requesting {n_results} results")
    
    try:
        # Build where clause if book_id specified
        where_clause = None
        if book_id is not None:
            # IMPORTANT: ChromaDB metadata uses "bookId" (case-sensitive)
            where_clause = {"bookId": book_id} 
            print(f"   Filtering by book_id: {book_id}")
            
        # Query with semantic search (ChromaDB does the vector magic!)
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_clause,
            include=['documents', 'metadatas', 'distances']
        )
        
        # ChromaDB returns nested lists, so we flatten them
        documents = results['documents'][0] if results['documents'] else []
        metadatas = results['metadatas'][0] if results['metadatas'] else []
        ids = results['ids'][0] if results['ids'] else []
        distances = results['distances'][0] if 'distances' in results else []
        
        print(f"✓ Found {len(documents)} relevant chunks")
        
        # Show relevance scores
        if distances:
            print(f"   Relevance scores (lower = more similar):")
            for i, dist in enumerate(distances[:3]):
                print(f"     Chunk {i+1}: {dist:.4f}")
        
        return {
            "documents": documents,
            "metadatas": metadatas,
            "ids": ids,
            "distances": distances
        }
        
    except Exception as e:
        print(f"✗ Error querying ChromaDB: {e}")
        return {"documents": [], "metadatas": [], "ids": [], "distances": []}


def get_collection_stats() -> Dict[str, Any]:
    """Get statistics about the ChromaDB collection"""
    collection = _get_collection() # Use local collection reference
    
    try:
        count = collection.count()
        
        # Get a sample of data
        sample = collection.peek(limit=3)
        
        return {
            "total_chunks": count,
            "collection_name": COLLECTION_NAME,
            "persist_directory": CHROMA_PERSIST_DIR,
            "sample_ids": sample['ids'] if sample else []
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {"total_chunks": 0, "error": str(e)}


def clear_collection():
    """Clear all data from the collection (use with caution!)"""
    global _client, _collection # Must declare global for assignment
    
    # Ensure client is initialized before attempting to delete
    if _client is None:
        initialize_chroma()
        
    if _client:
        try:
            _client.delete_collection(name=COLLECTION_NAME)
            print(f"✓ Deleted collection '{COLLECTION_NAME}'")
            
            # Recreate empty collection and assign to global _collection
            _collection = _client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "Curriculum text chunks with embeddings"}
            )
            print(f"✓ Created new empty collection '{COLLECTION_NAME}'")
            
        except Exception as e:
            print(f"Error clearing collection: {e}")
            raise


def delete_book_chunks(book_id: int):
    """Delete all chunks for a specific book"""
    collection = _get_collection() # Use local collection reference
    
    try:
        # Query all chunks for this book
        results = collection.get(
            where={"bookId": book_id}
        )
        
        if results['ids']:
            collection.delete(ids=results['ids'])
            print(f"✓ Deleted {len(results['ids'])} chunks for book {book_id}")
        else:
            print(f"No chunks found for book {book_id}")
            
    except Exception as e:
        print(f"Error deleting book chunks: {e}")


def check_chunks_exist(book_id: int) -> int:
    """Check if chunks already exist for a given book_id"""
    collection = _get_collection() # Use local collection reference
    
    try:
        # Query all chunks for this book
        results = collection.get(
            where={"bookId": book_id},
            include=['metadatas']
        )
        
        count = len(results['ids']) if results and 'ids' in results else 0
        
        if count > 0:
            print(f"ℹ️  Found {count} existing chunks for book_id={book_id}")
        
        return count
        
    except Exception as e:
        print(f"Error checking chunks: {e}")
        return 0


# Include the new initialization function in the exports
__all__ = ['add_chunks', 'query', 'get_collection_stats', 'clear_collection', 'delete_book_chunks', 'check_chunks_exist', 'initialize_chroma']


# Print initialization info
if __name__ == "__main__":
    print("\n" + "="*60)
    print("ChromaDB Service Status")
    print("="*60)
    
    # Initialize first (if run directly)
    try:
        initialize_chroma()
        stats = get_collection_stats()
        print(f"Total chunks: {stats['total_chunks']}")
        print(f"Location: {stats['persist_directory']}")
    except Exception as e:
        print(f"Initialization failed: {e}")

    print("="*60)
