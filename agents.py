"""
Agent orchestration and prompt templates for Curriculum -> Quiz -> Validator -> Adaptive
OPTIMIZED VERSION: Handles large PDFs efficiently
FIXED: Added explanation field to all quiz questions
"""


"""
Zwei Versionen:

ORIGINAL-Prompt:

SYSTEM:
You are a strict quiz-generation assistant. Use only the context provided.

USER:
Generate {n_questions} high-quality multiple-choice questions about the TOPIC: "{topic}".
You MUST base all content only on the CONTEXT and not invent facts.
For each question return an object with fields:
- question (string)
- choices (array of 4 strings labelled A-D order)
- correct (one of "A","B","C","D")
- explanation (string): A clear explanation of why the correct answer is right, based on the context
- hint (short sentence grounded in context)
- difficulty ("easy"|"medium"|"hard")

Return a JSON array of questions only. Provide no extra commentary outside the JSON.

CONTEXT:
{retrieved_chunks}

Version 1 (OLD):

SYSTEM:
You are a quiz-generation assistant. Use the context provided as your primary source.

USER:
Generate {n_questions} multiple-choice questions about the TOPIC: "{topic}".
Base your answers primarily on the CONTEXT below.
For each question return an object with fields:
- question
- choices (A-D)
- correct
- explanation (based on the context)
- hint
- difficulty

Return a JSON array only.

CONTEXT:
{retrieved_chunks}

VERSION 2 (OLD):

SYSTEM:
You are a strict quiz-generation assistant for educational games.
Use only the context provided.

USER:
Generate {n_questions} didactically appropriate multiple-choice questions for children.
The questions should be clearly worded, age-appropriate, and suitable for game-based learning.
You MUST base all content only on the CONTEXT and not invent facts.

For each question return:
- question
- choices (A-D)
- correct
- explanation (based on the context)
- hint
- difficulty

Return a JSON array only.

CONTEXT:
{retrieved_chunks}

"""

import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4
from openai import OpenAI
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Import your services
try:
    from chroma_service import add_chunks, query as chroma_query
    from models_firebase import Book, Chunk, Quiz, Student, StudentResponse, db_session
except ImportError:
    print("WARNING: chroma_service or models not found. Some functions may not work.")
    async def add_chunks(book_id, chunks): pass
    async def chroma_query(topic, n_results): return {"documents": [], "metadatas": []}
    db_session = None

# Check for OpenAI API key
if not os.getenv('OPENAI_API_KEY'):
    print('WARNING: OPENAI_API_KEY not set. Agents will not function until it is provided.')

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Output directory for JSON logs
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def save_agent_output(agent_name: str, output_data: Dict[str, Any]) -> str:
    """Save agent output to a JSON file with timestamp."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{agent_name}_output_{timestamp}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    output = {
        "agent": agent_name,
        "timestamp": datetime.now().isoformat(),
        "data": output_data
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Agent output saved to: {filename}")
    return filepath


async def call_openai(
    prompt: str | List[Dict[str, str]],
    model: str = 'gpt-4o-mini',
    max_tokens: int = 1200,
    temperature: float = 0.0
) -> str:
    """
    Helper: call OpenAI Chat Completions API with retry + simple error handling
    """
    try:
        messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": str(prompt)}]
        
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        output_text = response.choices[0].message.content or ''
        return output_text
    
    except Exception as err:
        print(f'OpenAI call failed: {err}')
        raise err


async def run_curriculum_agent(
    book_id: int,
    text: str,
    chunk_size: int = 2000
) -> Dict[str, Any]:
    """
    Curriculum Agent - OPTIMIZED VERSION
    - Process large PDFs efficiently using parallel batch processing
    - No artificial chunk limits - processes entire document
    """
    if not text or not book_id:
        raise ValueError('book_id and text are required')
    
    print(f"📊 Text length: {len(text):,} characters")
    
    # Simple chunking by paragraphs
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    chunks = []
    current = ''
    position = 0
    
    for para in paragraphs:
        combined = f"{current}\n\n{para}" if current else para
        if len(combined) > chunk_size and current:
            chunks.append({"position": position, "text": current})
            position += 1
            current = para
        else:
            current = combined
    
    if current:
        chunks.append({"position": position, "text": current})
    
    print(f"📦 Processing {len(chunks)} chunks...")
    
    # NEW: Batch processing - process chunks in parallel
    db_chunks = []
    batch_size = 3  # Process 5 chunks at a time
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        print(f"   Processing batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}...")
        
        # Process batch in parallel
        tasks = [process_single_chunk(chunk, book_id) for chunk in batch]
        batch_results = await asyncio.gather(*tasks)
        
        db_chunks.extend(batch_results)
    
    # Add to Chroma
    print(f"💾 Storing {len(db_chunks)} chunks in ChromaDB...")
    await asyncio.to_thread(add_chunks, book_id, db_chunks)
    
    result = {
        "book_id": book_id,
        "inserted_chunks": len(db_chunks),
        "chunks_summary": [
            {
                "position": c["metadata"]["position"],
                "summary": c["metadata"]["summary"][:100] + "...",
                "key_concepts": c["metadata"]["key_concepts"]
            }
            for c in db_chunks[:10]  # Only show first 10 in summary
        ]
    }
    
    # Save output to JSON file
    save_agent_output("curriculum_agent", result)
    
    return result


async def process_single_chunk(chunk: Dict[str, Any], book_id: int) -> Dict[str, Any]:
    """
    Process a single chunk - extract summary and keywords
    OPTIMIZED: Simpler prompt for faster processing
    """
    short_context = chunk['text'][:3000] if len(chunk['text']) > 3000 else chunk['text']
    
    # OPTIMIZED: Simpler, faster prompt
    summarization_prompt = [
        {"role": "system", "content": "Extract key information concisely."},
        {
            "role": "user",
            "content": (
                f"From this text, extract:\n"
                f"1. A 2-sentence summary\n"
                f"2. 3 key concepts (comma-separated)\n"
                f"3. 5 keywords (comma-separated)\n\n"
                f"TEXT: {short_context}\n\n"
                f"Respond in JSON: {{\"summary\": \"...\", \"key_concepts\": \"...\", \"keywords\": \"...\"}}"
            )
        }
    ]
    
    try:
        raw = await call_openai(summarization_prompt, max_tokens=200)
        
        # Parse JSON response
        parsed = None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            j_start = raw.find('{')
            j_end = raw.rfind('}') + 1
            if j_start >= 0 and j_end > j_start:
                try:
                    parsed = json.loads(raw[j_start:j_end])
                except json.JSONDecodeError:
                    pass
        
        if parsed:
            summary = parsed.get('summary', raw[:200])
            key_concepts = parsed.get('key_concepts', '')
            keywords = parsed.get('keywords', '')
        else:
            summary = raw[:200]
            key_concepts = ''
            keywords = ''
        
        # Ensure strings for ChromaDB
        chunk_id = f"{book_id}-{chunk['position']}"
        
        return {
            "id": chunk_id,
            "text": chunk['text'],
            "metadata": {
                "bookId": book_id,
                "position": chunk['position'],
                "summary": summary,
                "key_concepts": key_concepts,
                "keywords": keywords
            }
        }
    
    except Exception as e:
        print(f"⚠️ Error processing chunk {chunk['position']}: {e}")
        # Return chunk with minimal metadata
        chunk_id = f"{book_id}-{chunk['position']}"
        return {
            "id": chunk_id,
            "text": chunk['text'],
            "metadata": {
                "bookId": book_id,
                "position": chunk['position'],
                "summary": chunk['text'][:200],
                "key_concepts": "",
                "keywords": ""
            }
        }


async def get_relevant_context(topic: str, n_results: int = 6) -> str:
    """
    Vector Retrieval Helper
    - Uses chroma_query to fetch top-K document texts with metadata
    """
    resp = await asyncio.to_thread(chroma_query, topic, n_results)
    
    docs = resp.get('documents', resp.get('results', []))
    metadatas = resp.get('metadatas', [])
    
    context_parts = []
    for i, doc in enumerate(docs):
        doc_str = doc if isinstance(doc, str) else json.dumps(doc)
        meta = metadatas[i] if i < len(metadatas) else {}
        
        context_parts.append(
            f"--- CHUNK {i + 1} (bookId={meta.get('bookId', 'unknown')}, "
            f"pos={meta.get('position', 'n/a')}) ---\n{doc_str}"
        )
    
    return '\n\n'.join(context_parts)


async def run_quiz_generator_agent(
    book_id: int,
    topic: str,
    n_questions: int = 10
) -> Dict[str, Any]:
    """
    Quiz Generator Agent - FIXED VERSION
    - Using ONLY retrieved context, generate N questions with choices + hints + difficulty
    - NOW INCLUDES 'explanation' field
    """
    if not book_id or not topic:
        raise ValueError('book_id and topic required')
    
    print(f"\n🔍 Searching ChromaDB for relevant chunks...")
    print(f"   Topic: {topic}")
    print(f"   Book ID: {book_id}")
    
    # Query ChromaDB with book filter
    context_data = await asyncio.to_thread(chroma_query, topic, 6)
    
    # Filter by book_id
    docs = context_data.get('documents', [])
    metadatas = context_data.get('metadatas', [])
    distances = context_data.get('distances', [])
    
    # Filter chunks that belong to this book
    relevant_chunks = []
    for i, (doc, meta) in enumerate(zip(docs, metadatas)):
        if meta.get('bookId') == book_id:
            relevant_chunks.append((doc, meta, distances[i] if i < len(distances) else None))
    
    if not relevant_chunks:
        print(f"⚠️ No chunks found for book_id={book_id}, using all results")
        relevant_chunks = [(doc, meta, distances[i] if i < len(distances) else None) 
                          for i, (doc, meta) in enumerate(zip(docs, metadatas))]
    
    print(f"✓ Retrieved {len(relevant_chunks)} relevant chunks from ChromaDB")
    
    # Build context from retrieved chunks
    context_parts = []
    for i, (doc, meta, dist) in enumerate(relevant_chunks, 1):
        if dist is not None:
            relevance_display = f"{1 - dist:.3f}"
        else:
            relevance_display = 'N/A'
            
        context_parts.append(
            f"--- CHUNK {i} (position={meta.get('position', 'n/a')}, "
            f"relevance={relevance_display}) ---\n{doc}"
        )
    
    context = '\n\n'.join(context_parts)
    
    # FIXED PROMPT: Now explicitly asks for 'explanation' field
    prompt = [
        {"role": "system", "content": "You are a strict quiz-generation assistant. Use only the context provided."},
        {
            "role": "user",
            "content": (
                f'Generate {n_questions} high-quality multiple-choice questions about the TOPIC: "{topic}". '
                'You MUST base all content only on the CONTEXT and not invent facts. For each question return an object with fields:\n'
                '- question (string): The question text\n'
                '- choices (array of 4 strings labelled A-D order)\n'
                '- correct (one of "A","B","C","D"): The correct answer\n'
                '- explanation (string): A clear explanation of why the correct answer is right, based on the context\n'
                '- hint (short sentence grounded in context)\n'
                '- difficulty ("easy"|"medium"|"hard")\n\n'
                'Return a JSON array of questions only. Provide no extra commentary outside the JSON.'
            )
        },
        {"role": "user", "content": f"CONTEXT:\n{context[:16000]}"}
    ]
    
    print(f"\n🤖 Generating {n_questions} quiz questions with AI...")
    raw = await call_openai(prompt, max_tokens=2000, temperature=0.0)  # FIXED: Increased tokens
    
    # Parse questions
    try:
        questions = json.loads(raw)
    except json.JSONDecodeError:
        a_start = raw.find('[')
        a_end = raw.rfind(']') + 1
        if a_start >= 0 and a_end > a_start:
            questions = json.loads(raw[a_start:a_end])
        else:
            raise ValueError('Could not parse quiz generator output as JSON')
    
    # FIXED: Validate and ensure all questions have required fields
    for q in questions:
        if 'explanation' not in q or not q['explanation']:
            q['explanation'] = f"Based on the context, {q.get('correct', 'A')} is the correct answer."
    
    quiz_id = str(uuid4())
    
    result = {
        "quiz_id": quiz_id,
        "book_id": book_id,
        "topic": topic,
        "n_questions": len(questions),
        "chunks_used": len(relevant_chunks),
        "questions": questions,
        "model_raw_output": raw,
        "retrieved_chunks_info": [
            {
                "position": meta.get('position'),
                "summary": meta.get('summary', '')[:100] + "...",
                "relevance_score": 1 - dist if dist else None
            }
            for _, meta, dist in relevant_chunks
        ]
    }
    
    print(f"✓ Generated {len(questions)} questions based on {len(relevant_chunks)} chunks")
    
    # Save output to JSON file
    save_agent_output("quiz_generator_agent", result)
    
    return result


async def run_quiz_validator_agent(
    quiz_id: str,
    questions: List[Dict[str, Any]],
    topic: str,
    auto_fix: bool = True
) -> Dict[str, Any]:
    """
    Quiz Validator Agent
    - For each question, validate alignment with context and optionally auto-fix
    """
    context = await get_relevant_context(topic, 8)
    
    results = []
    
    for q in questions:
        prompt = [
            {"role": "system", "content": "You are a fact-checking validator. Only verify if the QUESTION is supported by the CONTEXT."},
            {
                "role": "user",
                "content": (
                    f"Given QUESTION and CHOICES, answer with JSON {{ valid: boolean, reason: string }}.\n"
                    f"QUESTION: {json.dumps(q)}\n\nCONTEXT:\n{context[:8000]}"
                )
            }
        ]
        
        raw = await call_openai(prompt, temperature=0.0, max_tokens=400)
        
        validation = {"valid": False, "reason": "validation parsing failed"}
        try:
            validation = json.loads(raw)
        except json.JSONDecodeError:
            # Heuristic detection
            validation['valid'] = bool(re.search(r'\btrue\b', raw, re.I)) and not bool(re.search(r'\bfalse\b', raw, re.I))
            validation['reason'] = raw[:300]
        
        fixed_question = None
        if not validation['valid'] and auto_fix:
            fix_prompt = [
                {"role": "system", "content": "You are a quiz fixer. Regenerate a single question strictly from CONTEXT."},
                {
                    "role": "user",
                    "content": (
                        f"Original question: {json.dumps(q)}\n\n"
                        f"CONTEXT:\n{context[:8000]}\n\n"
                        "Return a single JSON object with same fields: question, choices(A-D array), correct(A-D), explanation, hint, difficulty."
                    )
                }
            ]
            
            raw_fix = await call_openai(fix_prompt, temperature=0.0, max_tokens=500)
            try:
                fixed_question = json.loads(raw_fix)
            except json.JSONDecodeError:
                fixed_question = None
        
        results.append({
            "question": q,
            "validation": validation,
            "fixed_question": fixed_question
        })
    
    result = {
        "quiz_id": quiz_id,
        "total_questions": len(questions),
        "valid_count": sum(1 for r in results if r['validation']['valid']),
        "invalid_count": sum(1 for r in results if not r['validation']['valid']),
        "fixed_count": sum(1 for r in results if r['fixed_question'] is not None),
        "validation_results": results
    }
    
    # Save output to JSON file
    save_agent_output("quiz_validator_agent", result)
    
    return result


async def run_adaptive_agent(
    student_external_id: str,
    book_id: int,
    topic: str,
    n_questions: int = 10
) -> Dict[str, Any]:
    """
    Adaptive Agent - FIXED VERSION
    - Use student history to suggest difficulty modifier and regenerate quiz
    - NOW INCLUDES 'explanation' field
    """
    # Fetch student from database
    student = Student.find_by_external_id(student_external_id)
    
    if not student:
        # If student doesn't exist, use default/neutral difficulty
        avg_time = 20000
        avg_hints = 0.5
        history = []
    else:
        # Fetch student's response history from database
        history = StudentResponse.find_by_student(student['id'])
        
        if history:
            avg_time = sum(r.get('time_ms', 0) for r in history) / len(history)
            avg_hints = sum(r.get('hints_used', 0) for r in history) / len(history)
        else:
            # No history yet, use neutral values
            avg_time = 20000
            avg_hints = 0.5
    
    # Assess student performance
    if avg_time < 15000 and avg_hints < 0.5:
        difficulty_hint = 'increase difficulty'
    elif avg_time > 30000 or avg_hints > 1.0:
        difficulty_hint = 'decrease difficulty'
    else:
        difficulty_hint = 'maintain difficulty'
    
    context = await get_relevant_context(topic, 6)
    modifier = f"Student performance summary: avg_time_ms={round(avg_time)}, avg_hints={avg_hints:.2f}. Instruction: {difficulty_hint}."
    
    # FIXED PROMPT: Now explicitly asks for 'explanation' field
    prompt = [
        {"role": "system", "content": "You are a quiz generator that adapts to student performance."},
        {
            "role": "user",
            "content": (
                f'Generate {n_questions} questions for topic "{topic}". '
                f'Use only the CONTEXT. Adjust difficulty according to: {modifier}. '
                'For each question include:\n'
                '- question (string): The question text\n'
                '- choices (array of 4 strings labelled A-D)\n'
                '- correct (one of "A","B","C","D"): The correct answer\n'
                '- explanation (string): A clear explanation of why the correct answer is right\n'
                '- hint (string): A helpful hint\n'
                '- difficulty (string): "easy", "medium", or "hard"\n\n'
                'Return a JSON array of question objects only.'
            )
        },
        {"role": "user", "content": f"CONTEXT:\n{context[:12000]}"}
    ]
    
    raw = await call_openai(prompt, max_tokens=2000, temperature=0.0)  # FIXED: Increased tokens
    
    try:
        questions = json.loads(raw)
    except json.JSONDecodeError:
        a_start = raw.find('[')
        a_end = raw.rfind(']') + 1
        if a_start >= 0 and a_end > a_start:
            questions = json.loads(raw[a_start:a_end])
        else:
            raise ValueError('Could not parse adaptive generator output')
    
    # FIXED: Validate and ensure all questions have required fields
    for q in questions:
        # Ensure explanation exists
        if 'explanation' not in q or not q['explanation']:
            q['explanation'] = f"Based on the context, {q.get('correct', 'A')} is the correct answer."
        
        # Ensure choices is a proper array
        if 'choices' not in q or not isinstance(q['choices'], list):
            q['choices'] = ['Option A', 'Option B', 'Option C', 'Option D']
    
    quiz_id = str(uuid4())
    
    result = {
        "quiz_id": quiz_id,
        "book_id": book_id,
        "topic": topic,
        "student_external_id": student_external_id,
        "difficulty_hint": difficulty_hint,
        "performance_metrics": {
            "avg_time_ms": round(avg_time),
            "avg_hints": round(avg_hints, 2)
        },
        "n_questions": len(questions),
        "questions": questions,
        "model_raw_output": raw
    }
    
    # Save output to JSON file
    save_agent_output("adaptive_agent", result)
    
    return result


# Export functions
__all__ = [
    'run_curriculum_agent',
    'run_quiz_generator_agent',
    'run_quiz_validator_agent',
    'run_adaptive_agent',
    'get_relevant_context',
    'call_openai'

]
