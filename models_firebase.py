"""
Firebase-backed Database Models
Drop-in replacement for models.py with Firebase Realtime Database backend
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import firebase_service as fb

# Mock db_session for compatibility
db_session = None


class Book:
    """Firebase-backed Book model"""
    
    @staticmethod
    def create(**kwargs):
        """Create a new book"""
        return fb.create_book(
            title=kwargs.get('title'),
            author=kwargs.get('author'),
            file_path=kwargs.get('file_path')
        )
    
    @staticmethod
    def get(book_id: str):
        """Get a book by ID"""
        return fb.get_book(book_id)
    
    @staticmethod
    def list_all():
        """List all books"""
        return fb.list_books()
    
    @staticmethod
    def update_chunk_count(book_id: str, count: int):
        """Update chunk count"""
        fb.update_book_chunk_count(book_id, count)


class Chunk:
    """Chunks are stored in ChromaDB, not Firebase"""
    
    @staticmethod
    def create(**kwargs):
        """Chunks are handled by ChromaDB - this is a no-op"""
        return {
            'id': kwargs.get('id'),
            'book_id': kwargs.get('bookId'),
            'text': kwargs.get('text'),
            'position': kwargs.get('position')
        }


class Quiz:
    """Firebase-backed Quiz model"""
    
    @staticmethod
    def create(**kwargs):
        """Create a new quiz"""
        questions_list = kwargs.get('questions', kwargs.get('questionsJson', kwargs.get('questions_json', [])))
        
        return fb.create_quiz(
            book_id=kwargs.get('book_id', kwargs.get('bookId')),
            topic=kwargs.get('topic'),
            teacherId=kwargs.get('teacherId'),
            teacherName=kwargs.get('teacherName'),
            questions=questions_list,
            name=kwargs.get('name'), 
            nQuestions=kwargs.get('nQuestions'),
            studentId=kwargs.get('studentId'),
            quizName=kwargs.get('quizName'),
            metadata=kwargs.get('metadata', {})
        )
    
    @staticmethod
    def get(quiz_id: str):
        """Get a quiz by ID"""
        return fb.get_quiz(quiz_id)
    
    @staticmethod
    def list_by_book(book_id: str):
        """List quizzes for a specific book"""
        return fb.list_quizzes(book_id=book_id)
    
    @staticmethod
    def create_attempt(quiz_id: str, student_id: str, student_name: str, 
                      answers: Dict[str, Any], false_count: int, 
                      true_count: int, total: int) -> str:
        """Create a quiz attempt"""
        return fb.create_quiz_attempt(
            quiz_id=quiz_id,
            student_id=student_id,
            student_name=student_name,
            answers=answers,
            false_count=false_count,
            true_count=true_count,
            total=total
        )


class Student:
    """Firebase-backed Student model"""
    
    @staticmethod
    def create(**kwargs):
        """Create a new student"""
        external_id = kwargs.get('external_id', kwargs.get('externalId'))
        return fb.create_student(
            external_id=external_id,
            name=kwargs.get('name'),
            email=kwargs.get('email')
        )
    
    @staticmethod
    def find_by_external_id(external_id: str):
        """Find student by external ID"""
        return fb.get_student_by_external_id(external_id)
    
    @staticmethod
    def get_history(student_id: str):
        """Get student's quiz attempt history"""
        return fb.get_student_history(student_id)


class StudentResponse:
    """Firebase-backed StudentResponse model (Legacy compatibility)"""
    
    @staticmethod
    def create(**kwargs):
        """Create a student response (legacy)"""
        return fb.create_student_response(
            student_id=kwargs.get('student_id'),
            quiz_id=kwargs.get('quiz_id'),
            question_id=kwargs.get('question_id'),
            answer=kwargs.get('answer'),
            is_correct=kwargs.get('is_correct'),
            time_ms=kwargs.get('time_ms'),
            hints_used=kwargs.get('hints_used', 0)
        )
    
    @staticmethod
    def find_by_student(student_id: str):
        """Find all responses by a student"""
        return fb.get_student_responses(student_id)
    
    @staticmethod
    def get_performance_stats(student_id: str):
        """Get performance statistics"""
        return fb.get_student_performance_stats(student_id)


def clear_all_data():
    """Clear all Firebase data"""
    print("⚠️  Clearing all Firebase data...")
    
    for collection in ['books', 'quizzes', 'students', 'teacherQuizzes', 'users']:
        fb.clear_collection(collection)
    
    print("✓ Cleared all Firebase collections")


__all__ = [
    'Book',
    'Chunk',
    'Quiz',
    'Student',
    'StudentResponse',
    'clear_all_data',
    'db_session'
]
