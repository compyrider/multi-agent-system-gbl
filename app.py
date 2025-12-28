"""
Flask API for Quiz Generation System
Two main endpoints:
1. POST /api/quiz/generate - Upload PDF, process, generate validated quiz
2. POST /api/quiz/adaptive - Generate adaptive quiz based on student performance

INTEGRATED: Works with SSL/TLS fixes for Render deployment
"""

import os
import asyncio
import sys
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS
import tempfile
from functools import wraps
# import chroma_service
# With:
from chroma_service import check_chunks_exist, get_collection_stats, initialize_chroma

# agents
from agents import (
    run_curriculum_agent,
    run_quiz_generator_agent,
    run_quiz_validator_agent,
    run_adaptive_agent
)
from pdf_utils import extract_text_from_pdf, get_pdf_info, validate_extracted_text
from models_firebase import Book, Quiz, Student, StudentResponse
from chroma_service import check_chunks_exist, get_collection_stats
import firebase_service as fb

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'pdf'}

print("\n" + "="*70)
print("🚀 Quiz Generation API - Initializing")
print("="*70)

# ============================================================================
# FIREBASE INITIALIZATION (With SSL Fix)
# ============================================================================

print("\n📡 Initializing Firebase with SSL/TLS configuration...")
try:
    fb.initialize_firebase()
    print("✓ Firebase initialized successfully with SSL/TLS support")
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    print("⚠️ Application may not function without Firebase connection")
    sys.exit(1)

print("\n" + "="*70 + "\n")


# And add this to your app initialization block:
try:
    initialize_chroma()
except Exception as e:
    print(f"FATAL: ChromaDB initialization failed: {e}")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def async_route(f):
    """Decorator to run async functions in Flask routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return decorated_function


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.route('/', methods=['GET'])
def root():
    """Root endpoint - shows available routes"""
    return jsonify({
        'message': 'Quiz Generation API',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'generate_quiz': '/api/quiz/generate (POST)',
            'adaptive_quiz': '/api/quiz/adaptive (POST)',
            'list_books': '/api/books (GET)',
            'list_quizzes': '/api/quizzes (GET)',
            'stats': '/api/stats (GET)'
        }
    }), 200


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render"""
    try:
        # Check Firebase connection
        stats = fb.get_database_stats()
        
        # Check ChromaDB connection
        chroma_stats = get_collection_stats()
        
        # Check Firebase Storage configuration
        storage_configured = bool(os.getenv('FIREBASE_STORAGE_BUCKET'))
        
        return jsonify({
            'status': 'healthy',
            'firebase': {
                'connected': True,
                'collections': stats,
                'storage_configured': storage_configured,
                'database_url': os.getenv('FIREBASE_DATABASE_URL', 'Not set')[:50] + '...'
            },
            'chromadb': {
                'connected': True,
                'total_chunks': chroma_stats.get('total_chunks', 0)
            }
        }), 200
    
    except Exception as e:
        print(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503


# ============================================================================
# ENDPOINT 1: GENERATE QUIZ FROM PDF
# ============================================================================

@app.route('/api/quiz/generate', methods=['POST'])
@async_route
async def generate_quiz():
    """
    Upload PDF, process with curriculum agent, generate and validate quiz
    
    Request:
        - file: PDF file (multipart/form-data)
        - topic: Quiz topic (form field)
        - n_questions: Number of questions (optional, default=10)
        - book_title: Book title (optional)
        - book_author: Book author (optional)
        - teacher_id: Teacher ID (REQUIRED)
        - teacher_name: Teacher Name (REQUIRED)
    """
    try:
        # Validate request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        # Get parameters
        topic = request.form.get('topic')
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        n_questions = int(request.form.get('n_questions', 10))
        book_title = request.form.get('book_title', file.filename)
        book_author = request.form.get('book_author', 'Unknown')
        
        teacher_id = request.form.get('teacher_id', 'uploaded_pdf_agent_id')
        teacher_name = request.form.get('teacher_name', 'PDF Quiz Creator')
        
        # Validate parameters
        if n_questions < 1 or n_questions > 50:
            return jsonify({'error': 'n_questions must be between 1 and 50'}), 400
        
        print(f"\n{'='*60}")
        print(f"Processing PDF: {file.filename}")
        print(f"Topic: {topic}")
        print(f"Questions: {n_questions}")
        print(f"{'='*60}\n")
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)
        
        try:
            # Step 1: Extract text from PDF
            print("📄 Step 1: Extracting text from PDF...")
            pdf_info = get_pdf_info(temp_path)
            text = extract_text_from_pdf(temp_path)
            
            if not validate_extracted_text(text):
                return jsonify({
                    'error': 'Failed to extract valid text from PDF. File may be corrupted or empty.'
                }), 400
            
            print(f"✓ Extracted {len(text)} characters from {pdf_info.get('page_count', 'unknown')} pages")

            # Step 1.5: Handle Firebase Storage Upload (Conditional)
            storage_url = filename
            storage_bucket_env = os.getenv('FIREBASE_STORAGE_BUCKET')
            
            if storage_bucket_env:
                print("\n☁️ Step 1.5: Uploading file to Firebase Storage...")
                print(f"   Storage Bucket: {storage_bucket_env}")
                try:
                    storage_url = fb.upload_file_to_storage(temp_path, filename)
                    print(f"✓ File uploaded successfully to Firebase Storage: {storage_url}")
                except Exception as storage_error:
                    print(f"⚠️ Warning: Firebase Storage upload failed: {storage_error}")
                    print(f"   Proceeding with local filename as path: {filename}")
                    storage_url = filename
            else:
                print("\nℹ️ Firebase Storage Bucket not configured in environment")
                print(f"   Storing local filename as file path: {filename}")
            
            # Step 2: Create book record in Firebase
            print("\n📚 Step 2: Creating book record...")
            book = Book.create(
                title=book_title,
                author=book_author,
                file_path=storage_url
            )
            book_id = book['id']
            print(f"✓ Created book with ID: {book_id}")
            print(f"   File path stored: {storage_url}")
            
            # Step 3: Check if chunks already exist
            existing_chunks = check_chunks_exist(book_id)
            
            if existing_chunks > 0:
                print(f"\nℹ️ Found {existing_chunks} existing chunks for this book")
                print("   Skipping curriculum processing...")
                
                Book.update_chunk_count(book_id, existing_chunks)
                
                curriculum_result = {
                    'inserted_chunks': existing_chunks,
                    'skipped': True
                }
            else:
                # Step 4: Run Curriculum Agent
                print("\n🧠 Step 3: Running Curriculum Agent...")
                print("   This may take several minutes for large PDFs...")
                
                curriculum_result = await run_curriculum_agent(
                    book_id=book_id,
                    text=text,
                    chunk_size=2000
                )
                
                print(f"✓ Processed {curriculum_result['inserted_chunks']} chunks")
                
                print(f"💾 Updating book record with chunk count...")
                Book.update_chunk_count(book_id, curriculum_result['inserted_chunks'])
                print(f"✓ Book record updated: {curriculum_result['inserted_chunks']} chunks")
            
            # Step 5: Run Quiz Generator Agent
            print(f"\n❓ Step 4: Generating {n_questions} quiz questions...")
            quiz_result = await run_quiz_generator_agent(
                book_id=book_id,
                topic=topic,
                n_questions=n_questions
            )
            
            questions = quiz_result['questions']
            print(f"✓ Generated {len(questions)} questions")
            
            # Step 6: Run Quiz Validator Agent
            print("\n✅ Step 5: Validating quiz questions...")
            validation_result = await run_quiz_validator_agent(
                quiz_id=None, 
                questions=questions,
                topic=topic,
                auto_fix=True
            )
            
            print(f"✓ Validation complete:")
            print(f"   - Valid: {validation_result['valid_count']}")
            print(f"   - Invalid: {validation_result['invalid_count']}")
            print(f"   - Fixed: {validation_result['fixed_count']}")
            
            # Step 7: Use fixed questions if available
            final_questions = []
            for result in validation_result['validation_results']:
                if result.get('fixed_question'):
                    final_questions.append(result['fixed_question'])
                elif result['validation']['valid']:
                    final_questions.append(result['question'])
            
            if len(final_questions) < n_questions:
                for result in validation_result['validation_results']:
                    if len(final_questions) >= n_questions:
                        break
                    if not result['validation']['valid'] and not result.get('fixed_question'):
                        final_questions.append(result['question'])
            
            # Step 8: Save quiz to Firebase
            print("\n💾 Step 6: Saving quiz to Firebase...")
            
            quiz_record = Quiz.create(
                name=book_title,
                teacherId=teacher_id,
                teacherName=teacher_name,
                questions_json=final_questions,
                book_id=book_id,
                topic=topic,
                metadata={
                    'n_questions_requested': n_questions,
                    'n_questions_generated': len(final_questions),
                    'chunks_used': quiz_result.get('chunks_used', 0),
                    'validation_summary': {
                        'valid': validation_result['valid_count'],
                        'invalid': validation_result['invalid_count'],
                        'fixed': validation_result['fixed_count']
                    },
                    'storage_type': 'firebase_storage' if storage_bucket_env else 'local_filename'
                }
            )
            
            print(f"✓ Quiz saved with ID: {quiz_record['id']}")
            print(f"\n{'='*60}")
            print("✅ PIPELINE COMPLETE!")
            print(f"{'='*60}\n")
            
            # Return response
            return jsonify({
                'success': True,
                'book_id': book_id,
                'quiz_id': quiz_record['id'],
                'topic': topic,
                'n_questions': len(final_questions),
                'questions': final_questions,
                'validation': {
                    'total': validation_result['total_questions'],
                    'valid': validation_result['valid_count'],
                    'invalid': validation_result['invalid_count'],
                    'fixed': validation_result['fixed_count']
                },
                'metadata': {
                    'book_title': book_title,
                    'book_author': book_author,
                    'pdf_pages': pdf_info.get('page_count'),
                    'text_length': len(text),
                    'chunks_created': curriculum_result['inserted_chunks'],
                    'chunks_used': quiz_result.get('chunks_used', 0),
                    'file_storage': 'firebase_storage' if storage_bucket_env else 'local_filename',
                    'file_path': storage_url
                }
            }), 200
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                print(f"🗑️ Cleaned up temporary file: {filename}")
    
    except Exception as e:
        print(f"\n❌ Error in generate_quiz: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# ENDPOINT 2: GENERATE ADAPTIVE QUIZ
# ============================================================================

@app.route('/api/quiz/adaptive', methods=['POST'])
@async_route
async def generate_adaptive_quiz():
    """Generate adaptive quiz based on student performance"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        student_external_id = data.get('student_id')
        book_id = data.get('book_id')
        topic = data.get('topic')
        
        if not all([student_external_id, book_id, topic]):
            return jsonify({
                'error': 'student_id, book_id, and topic are required'
            }), 400
        
        n_questions = data.get('n_questions', 10)
        student_responses_data = data.get('student_responses', [])
        
        teacher_id = data.get('teacher_id', 'adaptive_agent')
        teacher_name = data.get('teacher_name', 'Adaptive System')
        quiz_name = data.get('quiz_name', f"Adaptive Quiz: {topic} ({student_external_id})")
        
        if n_questions < 1 or n_questions > 50:
            return jsonify({'error': 'n_questions must be between 1 and 50'}), 400
        
        print(f"\n{'='*60}")
        print(f"Generating Adaptive Quiz")
        print(f"Student: {student_external_id}")
        print(f"Book ID: {book_id}")
        print(f"Topic: {topic}")
        print(f"{'='*60}\n")
        
        print("👤 Step 1: Looking up student...")
        student = Student.find_by_external_id(student_external_id)
        
        if not student:
            print(f"   Creating new student: {student_external_id}")
            student = Student.create(
                external_id=student_external_id,
                name=data.get('student_name', f'Student {student_external_id}'),
                email=data.get('student_email')
            )
        
        student_id = student['id']
        print(f"✓ Student ID: {student_id}")
        
        if student_responses_data:
            print(f"\n📝 Step 2: Saving {len(student_responses_data)} student responses...")
            for response_data in student_responses_data:
                try:
                    StudentResponse.create(
                        student_id=student_id,
                        quiz_id=response_data.get('quiz_id', 'unknown'),
                        question_id=response_data.get('question_id', 0),
                        answer=response_data.get('answer', ''),
                        is_correct=response_data.get('is_correct', False),
                        time_ms=response_data.get('time_ms', 0),
                        hints_used=response_data.get('hints_used', 0)
                    )
                except Exception as e:
                    print(f"   ⚠️ Warning: Could not save response: {e}")
            
            print("✓ Student responses saved")
        
        print(f"\n🎯 Step 3: Running Adaptive Agent...")
        adaptive_result = await run_adaptive_agent(
            student_external_id=student_external_id,
            book_id=book_id,
            topic=topic,
            n_questions=n_questions
        )
        
        questions = adaptive_result['questions']
        difficulty_hint = adaptive_result['difficulty_hint']
        performance = adaptive_result['performance_metrics']
        
        print(f"✓ Generated {len(questions)} adaptive quiz questions")
        print(f"   Difficulty adjustment: {difficulty_hint}")
        print(f"   Performance - Time: {performance['avg_time_ms']}ms, Hints: {performance['avg_hints']}")
        
        print("\n💾 Step 4: Saving adaptive quiz to Firebase...")
        
        quiz_record = Quiz.create(
            name=quiz_name,
            teacherId=teacher_id,
            teacherName=teacher_name,
            questions_json=questions,
            book_id=book_id,
            topic=topic,
            metadata={
                'quiz_type': 'adaptive',
                'student_id': student_id,
                'student_external_id': student_external_id,
                'difficulty_adjustment': difficulty_hint,
                'performance_metrics': performance,
                'n_questions': len(questions)
            }
        )
        
        print(f"✓ Adaptive quiz saved with ID: {quiz_record['id']}")
        print(f"\n{'='*60}")
        print("✅ ADAPTIVE QUIZ GENERATION COMPLETE!")
        print(f"{'='*60}\n")
        
        return jsonify({
            'success': True,
            'quiz_id': quiz_record['id'],
            'student_id': student_external_id,
            'student_firebase_id': student_id,
            'book_id': book_id,
            'topic': topic,
            'difficulty_adjustment': difficulty_hint,
            'performance_metrics': performance,
            'n_questions': len(questions),
            'questions': questions,
            'metadata': {
                'quiz_type': 'adaptive',
                'created_at': quiz_record.get('created_at')
            }
        }), 200
    
    except Exception as e:
        print(f"\n❌ Error in generate_adaptive_quiz: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# HELPER ENDPOINTS
# ============================================================================

@app.route('/api/books', methods=['GET'])
def list_books():
    """List all books in the database"""
    try:
        books = Book.list_all()
        return jsonify({
            'success': True,
            'count': len(books),
            'books': books
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/books/<book_id>', methods=['GET'])
def get_book(book_id):
    """Get a specific book"""
    try:
        book = Book.get(book_id)
        if not book:
            return jsonify({'error': 'Book not found'}), 404
        
        return jsonify({
            'success': True,
            'book': book
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/quizzes', methods=['GET'])
def list_quizzes():
    """List all quizzes, optionally filtered by book_id"""
    try:
        book_id = request.args.get('book_id')
        quizzes = Quiz.list_by_book(book_id) if book_id else fb.list_quizzes()
        
        return jsonify({
            'success': True,
            'count': len(quizzes),
            'quizzes': quizzes
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/quizzes/<quiz_id>', methods=['GET'])
def get_quiz(quiz_id):
    """Get a specific quiz"""
    try:
        quiz = Quiz.get(quiz_id)
        if not quiz:
            return jsonify({'error': 'Quiz not found'}), 404
        
        return jsonify({
            'success': True,
            'quiz': quiz
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database and chroma collection statistics"""
    try:
        db_stats = fb.get_database_stats()
        chroma_stats = chroma_service.get_collection_stats()
        
        stats = {
            'success': True,
            'database': db_stats,
            'chromadb': chroma_stats
        }
        
        return jsonify(stats), 200

    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/students/<student_external_id>/performance', methods=['GET'])
def get_student_performance(student_external_id):
    """Get student performance statistics"""
    try:
        student = Student.find_by_external_id(student_external_id)
        
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        stats = StudentResponse.get_performance_stats(student['id'])
        
        return jsonify({
            'success': True,
            'student_id': student_external_id,
            'performance': stats
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return jsonify({
        'error': 'File too large. Maximum size is 50MB.'
    }), 413


@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors"""
    return jsonify({
        'error': 'Internal server error. Please try again later.'
    }), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug = os.environ.get('FLASK_ENV') == 'production'
    
    print("\n" + "="*70)
    print("🚀 Quiz Generation API Server")
    print("="*70)
    print(f"Port: {port}")
    print(f"Debug mode: {debug}")
    
    storage_configured = bool(os.getenv('FIREBASE_STORAGE_BUCKET'))
    print(f"Firebase Storage: {'Configured ✓' if storage_configured else 'Not Configured (using local paths)'}")
    
    print("\nAvailable Endpoints:")
    print("  GET  /              - API info")
    print("  GET  /health        - Health check")
    print("  POST /api/quiz/generate    - Generate quiz from PDF")
    print("  POST /api/quiz/adaptive    - Generate adaptive quiz")
    print("  GET  /api/stats     - Get database and ChromaDB statistics")
    print("  GET  /api/books     - List all books")
    print("  GET  /api/quizzes   - List all quizzes")
    print("  GET  /api/students/{id}/performance - Get student stats")
    print("="*70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)


