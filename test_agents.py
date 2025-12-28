"""
Test script for agent orchestration system
Tests all agents and saves their outputs to JSON files
"""

import asyncio
import os
from agents import (
    run_curriculum_agent,
    run_quiz_generator_agent,
    run_quiz_validator_agent,
    run_adaptive_agent
)


# Sample curriculum text for testing
SAMPLE_TEXT = """
Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It focuses on the development of computer programs that can access data and use it to learn for themselves.

The primary aim is to allow computers to learn automatically without human intervention or assistance and adjust actions accordingly. Machine learning algorithms build a model based on sample data, known as training data, in order to make predictions or decisions without being explicitly programmed to do so.

Types of Machine Learning

There are three main types of machine learning: supervised learning, unsupervised learning, and reinforcement learning.

Supervised learning involves training a model on a labeled dataset, which means that each training example is paired with an output label. The algorithm learns to predict the output from the input data. Common applications include email spam detection and image recognition.

Unsupervised learning works with unlabeled data. The algorithm tries to learn the underlying structure of the data without any guidance. Clustering and dimensionality reduction are common unsupervised learning techniques. Examples include customer segmentation and anomaly detection.

Reinforcement learning is about taking suitable action to maximize reward in a particular situation. It is employed by various software and machines to find the best possible behavior or path it should take in a specific situation. Unlike supervised learning, reinforcement learning doesn't need labeled data. The agent learns from its own experiences.

Applications of Machine Learning

Machine learning has numerous practical applications across various industries. In healthcare, it's used for disease diagnosis, drug discovery, and personalized treatment plans. Financial institutions use machine learning for fraud detection, risk assessment, and algorithmic trading.

In the technology sector, machine learning powers recommendation systems on platforms like Netflix and Amazon, enables natural language processing for virtual assistants like Siri and Alexa, and drives autonomous vehicles.

Retail companies leverage machine learning for demand forecasting, price optimization, and customer behavior analysis. Manufacturing uses it for predictive maintenance and quality control.

Challenges and Future

Despite its potential, machine learning faces several challenges. Data quality and quantity are crucial - algorithms need large amounts of high-quality data to learn effectively. Bias in training data can lead to biased models, raising ethical concerns.

Interpretability is another challenge; many machine learning models, especially deep learning networks, are "black boxes" that make it difficult to understand how they arrive at their decisions.

The future of machine learning looks promising with ongoing research in areas like transfer learning, federated learning, and explainable AI. As computational power increases and algorithms improve, machine learning will continue to transform industries and daily life.
"""


async def test_curriculum_agent():
    """Test the Curriculum Agent"""
    print("\n" + "="*60)
    print("Testing Curriculum Agent")
    print("="*60)
    
    try:
        result = await run_curriculum_agent(
            book_id=1,
            text=SAMPLE_TEXT,
            chunk_size=1000
        )
        
        print(f"✓ Successfully processed {result['inserted_chunks']} chunks")
        print(f"✓ Output saved to JSON file")
        
        return result
    
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


async def test_quiz_generator_agent():
    """Test the Quiz Generator Agent"""
    print("\n" + "="*60)
    print("Testing Quiz Generator Agent")
    print("="*60)
    
    try:
        result = await run_quiz_generator_agent(
            book_id=1,
            topic="machine learning basics",
            n_questions=5
        )
        
        print(f"✓ Generated quiz with ID: {result['quiz_id']}")
        print(f"✓ Number of questions: {result['n_questions']}")
        print(f"✓ Output saved to JSON file")
        
        # Print sample question
        if result['questions']:
            print("\nSample Question:")
            q = result['questions'][0]
            print(f"  Q: {q.get('question', 'N/A')}")
            print(f"  Difficulty: {q.get('difficulty', 'N/A')}")
            print(f"  Correct Answer: {q.get('correct', 'N/A')}")
        
        return result
    
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


async def test_quiz_validator_agent(quiz_data):
    """Test the Quiz Validator Agent"""
    print("\n" + "="*60)
    print("Testing Quiz Validator Agent")
    print("="*60)
    
    if not quiz_data:
        print("✗ Skipping validator test (no quiz data)")
        return None
    
    try:
        result = await run_quiz_validator_agent(
            quiz_id=quiz_data['quiz_id'],
            questions=quiz_data['questions'],
            topic=quiz_data['topic'],
            auto_fix=True
        )
        
        print(f"✓ Validated {result['total_questions']} questions")
        print(f"  - Valid: {result['valid_count']}")
        print(f"  - Invalid: {result['invalid_count']}")
        print(f"  - Fixed: {result['fixed_count']}")
        print(f"✓ Output saved to JSON file")
        
        return result
    
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


async def test_adaptive_agent():
    """Test the Adaptive Agent"""
    print("\n" + "="*60)
    print("Testing Adaptive Agent")
    print("="*60)
    
    try:
        result = await run_adaptive_agent(
            student_external_id="student_001",
            book_id=1,
            topic="machine learning applications",
            n_questions=5
        )
        
        print(f"✓ Generated adaptive quiz with ID: {result['quiz_id']}")
        print(f"✓ Difficulty hint: {result['difficulty_hint']}")
        print(f"✓ Number of questions: {result['n_questions']}")
        print(f"✓ Output saved to JSON file")
        
        return result
    
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


async def main():
    """Run all tests"""
    print("\n" + "╔" + "="*58 + "╗")
    print("║" + " "*15 + "AGENT TESTING SUITE" + " "*24 + "║")
    print("╚" + "="*58 + "╝")
    
    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        print("\n⚠️  WARNING: OPENAI_API_KEY not found in environment")
        print("Please set it in your .env file or environment variables")
        print("\nTests will fail without a valid API key.")
        return
    
    # Run tests sequentially
    curriculum_result = await test_curriculum_agent()
    
    quiz_result = await test_quiz_generator_agent()
    
    validator_result = await test_quiz_validator_agent(quiz_result)
    
    adaptive_result = await test_adaptive_agent()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    tests = [
        ("Curriculum Agent", curriculum_result),
        ("Quiz Generator", quiz_result),
        ("Quiz Validator", validator_result),
        ("Adaptive Agent", adaptive_result)
    ]
    
    passed = sum(1 for _, result in tests if result is not None)
    total = len(tests)
    
    for name, result in tests:
        status = "✓ PASSED" if result is not None else "✗ FAILED"
        print(f"{name:.<40} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print(f"\n✓ All agent outputs saved to JSON files in: {os.path.dirname(os.path.abspath(__file__))}")
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(main())