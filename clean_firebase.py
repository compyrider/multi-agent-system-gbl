
import firebase_service as fb
fb.initialize_firebase()
fb.clear_collection('quizzes')
fb.clear_collection('students')
fb.clear_collection('books')
fb.clear_collection('teacherQuizzes')