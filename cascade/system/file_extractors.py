"""
CASCADE System Observatory - File Format Extractors.

Extract log data from various file formats:
- Text: .log, .txt, .jsonl, .json, .yaml, .xml
- Tabular: .csv, .tsv, .parquet, .xlsx, .xls
- Compressed: .gz, .zip, .tar, .tar.gz, .bz2
- Documents: .pdf (text extraction)
- Databases: .sqlite, .db
- Binary logs: Windows Event Log (.evtx), systemd journal

Each extractor converts its format into lines of text that
UniversalAdapter can then parse.
"""

import io
import json
import gzip
import zipfile
import tarfile
import bz2
import tempfile
from pathlib import Path
from typing import List, Iterator, Optional, Tuple, Union, BinaryIO
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """Result of extracting log data from a file."""
    lines: List[str]
    source_format: str
    file_count: int = 1  # For archives
    total_bytes: int = 0
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class BaseExtractor(ABC):
    """Base class for file format extractors."""
    
    extensions: List[str] = []
    name: str = "base"
    
    @abstractmethod
    def extract(self, file_path: str) -> ExtractionResult:
        """Extract log lines from the file."""
        pass
    
    @abstractmethod
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        """Extract from raw bytes (for uploaded files)."""
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT FORMATS
# ═══════════════════════════════════════════════════════════════════════════════

class TextExtractor(BaseExtractor):
    """Extract from plain text files (.log, .txt, .out, etc.)"""
    
    extensions = [".log", ".txt", ".out", ".err", ".stdout", ".stderr"]
    name = "text"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        lines = content.strip().split("\n")
        return ExtractionResult(
            lines=lines,
            source_format="text",
            total_bytes=len(content),
        )
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        content = data.decode("utf-8", errors="ignore")
        lines = content.strip().split("\n")
        return ExtractionResult(
            lines=lines,
            source_format="text",
            total_bytes=len(data),
        )


class JSONExtractor(BaseExtractor):
    """Extract from JSON/JSONL files."""
    
    extensions = [".json", ".jsonl", ".ndjson"]
    name = "json"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return self._process_content(content)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        content = data.decode("utf-8", errors="ignore")
        return self._process_content(content)
    
    def _process_content(self, content: str) -> ExtractionResult:
        lines = []
        warnings = []
        
        # Try as JSONL first (one JSON per line)
        raw_lines = content.strip().split("\n")
        is_jsonl = True
        
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
                lines.append(line)
            except json.JSONDecodeError:
                is_jsonl = False
                break
        
        if not is_jsonl:
            # Try as single JSON array
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    lines = [json.dumps(item) for item in data]
                elif isinstance(data, dict):
                    # Single object - might have nested logs
                    if "logs" in data:
                        lines = [json.dumps(item) for item in data["logs"]]
                    elif "events" in data:
                        lines = [json.dumps(item) for item in data["events"]]
                    elif "records" in data:
                        lines = [json.dumps(item) for item in data["records"]]
                    else:
                        lines = [json.dumps(data)]
            except json.JSONDecodeError as e:
                warnings.append(f"JSON parse error: {e}")
                # Fall back to raw lines
                lines = raw_lines
        
        return ExtractionResult(
            lines=lines,
            source_format="json" if not is_jsonl else "jsonl",
            total_bytes=len(content),
            warnings=warnings,
        )


class XMLExtractor(BaseExtractor):
    """Extract from XML log files."""
    
    extensions = [".xml"]
    name = "xml"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return self._process_content(content)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        content = data.decode("utf-8", errors="ignore")
        return self._process_content(content)
    
    def _process_content(self, content: str) -> ExtractionResult:
        lines = []
        warnings = []
        
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            
            # Look for common log element patterns
            log_tags = ["log", "entry", "event", "record", "message", "item", "row"]
            
            for tag in log_tags:
                elements = root.findall(f".//{tag}")
                if elements:
                    for elem in elements:
                        # Convert element to dict
                        entry = {child.tag: child.text for child in elem}
                        if elem.text and elem.text.strip():
                            entry["_text"] = elem.text.strip()
                        entry.update(elem.attrib)
                        lines.append(json.dumps(entry))
                    break
            
            if not lines:
                # No standard log elements, extract all leaf text
                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        lines.append(elem.text.strip())
                        
        except Exception as e:
            warnings.append(f"XML parse error: {e}")
            # Fall back to line-by-line
            lines = [l.strip() for l in content.split("\n") if l.strip()]
        
        return ExtractionResult(
            lines=lines,
            source_format="xml",
            total_bytes=len(content),
            warnings=warnings,
        )


class YAMLExtractor(BaseExtractor):
    """Extract from YAML files (often used for K8s events)."""
    
    extensions = [".yaml", ".yml"]
    name = "yaml"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return self._process_content(content)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        content = data.decode("utf-8", errors="ignore")
        return self._process_content(content)
    
    def _process_content(self, content: str) -> ExtractionResult:
        lines = []
        warnings = []
        
        try:
            import yaml
            
            # Handle multi-document YAML (---separated)
            docs = list(yaml.safe_load_all(content))
            
            for doc in docs:
                if doc is None:
                    continue
                if isinstance(doc, list):
                    for item in doc:
                        lines.append(json.dumps(item, default=str))
                elif isinstance(doc, dict):
                    # Check for items list (K8s style)
                    if "items" in doc:
                        for item in doc["items"]:
                            lines.append(json.dumps(item, default=str))
                    else:
                        lines.append(json.dumps(doc, default=str))
                        
        except ImportError:
            warnings.append("PyYAML not installed, treating as text")
            lines = [l for l in content.split("\n") if l.strip() and not l.startswith("#")]
        except Exception as e:
            warnings.append(f"YAML parse error: {e}")
            lines = [l for l in content.split("\n") if l.strip()]
        
        return ExtractionResult(
            lines=lines,
            source_format="yaml",
            total_bytes=len(content),
            warnings=warnings,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TABULAR FORMATS
# ═══════════════════════════════════════════════════════════════════════════════

class CSVExtractor(BaseExtractor):
    """Extract from CSV/TSV files."""
    
    extensions = [".csv", ".tsv"]
    name = "csv"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return self._process_content(content, file_path)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        content = data.decode("utf-8", errors="ignore")
        return self._process_content(content, filename)
    
    def _process_content(self, content: str, filename: str = "") -> ExtractionResult:
        import csv
        
        lines = []
        warnings = []
        
        # Detect delimiter
        delimiter = "\t" if filename.endswith(".tsv") else ","
        
        try:
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            for row in reader:
                # Convert row to JSON
                lines.append(json.dumps(dict(row)))
        except Exception as e:
            warnings.append(f"CSV parse error: {e}")
            # Fall back to raw lines
            lines = [l for l in content.split("\n") if l.strip()]
        
        return ExtractionResult(
            lines=lines,
            source_format="csv",
            total_bytes=len(content),
            warnings=warnings,
        )


class ParquetExtractor(BaseExtractor):
    """Extract from Parquet files."""
    
    extensions = [".parquet", ".pq"]
    name = "parquet"
    
    def extract(self, file_path: str) -> ExtractionResult:
        return self._process_file(file_path)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        # Write to temp file for pyarrow
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            f.write(data)
            temp_path = f.name
        
        try:
            result = self._process_file(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
        
        return result
    
    def _process_file(self, file_path: str) -> ExtractionResult:
        lines = []
        warnings = []
        total_bytes = Path(file_path).stat().st_size
        
        try:
            import pyarrow.parquet as pq
            
            table = pq.read_table(file_path)
            df_dict = table.to_pydict()
            
            # Convert to row-wise JSON
            num_rows = len(next(iter(df_dict.values()))) if df_dict else 0
            for i in range(num_rows):
                row = {k: v[i] for k, v in df_dict.items()}
                lines.append(json.dumps(row, default=str))
                
        except ImportError:
            warnings.append("PyArrow not installed, cannot read Parquet")
        except Exception as e:
            warnings.append(f"Parquet read error: {e}")
        
        return ExtractionResult(
            lines=lines,
            source_format="parquet",
            total_bytes=total_bytes,
            warnings=warnings,
        )


class ExcelExtractor(BaseExtractor):
    """Extract from Excel files."""
    
    extensions = [".xlsx", ".xls"]
    name = "excel"
    
    def extract(self, file_path: str) -> ExtractionResult:
        return self._process_file(file_path)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        suffix = ".xlsx" if filename.endswith(".xlsx") else ".xls"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            temp_path = f.name
        
        try:
            result = self._process_file(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
        
        return result
    
    def _process_file(self, file_path: str) -> ExtractionResult:
        lines = []
        warnings = []
        total_bytes = Path(file_path).stat().st_size
        
        try:
            import pandas as pd
            
            # Read all sheets
            xlsx = pd.ExcelFile(file_path)
            
            for sheet_name in xlsx.sheet_names:
                df = pd.read_excel(xlsx, sheet_name=sheet_name)
                
                for _, row in df.iterrows():
                    record = row.to_dict()
                    record["_sheet"] = sheet_name
                    # Clean NaN values
                    record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
                    lines.append(json.dumps(record, default=str))
                    
        except ImportError:
            warnings.append("Pandas not installed, cannot read Excel")
        except Exception as e:
            warnings.append(f"Excel read error: {e}")
        
        return ExtractionResult(
            lines=lines,
            source_format="excel",
            total_bytes=total_bytes,
            warnings=warnings,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# COMPRESSED FORMATS
# ═══════════════════════════════════════════════════════════════════════════════

class GzipExtractor(BaseExtractor):
    """Extract from gzip compressed files."""
    
    extensions = [".gz", ".gzip"]
    name = "gzip"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with gzip.open(file_path, "rb") as f:
            data = f.read()
        
        # Determine inner format from filename
        inner_name = file_path[:-3] if file_path.endswith(".gz") else file_path
        return self._extract_inner(data, inner_name)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        decompressed = gzip.decompress(data)
        inner_name = filename[:-3] if filename.endswith(".gz") else filename
        return self._extract_inner(decompressed, inner_name)
    
    def _extract_inner(self, data: bytes, inner_name: str) -> ExtractionResult:
        # Get appropriate extractor for inner content
        extractor = get_extractor_for_file(inner_name)
        if extractor and extractor.name != "gzip":
            result = extractor.extract_bytes(data, inner_name)
            result.source_format = f"gzip/{result.source_format}"
            return result
        
        # Default to text
        content = data.decode("utf-8", errors="ignore")
        return ExtractionResult(
            lines=content.strip().split("\n"),
            source_format="gzip/text",
            total_bytes=len(data),
        )


class ZipExtractor(BaseExtractor):
    """Extract from ZIP archives."""
    
    extensions = [".zip"]
    name = "zip"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with open(file_path, "rb") as f:
            return self.extract_bytes(f.read(), file_path)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        all_lines = []
        warnings = []
        file_count = 0
        
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):  # Directory
                    continue
                
                try:
                    with zf.open(name) as f:
                        file_data = f.read()
                    
                    extractor = get_extractor_for_file(name)
                    if extractor:
                        result = extractor.extract_bytes(file_data, name)
                        all_lines.extend(result.lines)
                        warnings.extend(result.warnings)
                    else:
                        # Try as text
                        content = file_data.decode("utf-8", errors="ignore")
                        all_lines.extend(content.strip().split("\n"))
                    
                    file_count += 1
                except Exception as e:
                    warnings.append(f"Error extracting {name}: {e}")
        
        return ExtractionResult(
            lines=all_lines,
            source_format="zip",
            file_count=file_count,
            total_bytes=len(data),
            warnings=warnings,
        )


class TarExtractor(BaseExtractor):
    """Extract from TAR archives (.tar, .tar.gz, .tgz, .tar.bz2)."""
    
    extensions = [".tar", ".tar.gz", ".tgz", ".tar.bz2"]
    name = "tar"
    
    def extract(self, file_path: str) -> ExtractionResult:
        mode = "r:*"  # Auto-detect compression
        all_lines = []
        warnings = []
        file_count = 0
        
        try:
            with tarfile.open(file_path, mode) as tf:
                for member in tf.getmembers():
                    if not member.isfile():
                        continue
                    
                    try:
                        f = tf.extractfile(member)
                        if f is None:
                            continue
                        
                        file_data = f.read()
                        extractor = get_extractor_for_file(member.name)
                        
                        if extractor:
                            result = extractor.extract_bytes(file_data, member.name)
                            all_lines.extend(result.lines)
                            warnings.extend(result.warnings)
                        else:
                            content = file_data.decode("utf-8", errors="ignore")
                            all_lines.extend(content.strip().split("\n"))
                        
                        file_count += 1
                    except Exception as e:
                        warnings.append(f"Error extracting {member.name}: {e}")
        except Exception as e:
            warnings.append(f"TAR open error: {e}")
        
        return ExtractionResult(
            lines=all_lines,
            source_format="tar",
            file_count=file_count,
            total_bytes=Path(file_path).stat().st_size,
            warnings=warnings,
        )
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            f.write(data)
            temp_path = f.name
        
        try:
            result = self.extract(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
        
        result.total_bytes = len(data)
        return result


class Bz2Extractor(BaseExtractor):
    """Extract from bzip2 compressed files."""
    
    extensions = [".bz2"]
    name = "bz2"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with bz2.open(file_path, "rb") as f:
            data = f.read()
        
        inner_name = file_path[:-4] if file_path.endswith(".bz2") else file_path
        return self._extract_inner(data, inner_name)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        decompressed = bz2.decompress(data)
        inner_name = filename[:-4] if filename.endswith(".bz2") else filename
        return self._extract_inner(decompressed, inner_name)
    
    def _extract_inner(self, data: bytes, inner_name: str) -> ExtractionResult:
        extractor = get_extractor_for_file(inner_name)
        if extractor and extractor.name != "bz2":
            result = extractor.extract_bytes(data, inner_name)
            result.source_format = f"bz2/{result.source_format}"
            return result
        
        content = data.decode("utf-8", errors="ignore")
        return ExtractionResult(
            lines=content.strip().split("\n"),
            source_format="bz2/text",
            total_bytes=len(data),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT FORMATS
# ═══════════════════════════════════════════════════════════════════════════════

class PDFExtractor(BaseExtractor):
    """Extract text from PDF files."""
    
    extensions = [".pdf"]
    name = "pdf"
    
    def extract(self, file_path: str) -> ExtractionResult:
        with open(file_path, "rb") as f:
            return self.extract_bytes(f.read(), file_path)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        lines = []
        warnings = []
        
        # Try multiple PDF libraries
        extracted = False
        
        # Try PyMuPDF (fitz) first - best quality
        if not extracted:
            try:
                import fitz  # PyMuPDF
                
                doc = fitz.open(stream=data, filetype="pdf")
                for page in doc:
                    text = page.get_text()
                    lines.extend(text.strip().split("\n"))
                doc.close()
                extracted = True
            except ImportError:
                pass
            except Exception as e:
                warnings.append(f"PyMuPDF error: {e}")
        
        # Try pdfplumber
        if not extracted:
            try:
                import pdfplumber
                
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text() or ""
                        lines.extend(text.strip().split("\n"))
                extracted = True
            except ImportError:
                pass
            except Exception as e:
                warnings.append(f"pdfplumber error: {e}")
        
        # Try PyPDF2
        if not extracted:
            try:
                from PyPDF2 import PdfReader
                
                reader = PdfReader(io.BytesIO(data))
                for page in reader.pages:
                    text = page.extract_text() or ""
                    lines.extend(text.strip().split("\n"))
                extracted = True
            except ImportError:
                pass
            except Exception as e:
                warnings.append(f"PyPDF2 error: {e}")
        
        if not extracted:
            warnings.append("No PDF library available. Install: pip install pymupdf pdfplumber PyPDF2")
        
        # Filter empty lines and clean up
        lines = [l.strip() for l in lines if l.strip()]
        
        return ExtractionResult(
            lines=lines,
            source_format="pdf",
            total_bytes=len(data),
            warnings=warnings,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE FORMATS
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteExtractor(BaseExtractor):
    """Extract from SQLite database files."""
    
    extensions = [".sqlite", ".db", ".sqlite3"]
    name = "sqlite"
    
    def extract(self, file_path: str) -> ExtractionResult:
        return self._process_db(file_path)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(data)
            temp_path = f.name
        
        try:
            result = self._process_db(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
        
        result.total_bytes = len(data)
        return result
    
    def _process_db(self, file_path: str) -> ExtractionResult:
        import sqlite3
        
        lines = []
        warnings = []
        
        try:
            conn = sqlite3.connect(file_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Look for log-like tables first
            log_tables = [t for t in tables if any(x in t.lower() 
                         for x in ["log", "event", "audit", "trace", "message", "record"])]
            
            # If no log tables, use all tables
            target_tables = log_tables if log_tables else tables
            
            for table in target_tables:
                try:
                    cursor.execute(f"SELECT * FROM [{table}] LIMIT 10000")
                    columns = [desc[0] for desc in cursor.description]
                    
                    for row in cursor.fetchall():
                        record = dict(zip(columns, row))
                        record["_table"] = table
                        lines.append(json.dumps(record, default=str))
                except Exception as e:
                    warnings.append(f"Error reading table {table}: {e}")
            
            conn.close()
            
        except Exception as e:
            warnings.append(f"SQLite error: {e}")
        
        return ExtractionResult(
            lines=lines,
            source_format="sqlite",
            total_bytes=Path(file_path).stat().st_size,
            warnings=warnings,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BINARY LOG FORMATS
# ═══════════════════════════════════════════════════════════════════════════════

class WindowsEventLogExtractor(BaseExtractor):
    """Extract from Windows Event Log files (.evtx)."""
    
    extensions = [".evtx"]
    name = "evtx"
    
    def extract(self, file_path: str) -> ExtractionResult:
        return self._process_evtx(file_path)
    
    def extract_bytes(self, data: bytes, filename: str = "") -> ExtractionResult:
        with tempfile.NamedTemporaryFile(suffix=".evtx", delete=False) as f:
            f.write(data)
            temp_path = f.name
        
        try:
            result = self._process_evtx(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
        
        result.total_bytes = len(data)
        return result
    
    def _process_evtx(self, file_path: str) -> ExtractionResult:
        lines = []
        warnings = []
        
        try:
            from evtx import PyEvtxParser
            
            parser = PyEvtxParser(file_path)
            for record in parser.records():
                try:
                    lines.append(json.dumps(record, default=str))
                except:
                    pass
                    
        except ImportError:
            warnings.append("evtx library not installed. Install: pip install evtx")
        except Exception as e:
            warnings.append(f"EVTX parse error: {e}")
        
        return ExtractionResult(
            lines=lines,
            source_format="evtx",
            total_bytes=Path(file_path).stat().st_size if Path(file_path).exists() else 0,
            warnings=warnings,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTOR REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

# All available extractors
EXTRACTORS: List[BaseExtractor] = [
    TextExtractor(),
    JSONExtractor(),
    XMLExtractor(),
    YAMLExtractor(),
    CSVExtractor(),
    ParquetExtractor(),
    ExcelExtractor(),
    GzipExtractor(),
    ZipExtractor(),
    TarExtractor(),
    Bz2Extractor(),
    PDFExtractor(),
    SQLiteExtractor(),
    WindowsEventLogExtractor(),
]

# Build extension -> extractor mapping
EXTENSION_MAP: dict = {}
for extractor in EXTRACTORS:
    for ext in extractor.extensions:
        EXTENSION_MAP[ext] = extractor


def get_extractor_for_file(filename: str) -> Optional[BaseExtractor]:
    """Get the appropriate extractor for a file based on extension."""
    path = Path(filename)
    
    # Handle compound extensions like .tar.gz
    suffixes = path.suffixes
    if len(suffixes) >= 2:
        compound = "".join(suffixes[-2:])
        if compound in EXTENSION_MAP:
            return EXTENSION_MAP[compound]
    
    # Single extension
    suffix = path.suffix.lower()
    return EXTENSION_MAP.get(suffix)


def extract_from_file(file_path: str) -> ExtractionResult:
    """
    Extract log lines from any supported file format.
    
    Args:
        file_path: Path to the file
        
    Returns:
        ExtractionResult with lines and metadata
    """
    extractor = get_extractor_for_file(file_path)
    
    if extractor is None:
        # Default to text extraction
        extractor = TextExtractor()
    
    return extractor.extract(file_path)


def extract_from_bytes(data: bytes, filename: str) -> ExtractionResult:
    """
    Extract log lines from raw bytes (e.g., uploaded file).
    
    Args:
        data: Raw file bytes
        filename: Original filename (for format detection)
        
    Returns:
        ExtractionResult with lines and metadata
    """
    extractor = get_extractor_for_file(filename)
    
    if extractor is None:
        extractor = TextExtractor()
    
    return extractor.extract_bytes(data, filename)


def get_supported_extensions() -> List[str]:
    """Get list of all supported file extensions."""
    return list(EXTENSION_MAP.keys())


def get_supported_formats() -> dict:
    """Get mapping of format name to extensions."""
    formats = {}
    for extractor in EXTRACTORS:
        formats[extractor.name] = extractor.extensions
    return formats
