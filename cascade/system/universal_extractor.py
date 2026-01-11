"""
CASCADE Universal File Extractor
Powered by Apache Tika - Professional document processing
Handles ANY file format with proper metadata and content extraction
"""

import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import hashlib
from datetime import datetime

# Try to import Apache Tika (professional solution)
try:
    from tika import parser
    TIKA_AVAILABLE = True
except ImportError:
    TIKA_AVAILABLE = False
    print("⚠️ Apache Tika not installed. Install with: pip install tika")

# Fallback extractors
try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class UniversalExtractor:
    """
    Professional file extractor using Apache Tika
    Can handle ANY file format known to man
    """
    
    def __init__(self):
        self.session = None
        if TIKA_AVAILABLE:
            # Start Tika server if not running
            parser.from_buffer('')
    
    def extract_file(self, file_path: str) -> Dict[str, Any]:
        """
        Extract content and metadata from ANY file
        
        Returns:
            Dict with:
            - content: Full text content
            - metadata: File metadata
            - file_info: Basic file info
            - error: Error message if any
        """
        result = {
            "content": "",
            "metadata": {},
            "file_info": self._get_file_info(file_path),
            "error": None
        }
        
        try:
            # Use Apache Tika if available (best option)
            if TIKA_AVAILABLE:
                parsed = parser.from_file(file_path, service_url='http://localhost:9998')
                result["content"] = parsed.get("content", "")
                result["metadata"] = parsed.get("metadata", {})
                
                # Add Tika-specific metadata
                if result["metadata"]:
                    result["metadata"]["extractor"] = "Apache Tika"
                    result["metadata"]["extraction_timestamp"] = datetime.now().isoformat()
            
            # Fallback to format-specific extractors
            else:
                result = self._fallback_extract(file_path, result)
                
        except Exception as e:
            result["error"] = str(e)
            # Try fallback if Tika fails
            if TIKA_AVAILABLE:
                result = self._fallback_extract(file_path, result)
        
        return result
    
    def _get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get basic file information"""
        path = Path(file_path)
        
        # Calculate file hash
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return {
            "name": path.name,
            "extension": path.suffix.lower(),
            "size": path.stat().st_size,
            "hash_md5": hash_md5.hexdigest(),
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        }
    
    def _fallback_extract(self, file_path: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback extraction without Tika"""
        ext = Path(file_path).suffix.lower()
        
        # PDF files
        if ext == ".pdf":
            content = self._extract_pdf(file_path)
            if content:
                result["content"] = content
                result["metadata"]["extractor"] = "PDF fallback"
        
        # Office documents
        elif ext in [".docx", ".doc"]:
            content = self._extract_docx(file_path)
            if content:
                result["content"] = content
                result["metadata"]["extractor"] = "DOCX fallback"
        
        # Excel files
        elif ext in [".xlsx", ".xls"]:
            content = self._extract_excel(file_path)
            if content:
                result["content"] = content
                result["metadata"]["extractor"] = "Excel fallback"
        
        # Images with OCR (if available)
        elif ext in [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]:
            content = self._extract_image(file_path)
            if content:
                result["content"] = content
                result["metadata"]["extractor"] = "Image OCR fallback"
        
        # Code files
        elif ext in [".py", ".js", ".java", ".cpp", ".c", ".h", ".css", ".html", ".xml", ".json", ".yaml", ".yml"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                result["content"] = f.read()
                result["metadata"]["extractor"] = "Text reader"
        
        return result
    
    def _extract_pdf(self, file_path: str) -> Optional[str]:
        """Extract text from PDF using multiple methods"""
        content = ""
        
        # Try PyMuPDF first (best quality)
        if PDF_AVAILABLE:
            try:
                doc = fitz.open(file_path)
                for page in doc:
                    content += page.get_text() + "\n"
                doc.close()
                if content.strip():
                    return content
            except:
                pass
        
        # Try pdfplumber
        if PDFPLUMBER_AVAILABLE:
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text() or ""
                        content += text + "\n"
                if content.strip():
                    return content
            except:
                pass
        
        # Try PyPDF2
        if PYPDF2_AVAILABLE:
            try:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text = page.extract_text() or ""
                    content += text + "\n"
                if content.strip():
                    return content
            except:
                pass
        
        return content if content.strip() else None
    
    def _extract_docx(self, file_path: str) -> Optional[str]:
        """Extract text from DOCX"""
        if DOCX_AVAILABLE:
            try:
                doc = docx.Document(file_path)
                content = ""
                for paragraph in doc.paragraphs:
                    content += paragraph.text + "\n"
                return content if content.strip() else None
            except:
                pass
        return None
    
    def _extract_excel(self, file_path: str) -> Optional[str]:
        """Extract text from Excel"""
        if XLSX_AVAILABLE and PANDAS_AVAILABLE:
            try:
                # Read all sheets
                content = ""
                excel_file = pd.ExcelFile(file_path)
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    content += f"\n=== Sheet: {sheet_name} ===\n"
                    content += df.to_string() + "\n"
                return content if content.strip() else None
            except:
                pass
        return None
    
    def _extract_image(self, file_path: str) -> Optional[str]:
        """Extract text from image using OCR (if available)"""
        # Try OCR if pytesseract is available
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text if text.strip() else None
        except:
            return None
    
    def process_folder(self, folder_files: List[Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Process multiple files and create a unified dataset
        
        Args:
            folder_files: List of uploaded file objects
            
        Returns:
            Tuple of (DataFrame with all content, processing_summary)
        """
        all_records = []
        file_summary = []
        
        for file_obj in folder_files:
            try:
                # Extract from file
                extracted = self.extract_file(file_obj.name)
                
                # Create record
                record = {
                    "file_name": extracted["file_info"]["name"],
                    "file_extension": extracted["file_info"]["extension"],
                    "file_size": extracted["file_info"]["size"],
                    "file_hash": extracted["file_info"]["hash_md5"],
                    "content": extracted["content"],
                    "extractor": extracted["metadata"].get("extractor", "unknown"),
                    "extraction_timestamp": datetime.now().isoformat(),
                    "error": extracted["error"]
                }
                
                # Add metadata as JSON
                if extracted["metadata"]:
                    record["metadata"] = json.dumps(extracted["metadata"])
                
                all_records.append(record)
                
                # Summary
                file_summary.append({
                    "file": extracted["file_info"]["name"],
                    "status": "success" if extracted["content"] else "failed",
                    "content_length": len(extracted["content"]),
                    "extractor": extracted["metadata"].get("extractor", "unknown"),
                    "error": extracted["error"]
                })
                
            except Exception as e:
                file_summary.append({
                    "file": getattr(file_obj, 'name', 'unknown'),
                    "status": "error",
                    "error": str(e)
                })
        
        # Create DataFrame
        if all_records:
            df = pd.DataFrame(all_records)
            
            summary = {
                "total_files": len(folder_files),
                "processed": len([s for s in file_summary if s["status"] == "success"]),
                "failed": len([s for s in file_summary if s["status"] != "success"]),
                "total_content_chars": df["content"].str.len().sum(),
                "file_details": file_summary
            }
            
            return df, summary
        
        return None, {"error": "No files processed", "details": file_summary}


# Convenience function
def extract_from_files(file_list: List[Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Extract content from multiple files using the universal extractor
    
    Args:
        file_list: List of file objects
        
    Returns:
        Tuple of (DataFrame, summary)
    """
    extractor = UniversalExtractor()
    return extractor.process_folder(file_list)
