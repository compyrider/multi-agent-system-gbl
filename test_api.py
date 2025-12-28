"""
Test script for Quiz Generation API
Tests both endpoints locally or on Render
UPDATED: Better timeout handling for large PDFs and a comprehensive summary.
"""

import requests
import json
import os
import time
from pathlib import Path
from typing import Optional, Tuple, Any, List

# Configuration
BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:10000')
TEST_PDF_PATH = "new-oxford-secondary-science-tg-8.pdf"

# TIMEOUT SETTINGS (in seconds)
# TIMEOUT SETTINGS (in seconds) - UPDATED FOR RENDER
# TIMEOUT SETTINGS - Adjusted for Render Free Tier
HEALTH_TIMEOUT = 90  # Extra time for cold starts
QUIZ_GENERATE_TIMEOUT = 1800
ADAPTIVE_QUIZ_TIMEOUT = 180
GENERAL_TIMEOUT = 90  # Extra time for free tier


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def print_result(response: requests.Response):
    """Pretty print API response"""
    try:
        if response.status_code < 300:
            print(f"✓ Status: {response.status_code}")
            print(f"Response:\n{json.dumps(response.json(), indent=2)}")
        else:
            print(f"✗ Status: {response.status_code}")
            print(f"Error:\n{json.dumps(response.json(), indent=2)}")
    except requests.exceptions.JSONDecodeError:
        # Handle cases where the response is not JSON (e.g., 404, 500 without json body)
        print(f"✗ Status: {response.status_code}")
        print(f"Error: Non-JSON response received. Content snippet: {response.text[:100]}...")
    print()


def format_time(seconds: int):
    """Format seconds into minutes:seconds string"""
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}m {seconds}s"


# =============================================================================
# QUIZ GENERATION TESTS
# =============================================================================

def test_health_check() -> bool:
    """Test the /health endpoint"""
    print_section("1. Testing Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=HEALTH_TIMEOUT)
        print_result(response)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: Could not connect to {BASE_URL}/health. ({e})")
        return False


def test_generate_quiz_from_pdf() -> Tuple[Optional[str], bool]:
    """Test the /api/quiz/generate endpoint with file upload"""
    print_section(f"2. Testing Quiz Generation from PDF ({TEST_PDF_PATH})")
    
    if not Path(TEST_PDF_PATH).exists():
        print(f"✗ Error: Test PDF not found at: {TEST_PDF_PATH}")
        print("Please ensure the file is in the same directory as test_api.py or update TEST_PDF_PATH.")
        return None, False
    
    # Data to be sent with the file
    data = {
        'topic': 'Lesson 4 Plan Receptors',
        'n_questions': 5,
        'book_title': TEST_PDF_PATH,
        'book_author': 'Oxford University Press',
        'teacher_id': 'test_teacher_123',
        'teacher_name': 'Test Automation',
    }
    
    files = {
        'file': (Path(TEST_PDF_PATH).name, open(TEST_PDF_PATH, 'rb'), 'application/pdf')
    }
    
    print(f"Payload: {json.dumps(data, indent=2)}")
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/api/quiz/generate", 
            data=data, 
            files=files, 
            timeout=QUIZ_GENERATE_TIMEOUT
        )
        end_time = time.time()
        duration = end_time - start_time
        print(f"Total Request Time: {format_time(int(duration))}")
        
        print_result(response)
        
        if response.status_code == 200 and response.json().get('success'):
            return response.json().get('book_id'), True
            
    except requests.exceptions.Timeout:
        print(f"✗ Error: Request timed out after {format_time(QUIZ_GENERATE_TIMEOUT)}")
    except requests.exceptions.RequestException as e:
        print(f"✗ Error during request: {e}")
        
    return None, False


def test_generate_adaptive_quiz(book_id: Optional[str] = None) -> bool:
    """Test the /api/quiz/adaptive endpoint"""
    print_section("3. Testing Adaptive Quiz Generation")
    
    # We must have a book_id to simulate a real scenario, but allow a fallback
    if book_id is None:
        book_id = 'unknown_book_id'
        print("⚠️  Warning: No book_id provided from previous test. Using a dummy ID.")

    payload = {
        'student_id': 'test_student_001',
        'book_id': book_id,
        'topic': 'Lesson 4 plan Receptors',
        'n_questions': 5,
        'teacher_id': 'adaptive_test_agent',
        'teacher_name': 'Adaptive Test System',
        'quiz_name': 'Adaptive Test for Student 001',
    }

    print(f"Payload: {json.dumps(payload, indent=2)}")

    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/api/quiz/adaptive", 
            json=payload, 
            timeout=ADAPTIVE_QUIZ_TIMEOUT
        )
        end_time = time.time()
        duration = end_time - start_time
        print(f"Total Request Time: {format_time(int(duration))}")
        
        print_result(response)
        
        return response.status_code == 200 and response.json().get('success')

    except requests.exceptions.Timeout:
        print(f"✗ Error: Request timed out after {format_time(ADAPTIVE_QUIZ_TIMEOUT)}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Error during request: {e}")
        return False


def test_get_database_stats() -> bool:
    """Test the /api/stats endpoint (formerly 4)"""
    print_section("4. Testing Database Stats")
    
    try:
        response = requests.get(f"{BASE_URL}/api/stats", timeout=GENERAL_TIMEOUT)
        print_result(response)
        return response.status_code == 200 and response.json().get('success')
    except requests.exceptions.RequestException as e:
        print(f"✗ Error during request: {e}")
        return False


def test_list_books() -> bool:
    """Test the /api/books endpoint (formerly 5)"""
    print_section("5. Testing List Books")
    
    try:
        response = requests.get(f"{BASE_URL}/api/books", timeout=GENERAL_TIMEOUT)
        print_result(response)
        return response.status_code == 200 and response.json().get('success')
    except requests.exceptions.RequestException as e:
        print(f"✗ Error during request: {e}")
        return False


def test_list_quizzes() -> bool:
    """Test the /api/quizzes endpoint (formerly 6)"""
    print_section("6. Testing List Quizzes")
    
    try:
        response = requests.get(f"{BASE_URL}/api/quizzes", timeout=GENERAL_TIMEOUT)
        print_result(response)
        return response.status_code == 200 and response.json().get('success')
    except requests.exceptions.RequestException as e:
        print(f"✗ Error during request: {e}")
        return False


def test_student_performance() -> bool:
    """Test the /api/students/<student_id>/performance endpoint"""
    print_section("7. Testing Student Performance Stats")
    
    # Use the same dummy student ID used in the adaptive test
    student_id = 'test_student_001'
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/students/{student_id}/performance", 
            timeout=GENERAL_TIMEOUT
        )
        print_result(response)
        # Note: This endpoint might not exist yet, but we test for the response.
        # Assuming a successful response is 200 and has a 'success' flag if it exists.
        return response.status_code == 200 # and response.json().get('success', True)
    except requests.exceptions.RequestException as e:
        print(f"✗ Error during request: {e}")
        return False


# =============================================================================
# RUNNER
# =============================================================================

def run_all_tests():
    """Run the main test sequence and print summary"""
    
    # Run tests and capture results
    health_ok = test_health_check()
    book_id, quiz_ok = test_generate_quiz_from_pdf()
    adaptive_ok = test_generate_adaptive_quiz(book_id)
    stats_ok = test_get_database_stats()
    books_ok = test_list_books()
    quizzes_ok = test_list_quizzes()
    performance_ok = test_student_performance()

    # Summary
    print_section("TEST SUMMARY")
    
    # The summary structure matches the requested format but uses boolean variables
    # for accurate success/failure tracking.
    results = [
        ("Health Check", health_ok),
        ("Generate Quiz", quiz_ok),
        ("Adaptive Quiz", adaptive_ok),
        ("Database Stats", stats_ok),
        ("List Books", books_ok),
        ("List Quizzes", quizzes_ok),
        ("Student Performance", performance_ok)
    ]

    # Print summary table
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {name.ljust(25)}: {status}")
    print("\n" + "="*70)


def interactive_menu():
    """Interactive CLI menu for testing"""
    global BASE_URL
    
    while True:
        print("\n" + "-"*70)
        print("Choose a test to run:")
        print(" 1. Run Health Check (/health)")
        print(f" 2. Generate Quiz from PDF ({Path(TEST_PDF_PATH).name})")
        print(" 3. Generate Adaptive Quiz (Requires existing book data)")
        print(" 4. Get Database Stats (/api/stats)")
        print(" 5. List All Books (/api/books)")
        print(" 6. List All Quizzes (/api/quizzes)")
        print(" 7. Test Student Performance (/api/students/{id}/performance)") # Added new test
        print(" 8. Run All Tests (1-7 in sequence)")
        print(" 9. Change API Base URL (Current: " + BASE_URL + ")")
        print(" 10. Show Timeouts")
        print(" 11. Exit")
        print("-"*70)
        
        choice = input("Enter choice: ").strip()
        
        if choice == '1':
            test_health_check()
        elif choice == '2':
            test_generate_quiz_from_pdf()
        elif choice == '3':
            # Ask for book_id for adaptive test
            book_id = input("Enter book_id (optional, press Enter to use dummy ID): ").strip()
            test_generate_adaptive_quiz(book_id if book_id else None)
        elif choice == '4':
            test_get_database_stats()
        elif choice == '5':
            test_list_books()
        elif choice == '6':
            test_list_quizzes()
        elif choice == '7': # Added new test call
            test_student_performance()
        elif choice == '8': # Run All is now 1-7
            run_all_tests()
        elif choice == '9':
            new_url = input(f"Enter new base URL (e.g., http://localhost:8000): ").strip()
            if new_url:
                BASE_URL = new_url
                print(f"✓ Base URL updated to: {BASE_URL}")
        elif choice == '10':
            print("\nCurrent Timeouts:")
            print(f"  Quiz Generation: {format_time(QUIZ_GENERATE_TIMEOUT)}")
            print(f"  Adaptive Quiz: {format_time(ADAPTIVE_QUIZ_TIMEOUT)}")
            print("\nTo change timeouts, edit QUIZ_GENERATE_TIMEOUT and")
            print("ADAPTIVE_QUIZ_TIMEOUT at the top of test_api.py")
        elif choice == '11':
            print("\nGoodbye! 👋\n")
            break
        else:
            print("\n⚠️  Invalid choice. Please enter 1-11.\n")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("\n" + "🧪 Quiz Generation API Test Script")
    print("="*70)
    print(f"Base URL: {BASE_URL}")
    print(f"Test PDF: {TEST_PDF_PATH}")
    print(f"Quiz Timeout: {format_time(QUIZ_GENERATE_TIMEOUT)}")
    print("="*70)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        # Run all tests automatically
        run_all_tests()
    else:
        # Run in interactive mode
        interactive_menu()