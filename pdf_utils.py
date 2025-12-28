# """
# Document text extraction utilities (PDF, DOCX, TXT)
# Supports multiple PDF libraries with fallback options
# """

# import os
# from typing import Optional, Dict, Any

# # =============================================================================
# # EXTRACTION DISPATCHER
# # =============================================================================

# def extract_text_from_file(file_path: str, method: str = 'auto') -> str:
#     """
#     Extract text from a generic file (PDF, DOCX, TXT).
    
#     Args:
#         file_path: Path to the document file
#         method: Extraction method (used only for PDFs: 'pypdf2', 'pdfplumber', 'pymupdf', or 'auto')
    
#     Returns:
#         Extracted text as a string
    
#     Raises:
#         FileNotFoundError: If file doesn't exist
#         ValueError: If file type is unsupported or extraction fails
#     """
    
#     if not os.path.exists(file_path):
#         raise FileNotFoundError(f"File not found: {file_path}")

#     file_name = os.path.basename(file_path)
#     file_ext = os.path.splitext(file_name)[1].lower()

#     print(f"📄 Extracting text from: {file_name} (Type: {file_ext})")

#     if file_ext == '.pdf':
#         return _extract_from_pdf_dispatch(file_path, method)
#     elif file_ext == '.docx':
#         return _extract_with_docx(file_path)
#     elif file_ext == '.txt':
#         return _extract_with_txt(file_path)
#     elif file_ext == '.doc':
#         raise ValueError(
#             "Unsupported file type: .doc (older Word format). Please convert it to .docx or .pdf."
#         )
#     else:
#         raise ValueError(f"Unsupported file extension: {file_ext}")


# # =============================================================================
# # GENERIC HELPERS
# # =============================================================================

# def _extract_with_txt(file_path: str) -> str:
#     """Extract text from a plain text (.txt) file"""
#     try:
#         with open(file_path, 'r', encoding='utf-8') as f:
#             extracted_text = f.read()
#         print(f"✓ Extracted {len(extracted_text)} characters from TXT")
#         return extracted_text
#     except Exception as e:
#         raise ValueError(f"Failed to read TXT file: {e}")


# def _extract_with_docx(file_path: str) -> str:
#     """Extract text from a Word (.docx) file using python-docx"""
#     try:
#         import docx
#     except ImportError:
#         raise ImportError("python-docx not installed. Run: pip install python-docx")

#     try:
#         document = docx.Document(file_path)
#         text_parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
        
#         extracted_text = '\n\n'.join(text_parts)
#         print(f"✓ Extracted {len(extracted_text)} characters using python-docx")
#         return extracted_text
#     except Exception as e:
#         raise ValueError(f"python-docx failed to extract text: {e}")


# # =============================================================================
# # PDF HELPERS (Refactored)
# # =============================================================================

# def _extract_from_pdf_dispatch(pdf_path: str, method: str = 'auto') -> str:
#     """
#     Internal dispatcher for PDF extraction methods. (Old extract_text_from_pdf)
#     """
#     methods_to_try = []
    
#     if method == 'auto':
#         methods_to_try = ['pdfplumber', 'pymupdf', 'pypdf2']
#     else:
#         methods_to_try = [method]
    
#     last_error = None
    
#     for extraction_method in methods_to_try:
#         try:
#             if extraction_method == 'pypdf2':
#                 return _extract_with_pypdf2(pdf_path)
#             elif extraction_method == 'pdfplumber':
#                 return _extract_with_pdfplumber(pdf_path)
#             elif extraction_method == 'pymupdf':
#                 return _extract_with_pymupdf(pdf_path)
#         except ImportError as e:
#             last_error = e
#             print(f"⚠️  {extraction_method} dependency not available: {e}")
#             continue
#         except Exception as e:
#             last_error = e
#             print(f"⚠️  {extraction_method} failed: {e}")
#             continue
    
#     # If we get here, all methods failed
#     raise ValueError(
#         f"Could not extract text from PDF. Last error: {last_error}\n"
#         "Try installing a PDF library (e.g., pip install PyPDF2 or pip install pdfplumber)"
#     )


# def _extract_with_pypdf2(pdf_path: str) -> str:
#     """Extract text using PyPDF2 library"""
#     try:
#         from PyPDF2 import PdfReader
#     except ImportError:
#         raise ImportError("PyPDF2 not installed. Run: pip install PyPDF2")
    
#     reader = PdfReader(pdf_path)
#     text_parts = []
    
#     for page in reader.pages:
#         page_text = page.extract_text()
#         if page_text:
#             text_parts.append(page_text)
    
#     extracted_text = '\n\n'.join(text_parts)
#     print(f"✓ Extracted {len(extracted_text)} characters using PyPDF2")
#     return extracted_text


# def _extract_with_pdfplumber(pdf_path: str) -> str:
#     """Extract text using pdfplumber library (best quality)"""
#     try:
#         import pdfplumber
#     except ImportError:
#         raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")
    
#     text_parts = []
    
#     with pdfplumber.open(pdf_path) as pdf:
#         for page in pdf.pages:
#             page_text = page.extract_text()
#             if page_text:
#                 text_parts.append(page_text)
    
#     extracted_text = '\n\n'.join(text_parts)
#     print(f"✓ Extracted {len(extracted_text)} characters using pdfplumber")
#     return extracted_text


# def _extract_with_pymupdf(pdf_path: str) -> str:
#     """Extract text using PyMuPDF/fitz library (fast)"""
#     try:
#         import fitz  # PyMuPDF
#     except ImportError:
#         raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")
    
#     text_parts = []
    
#     doc = fitz.open(pdf_path)
#     for page_num in range(len(doc)):
#         page = doc[page_num]
#         page_text = page.get_text()
#         if page_text:
#             text_parts.append(page_text)
    
#     doc.close()
    
#     extracted_text = '\n\n'.join(text_parts)
#     print(f"✓ Extracted {len(extracted_text)} characters using PyMuPDF")
#     return extracted_text


# # =============================================================================
# # INFO UTILITY (Refactored)
# # =============================================================================

# def validate_extracted_text(text: str, min_length: int = 100) -> bool:
#     """
#     Validate that extracted text is meaningful
#     """
#     if not text or len(text.strip()) < min_length:
#         return False
    
#     # Check if text is mostly printable characters
#     printable_ratio = sum(c.isprintable() or c.isspace() for c in text) / len(text)
    
#     if printable_ratio < 0.7:  # At least 70% printable
#         return False
    
#     return True


# def get_file_info(file_path: str) -> Dict[str, Any]:
#     """
#     Get basic information about a document file (PDF, DOCX, TXT). (Old get_pdf_info)
    
#     Returns:
#         Dictionary with page count (or None), file size, etc.
#     """
#     if not os.path.exists(file_path):
#         raise FileNotFoundError(f"File not found: {file_path}")
    
#     file_size = os.path.getsize(file_path)
#     file_name = os.path.basename(file_path)
#     file_ext = os.path.splitext(file_name)[1].lower()
    
#     # Try to get page count, primarily relevant for PDF
#     page_count = None
    
#     if file_ext == '.pdf':
#         try:
#             from PyPDF2 import PdfReader
#             reader = PdfReader(file_path)
#             page_count = len(reader.pages)
#         except:
#             try:
#                 import pdfplumber
#                 with pdfplumber.open(file_path) as pdf:
#                     page_count = len(pdf.pages)
#             except:
#                 pass
#     elif file_ext == '.txt':
#         # For simplicity, treat a TXT file as a single logical page
#         page_count = 1 
    
#     return {
#         'path': file_path,
#         'filename': file_name,
#         'extension': file_ext,
#         'size_bytes': file_size,
#         'size_mb': round(file_size / (1024 * 1024), 2),
#         'page_count': page_count
#     }


# # Example usage
# if __name__ == "__main__":
#     # Test the extraction
#     test_file = "sample.pdf"  # Replace with a .pdf, .docx, or .txt file path
    
#     if os.path.exists(test_file):
#         try:
#             # Get file info
#             info = get_file_info(test_file)
#             print(f"File Info: {info}")
            
#             # Extract text
#             # Note: For .docx, you need 'pip install python-docx'
#             # For PDF, you need 'pip install PyPDF2' or 'pip install pdfplumber'
#             text = extract_text_from_file(test_file)
            
#             # Validate
#             if validate_extracted_text(text):
#                 print(f"✓ Successfully extracted {len(text)} characters")
#                 print(f"Preview: {text[:200]}...")
#             else:
#                 print("⚠️  Extracted text appears invalid or too short")
                
#         except Exception as e:
#             print(f"Error: {e}")
#     else:
#         print(f"Test file '{test_file}' not found. Create one (e.g., 'sample.txt') to test.")


"""
PDF utilities for text extraction and validation
Handles PDF processing for the quiz generation system
"""

import os
from typing import Dict, Any, Optional
import PyPDF2


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        str: Extracted text from all pages
    
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        Exception: If PDF cannot be read
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        text = ""
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            print(f"📄 Extracting text from {len(pdf_reader.pages)} pages...")
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
                    
                    # Progress indicator for large PDFs
                    if page_num % 10 == 0:
                        print(f"   Processed {page_num}/{len(pdf_reader.pages)} pages...")
                
                except Exception as e:
                    print(f"   ⚠️ Warning: Could not extract text from page {page_num}: {e}")
                    continue
        
        return text.strip()
    
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


def get_pdf_info(pdf_path: str) -> Dict[str, Any]:
    """
    Get metadata information about a PDF file
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        dict: PDF metadata including page count, file size, etc.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            info = {
                'page_count': len(pdf_reader.pages),
                'file_size_bytes': os.path.getsize(pdf_path),
                'file_size_mb': round(os.path.getsize(pdf_path) / (1024 * 1024), 2),
                'filename': os.path.basename(pdf_path)
            }
            
            # Try to get PDF metadata if available
            if pdf_reader.metadata:
                metadata = pdf_reader.metadata
                info['title'] = metadata.get('/Title', 'Unknown')
                info['author'] = metadata.get('/Author', 'Unknown')
                info['subject'] = metadata.get('/Subject', '')
                info['creator'] = metadata.get('/Creator', '')
            
            return info
    
    except Exception as e:
        print(f"⚠️ Warning: Could not read PDF info: {e}")
        return {
            'page_count': 0,
            'file_size_bytes': os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0,
            'file_size_mb': 0,
            'filename': os.path.basename(pdf_path)
        }


def validate_extracted_text(text: str, min_length: int = 100) -> bool:
    """
    Validate that extracted text is meaningful
    
    Args:
        text: Extracted text to validate
        min_length: Minimum required text length
    
    Returns:
        bool: True if text is valid, False otherwise
    """
    if not text or not isinstance(text, str):
        print("❌ Validation failed: No text extracted")
        return False
    
    text_cleaned = text.strip()
    
    if len(text_cleaned) < min_length:
        print(f"❌ Validation failed: Text too short (got {len(text_cleaned)} chars, need {min_length})")
        return False
    
    # Check if text has reasonable word count
    words = text_cleaned.split()
    if len(words) < 20:
        print(f"❌ Validation failed: Too few words (got {len(words)} words)")
        return False
    
    # Check for reasonable character distribution (not all special chars)
    alphanumeric_count = sum(c.isalnum() for c in text_cleaned)
    if alphanumeric_count < len(text_cleaned) * 0.5:
        print(f"❌ Validation failed: Text contains too many special characters")
        return False
    
    print(f"✓ Text validation passed: {len(text_cleaned)} characters, {len(words)} words")
    return True


# Alternative function name for backward compatibility
def extract_text_from_file(file_path: str) -> str:
    """
    Alias for extract_text_from_pdf for backward compatibility
    """
    return extract_text_from_pdf(file_path)


# Export all functions
__all__ = [
    'extract_text_from_pdf',
    'extract_text_from_file',
    'get_pdf_info',
    'validate_extracted_text'
]


# Test function
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        
        print("\n" + "="*70)
        print("PDF Extraction Test")
        print("="*70)
        
        try:
            # Get PDF info
            info = get_pdf_info(pdf_path)
            print(f"\n📄 PDF Information:")
            print(f"   File: {info['filename']}")
            print(f"   Size: {info['file_size_mb']} MB")
            print(f"   Pages: {info['page_count']}")
            
            # Extract text
            print(f"\n🔄 Extracting text...")
            text = extract_text_from_pdf(pdf_path)
            
            # Validate
            if validate_extracted_text(text):
                print(f"\n✅ Success! Extracted {len(text)} characters")
                print(f"\nFirst 500 characters:")
                print("-" * 70)
                print(text[:500])
                print("-" * 70)
            else:
                print("\n❌ Validation failed")
        
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    else:
        print("Usage: python pdf_utils.py <path_to_pdf>")