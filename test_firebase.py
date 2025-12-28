import asyncio
from firebase_service import initialize_firebase, get_database_stats
from models_firebase import Book, Student, Quiz
from chroma_service import get_collection_stats

async def test_integration():
    print("\n" + "="*60)
    print("Testing Firebase + ChromaDB Integration")
    print("="*60)
    
    # Test Firebase
    try:
        initialize_firebase()
        print("\n✓ Firebase connected successfully")
        
        stats = get_database_stats()
        print("\nFirebase Collections:")
        for collection, count in stats.items():
            print(f"  - {collection}: {count} documents")
    except Exception as e:
        print(f"\n✗ Firebase error: {e}")
        return
    
    # Test ChromaDB
    try:
        chroma_stats = get_collection_stats()
        print(f"\nChromaDB:")
        print(f"  - Total chunks: {chroma_stats['total_chunks']}")
        print(f"  - Location: {chroma_stats['persist_directory']}")
        print("\n✓ ChromaDB connected successfully")
    except Exception as e:
        print(f"\n✗ ChromaDB error: {e}")
        return
    
    # Test creating a book
    try:
        book = Book.create(
            title="Test Book",
            author="Test Author",
            file_path="new-oxford-secondary-science-tg-8.pdf"
        )
        print(f"\n✓ Created test book: {book['id']}")
    except Exception as e:
        print(f"\n✗ Error creating book: {e}")
    
    print("\n" + "="*60)
    print("✓ Integration test complete!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_integration())