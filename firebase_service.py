"""
Firebase service for storing structured data using Realtime Database
Updated to match the exact schema structure from Firebase Console
Works alongside ChromaDB (which handles vector embeddings)
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, db, storage, initialize_app
except ImportError:
    print("WARNING: Firebase Admin SDK not installed. Run: pip install firebase-admin")
    firebase_admin = None

# Initialize Firebase
_db_ref = None
_storage_bucket = None


def initialize_firebase():
    """Initialize Firebase with credentials, Realtime Database, and Storage"""
    global _db_ref, _storage_bucket
    
    if _db_ref is not None:
        return _db_ref
    
    if firebase_admin is None:
        raise ImportError("Firebase Admin SDK not installed")
    
    # Get database URL and storage bucket from environment
    database_url = os.getenv('FIREBASE_DATABASE_URL')
    bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
    
    if not database_url:
        raise ValueError("FIREBASE_DATABASE_URL environment variable is required for Realtime Database")
    
    app_options = {
        'databaseURL': database_url
    }
    
    if bucket_name:
        app_options['storageBucket'] = bucket_name

    # Option 1: Use service account JSON file
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', './firebase-credentials.json')
    
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, app_options)
        print(f"✓ Firebase initialized with credentials from: {cred_path}")
    
    # Option 2: Use environment variables (for deployment)
    elif os.getenv('FIREBASE_PROJECT_ID'):
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.getenv('FIREBASE_PROJECT_ID'),
            "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
            "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
            "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
            "client_id": os.getenv('FIREBASE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv('FIREBASE_CERT_URL')
        })
        firebase_admin.initialize_app(cred, app_options)
        print("✓ Firebase initialized with environment variables")
    
    else:
        raise ValueError(
            "Firebase credentials not found. Either:\n"
            "1. Set FIREBASE_CREDENTIALS_PATH to your JSON file path, or\n"
            "2. Set individual Firebase environment variables\n"
            "3. Set FIREBASE_DATABASE_URL for Realtime Database"
        )
    
    _db_ref = db.reference()
    
    if bucket_name:
        _storage_bucket = storage.bucket()
        print(f"✓ Firebase Storage bucket instance created.")

    return _db_ref


def get_db():
    """Get Realtime Database reference"""
    global _db_ref
    if _db_ref is None:
        _db_ref = initialize_firebase()
    return _db_ref


def get_timestamp():
    """Get current timestamp as ISO string"""
    return datetime.now().isoformat()


# =============================================================================
# USER OPERATIONS (NEW)
# =============================================================================

def create_user(email: str, name: str, is_teacher: bool = False, user_id: str = None) -> Dict[str, Any]:
    """
    Create a new user (teacher or student)
    Schema: users/{userId}/ with email, name, isTeacher
    
    Args:
        email: User's email
        name: User's name
        is_teacher: Whether user is a teacher
        user_id: Optional custom user ID (auto-generated if not provided)
    """
    db_ref = get_db()
    
    user_data = {
        'email': email,
        'name': name,
        'isTeacher': is_teacher
    }
    
    if user_id:
        # Use provided user_id
        db_ref.child('users').child(user_id).set(user_data)
        user_data['id'] = user_id
    else:
        # Auto-generate user_id
        users_ref = db_ref.child('users')
        new_user_ref = users_ref.push(user_data)
        user_id = new_user_ref.key
        user_data['id'] = user_id
    
    print(f"✓ Created user: {name} ({'Teacher' if is_teacher else 'Student'}) (ID: {user_id})")
    
    return user_data


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by ID"""
    db_ref = get_db()
    
    user_data = db_ref.child('users').child(user_id).get()
    
    if user_data:
        user_data['id'] = user_id
        return user_data
    
    return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get a user by email"""
    db_ref = get_db()
    
    users_data = db_ref.child('users').get()
    
    if not users_data:
        return None
    
    for user_id, user_data in users_data.items():
        if user_data.get('email') == email:
            user_data['id'] = user_id
            return user_data
    
    return None


def list_users(is_teacher: bool = None) -> List[Dict[str, Any]]:
    """
    List all users, optionally filtered by role
    
    Args:
        is_teacher: None (all users), True (teachers only), False (students only)
    """
    db_ref = get_db()
    
    users_data = db_ref.child('users').get()
    
    if not users_data:
        return []
    
    users = []
    for user_id, user_data in users_data.items():
        if is_teacher is None or user_data.get('isTeacher', False) == is_teacher:
            user_data['id'] = user_id
            users.append(user_data)
    
    return users


# =============================================================================
# BOOK OPERATIONS
# =============================================================================

def create_book(title: str, author: str, file_path: str = None) -> Dict[str, Any]:
    """Create a new book record"""
    db_ref = get_db()
    
    book_data = {
        'title': title,
        'author': author,
        'file_path': file_path,
        'created_at': get_timestamp(),
        'chunk_count': 0
    }
    
    books_ref = db_ref.child('books')
    new_book_ref = books_ref.push(book_data)
    book_id = new_book_ref.key
    
    book_data['id'] = book_id
    
    print(f"✓ Created book: {title} (ID: {book_id})")
    
    return book_data


def get_book(book_id: str) -> Optional[Dict[str, Any]]:
    """Get a book by ID"""
    db_ref = get_db()
    
    book_data = db_ref.child('books').child(book_id).get()
    
    if book_data:
        book_data['id'] = book_id
        return book_data
    
    return None


def list_books() -> List[Dict[str, Any]]:
    """List all books"""
    db_ref = get_db()
    
    books_data = db_ref.child('books').get()
    
    if not books_data:
        return []
    
    books = []
    for book_id, book_data in books_data.items():
        book_data['id'] = book_id
        books.append(book_data)
    
    books.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return books


def update_book_chunk_count(book_id: str, chunk_count: int):
    """Update the chunk count for a book"""
    db_ref = get_db()
    
    db_ref.child('books').child(book_id).update({
        'chunk_count': chunk_count,
        'updated_at': get_timestamp()
    })


# =============================================================================
# QUIZ OPERATIONS (UPDATED TO MATCH SCHEMA)
# =============================================================================

def create_quiz(
    book_id: str, 
    topic: str, 
    questions: List[Dict[str, Any]], 
    teacherId: str = None, 
    teacherName: str = None, 
    name: str = None, 
    nQuestions: int = None,
    studentId: str = None,
    quizName: str = None,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create a new quiz following the exact schema:
    quizzes/{quizId}/attempts/{attemptId}/ contains ALL quiz data
    
    This creates the quiz structure and initial attempt entry
    """
    db_ref = get_db()
    
    # Generate quiz ID first
    quizzes_ref = db_ref.child('quizzes')
    new_quiz_ref = quizzes_ref.push()
    quiz_id = new_quiz_ref.key
    
    # Convert questions list to nested object structure (q1, q2, q3...)
    questions_dict = {}
    for i, question in enumerate(questions, 1):
        question_key = f"q{i}"
        questions_dict[question_key] = {
            'text': question.get('question', ''),
            'options': {
                '0': question.get('choices', ['', '', '', ''])[0],
                '1': question.get('choices', ['', '', '', ''])[1],
                '2': question.get('choices', ['', '', '', ''])[2],
                '3': question.get('choices', ['', '', ''])[3] if len(question.get('choices', [])) > 3 else ''
            },
            'correctIndex': ord(question.get('correct', 'A')) - ord('A'),  # Convert A/B/C/D to 0/1/2/3
            'hint': question.get('hint', ''),
            'explanation': question.get('explanation', '')
        }
    
    # Create initial attempt entry (stores quiz template)
    attempt_data = {
        'createdAt': get_timestamp(),
        'name': name or quizName or f"Quiz: {topic}",
        'quizId': quiz_id,
        'teacherId': teacherId or 'unknown',
        'teacherName': teacherName or 'Unknown Teacher',
        'questions': questions_dict,
        'total': len(questions),
        'trueCount': 0,  # Will be filled when student takes quiz
        'falseCount': 0   # Will be filled when student takes quiz
    }
    
    # Store in quizzes/{quizId}/attempts/{attemptId}
    attempts_ref = db_ref.child('quizzes').child(quiz_id).child('attempts')
    new_attempt_ref = attempts_ref.push(attempt_data)
    attempt_id = new_attempt_ref.key
    
    # Link to teacherQuizzes if teacher provided
    if teacherId:
        db_ref.child('teacherQuizzes').child(teacherId).child(quiz_id).set(True)
        print(f"✓ Linked quiz to teacher: {teacherId}")
    
    # Return data with both quiz_id and attempt_id
    return_data = {
        'id': quiz_id,
        'quiz_id': quiz_id,
        'attempt_id': attempt_id,
        'book_id': book_id,
        'topic': topic,
        'name': attempt_data['name'],
        'n_questions': len(questions),
        'questions': questions,  # Keep original format for API compatibility
        'created_at': attempt_data['createdAt'],
        'teacherId': teacherId,
        'teacherName': teacherName
    }
    
    print(f"✓ Created quiz: {return_data['name']} (Quiz ID: {quiz_id}, Attempt ID: {attempt_id})")
    
    return return_data


def get_quiz(quiz_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a quiz by ID
    Returns the first attempt (template) with converted question format
    """
    db_ref = get_db()
    
    # Get attempts under this quiz
    attempts_data = db_ref.child('quizzes').child(quiz_id).child('attempts').get()
    
    if not attempts_data:
        return None
    
    # Get first attempt (quiz template)
    first_attempt_id = list(attempts_data.keys())[0]
    quiz_data = attempts_data[first_attempt_id]
    
    # Convert questions from nested object to list format for API compatibility
    questions_dict = quiz_data.get('questions', {})
    questions_list = []
    
    for q_key in sorted(questions_dict.keys(), key=lambda x: int(x[1:])):
        q_data = questions_dict[q_key]
        
        choices = [
            q_data.get('options', {}).get('0', ''),
            q_data.get('options', {}).get('1', ''),
            q_data.get('options', {}).get('2', ''),
            q_data.get('options', {}).get('3', '')
        ]
        
        correct_index = q_data.get('correctIndex', 0)
        correct_letter = chr(ord('A') + correct_index)
        
        questions_list.append({
            'question': q_data.get('text', ''),
            'choices': choices,
            'correct': correct_letter,
            'hint': q_data.get('hint', ''),
            'difficulty': q_data.get('difficulty', 'medium'),
            'explanation': q_data.get('explanation', '')
        })
    
    quiz_data['id'] = quiz_id
    quiz_data['quiz_id'] = quiz_data.get('quizId', quiz_id)
    quiz_data['questions'] = questions_list
    quiz_data['n_questions'] = len(questions_list)
    quiz_data['created_at'] = quiz_data.get('createdAt', '')
    
    return quiz_data


def list_quizzes(book_id: str = None) -> List[Dict[str, Any]]:
    """List all quizzes (returns first attempt from each quiz)"""
    db_ref = get_db()
    
    quizzes_data = db_ref.child('quizzes').get()
    
    if not quizzes_data:
        return []
    
    quizzes = []
    for quiz_id, quiz_content in quizzes_data.items():
        attempts = quiz_content.get('attempts', {})
        
        if not attempts:
            continue
        
        # Get first attempt (quiz template)
        first_attempt = list(attempts.values())[0]
        
        quiz_summary = {
            'id': quiz_id,
            'quiz_id': first_attempt.get('quizId', quiz_id),
            'name': first_attempt.get('name', ''),
            'teacherId': first_attempt.get('teacherId', ''),
            'teacherName': first_attempt.get('teacherName', ''),
            'n_questions': first_attempt.get('total', 0),
            'created_at': first_attempt.get('createdAt', ''),
            'total_attempts': len(attempts)
        }
        
        quizzes.append(quiz_summary)
    
    quizzes.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return quizzes


# =============================================================================
# STUDENT OPERATIONS
# =============================================================================

def create_student(external_id: str, name: str, email: str = None) -> Dict[str, Any]:
    """
    Create a new student using external_id as the key
    Schema: students/{external_id}/history/{attemptId}
    """
    db_ref = get_db()
    
    students_ref = db_ref.child('students').child(external_id)
    existing_student = students_ref.get()
    
    if existing_student:
        existing_student['id'] = external_id
        print(f"ℹ️  Student already exists: {external_id}")
        return existing_student
    
    student_data = {
        'external_id': external_id,
        'name': name,
        'email': email,
        'created_at': get_timestamp(),
        'history': {}
    }
    
    students_ref.set(student_data)
    student_data['id'] = external_id
    
    # Also create user entry
    create_user(email=email or f"{external_id}@example.com", name=name, is_teacher=False, user_id=external_id)
    
    print(f"✓ Created student: {name} (ID: {external_id})")
    
    return student_data


def get_student_by_external_id(external_id: str) -> Optional[Dict[str, Any]]:
    """Get student by external ID"""
    db_ref = get_db()
    
    student_data = db_ref.child('students').child(external_id).get()
    
    if student_data:
        student_data['id'] = external_id
        return student_data
    
    return None


# =============================================================================
# STUDENT RESPONSE OPERATIONS
# =============================================================================

def create_student_response(
    student_id: str,
    quiz_id: str,
    question_id: int,
    answer: str,
    is_correct: bool,
    time_ms: int,
    hints_used: int = 0
) -> Dict[str, Any]:
    """Legacy function - kept for compatibility"""
    print("⚠️  Warning: Use record_quiz_attempt for new schema")
    return {}


def record_quiz_attempt(
    student_id: str,
    quiz_id: str,
    quiz_name: str,
    responses: List[Dict[str, Any]],
    student_name: str = "student"
) -> str:
    """
    Record a complete quiz attempt for a student
    Schema: 
      - students/{studentId}/history/{attemptId}
      - quizzes/{quizId}/attempts/{attemptId}
    
    Args:
        student_id: Student's external ID
        quiz_id: Quiz ID
        quiz_name: Name of the quiz
        responses: List of question responses with is_correct
        student_name: Student's name
    
    Returns:
        attempt_id: The generated attempt ID
    """
    db_ref = get_db()
    
    # Calculate statistics
    total = len(responses)
    correct = sum(1 for r in responses if r.get('is_correct', False))
    
    timestamp = get_timestamp()
    
    # Get the quiz template (first attempt with questions)
    quiz_attempts = db_ref.child('quizzes').child(quiz_id).child('attempts').get()
    
    if not quiz_attempts:
        print(f"⚠️  Warning: Quiz {quiz_id} not found")
        return None
    
    # Get questions from template
    template_attempt = list(quiz_attempts.values())[0]
    questions = template_attempt.get('questions', {})
    
    # Create student attempt data
    attempt_data = {
        'quizId': quiz_id,
        'quizName': quiz_name,
        'timestamp': timestamp,
        'total': total,
        'trueCount': correct,
        'falseCount': total - correct
    }
    
    # Add to student's history
    history_ref = db_ref.child('students').child(student_id).child('history')
    new_attempt_ref = history_ref.push(attempt_data)
    attempt_id = new_attempt_ref.key
    
    # Also record in quizzes/{quizId}/attempts/{attemptId}
    quiz_attempt_data = {
        'studentId': student_id,
        'studentName': student_name,
        'timestamp': timestamp,
        'total': total,
        'trueCount': correct,
        'falseCount': total - correct,
        'questions': questions,  # Include questions in student's attempt
        'createdAt': timestamp,
        'name': quiz_name,
        'quizId': quiz_id
    }
    
    quiz_attempt_ref = db_ref.child('quizzes').child(quiz_id).child('attempts').child(attempt_id)
    quiz_attempt_ref.set(quiz_attempt_data)
    
    print(f"✓ Recorded quiz attempt for student {student_id}: {correct}/{total} correct (Attempt ID: {attempt_id})")
    
    return attempt_id


def get_student_responses(student_id: str) -> List[Dict[str, Any]]:
    """Get all quiz attempts for a student from their history"""
    db_ref = get_db()
    
    history_data = db_ref.child('students').child(student_id).child('history').get()
    
    if not history_data:
        return []
    
    responses = []
    for attempt_id, attempt_data in history_data.items():
        attempt_data['id'] = attempt_id
        attempt_data['is_correct'] = attempt_data.get('trueCount', 0) > attempt_data.get('falseCount', 0)
        attempt_data['time_ms'] = 0
        attempt_data['hints_used'] = 0
        
        responses.append(attempt_data)
    
    return responses


def get_student_performance_stats(student_id: str) -> Dict[str, Any]:
    """Calculate performance statistics for a student"""
    responses = get_student_responses(student_id)
    
    if not responses:
        return {
            'total_responses': 0,
            'avg_time_ms': 0,
            'avg_hints': 0,
            'accuracy': 0
        }
    
    total_questions = sum(r.get('total', 0) for r in responses)
    total_correct = sum(r.get('trueCount', 0) for r in responses)
    
    return {
        'total_responses': len(responses),
        'total_questions': total_questions,
        'correct_responses': total_correct,
        'accuracy': round(total_correct / total_questions * 100, 2) if total_questions > 0 else 0,
        'avg_time_ms': 0,
        'avg_hints': 0
    }


# =============================================================================
# STORAGE OPERATIONS
# =============================================================================

def get_storage_bucket():
    """Get Firebase Storage bucket instance"""
    global _storage_bucket
    if _storage_bucket is None:
        initialize_firebase() 
    if _storage_bucket is None:
        raise EnvironmentError("Firebase Storage Bucket is not initialized.")
    return _storage_bucket


def upload_file_to_storage(local_file_path: str, destination_filename: str) -> str:
    """Upload file to Firebase Storage"""
    bucket = get_storage_bucket()
    cloud_path = f"uploads/{destination_filename}"
    blob = bucket.blob(cloud_path)
    
    if not os.path.exists(local_file_path):
        raise FileNotFoundError(f"Local file not found: {local_file_path}")
        
    blob.upload_from_filename(local_file_path)
    print(f"✓ Uploaded file to Firebase Storage: {cloud_path}")
    
    return cloud_path


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def clear_collection(collection_name: str):
    """Clear all data in a collection"""
    db_ref = get_db()
    collection_ref = db_ref.child(collection_name)
    collection_ref.delete()
    print(f"✓ Deleted all data from '{collection_name}'")


def get_database_stats() -> Dict[str, Any]:
    """Get statistics about all collections"""
    db_ref = get_db()
    
    stats = {}
    
    for collection_name in ['books', 'quizzes', 'students', 'teacherQuizzes', 'users']:
        data = db_ref.child(collection_name).get()
        count = len(data) if data else 0
        stats[collection_name] = count
    
    return stats


def create_quiz_from_model_data(quiz_data: Dict[str, Any]) -> Dict[str, Any]:
    """Alias for create_quiz"""
    return create_quiz(**quiz_data)


# Export functions
__all__ = [
    'initialize_firebase',
    'get_db',
    'create_user',
    'get_user',
    'get_user_by_email',
    'list_users',
    'create_book',
    'get_book',
    'list_books',
    'update_book_chunk_count',
    'create_quiz',
    'get_quiz',
    'list_quizzes',
    'create_student',
    'get_student_by_external_id',
    'create_student_response',
    'record_quiz_attempt',
    'get_student_responses',
    'get_student_performance_stats',
    'create_quiz_from_model_data',
    'clear_collection',
    'get_database_stats',
    'upload_file_to_storage',
    'get_storage_bucket'
]


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Firebase Realtime Database Service Test")
    print("="*60)
    
    try:
        initialize_firebase()
        stats = get_database_stats()
        print("\nDatabase Statistics:")
        for collection, count in stats.items():
            print(f"  {collection}: {count} items")
        print("\n✓ Firebase Realtime Database connection successful!")
    except Exception as e:
        print(f"\n✗ Firebase connection failed: {e}")
    
    print("="*60)
