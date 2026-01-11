"""
CASCADE Folder Processor
Handle batch processing of multiple files in folders
"""

import os
import zipfile
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd

def process_folder_upload(files: List[Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Process multiple uploaded files and combine them
    
    Args:
        files: List of uploaded file objects from Gradio
        
    Returns:
        Tuple of (combined_dataframe, processing_summary)
    """
    if not files:
        return None, {"error": "No files provided"}
    
    all_data = []
    file_summary = []
    total_rows = 0
    
    for file_obj in files:
        try:
            # Get file path and info
            file_path = file_obj.name
            file_name = Path(file_path).name
            file_ext = Path(file_path).suffix.lower()
            
            # Read file based on extension
            df = None
            
            if file_ext == ".csv":
                df = pd.read_csv(file_path)
            elif file_ext == ".json":
                df = pd.read_json(file_path)
            elif file_ext == ".jsonl":
                df = pd.read_json(file_path, lines=True)
            elif file_ext == ".parquet":
                df = pd.read_parquet(file_path)
            elif file_ext in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path)
            else:
                # For other formats, try to extract text
                from .file_extractors import extract_from_file
                result = extract_from_file(file_path)
                if result.lines:
                    df = pd.DataFrame([{"text": line, "source_file": file_name} 
                                     for line in result.lines])
                else:
                    file_summary.append({
                        "file": file_name,
                        "status": "skipped",
                        "reason": "Unsupported format"
                    })
                    continue
            
            # Add source file column
            if df is not None and len(df) > 0:
                df["source_file"] = file_name
                all_data.append(df)
                
                file_summary.append({
                    "file": file_name,
                    "status": "success",
                    "rows": len(df),
                    "columns": len(df.columns)
                })
                total_rows += len(df)
                
        except Exception as e:
            file_summary.append({
                "file": file_name,
                "status": "error",
                "error": str(e)
            })
    
    # Combine all data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        
        summary = {
            "total_files": len(files),
            "processed_files": len([s for s in file_summary if s["status"] == "success"]),
            "total_rows": total_rows,
            "file_details": file_summary
        }
        
        return combined_df, summary
    else:
        return None, {"error": "No files could be processed", "details": file_summary}

def process_zip_file(zip_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Process a zip file containing multiple files
    
    Args:
        zip_path: Path to the zip file
        
    Returns:
        Tuple of (combined_dataframe, processing_summary)
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract zip
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find all extracted files
        extracted_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Create a mock file object with name attribute
                class MockFile:
                    def __init__(self, path):
                        self.name = path
                extracted_files.append(MockFile(file_path))
        
        return process_folder_upload(extracted_files)
