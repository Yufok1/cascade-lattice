"""
CASCADE Repository Ingester
Convert entire repositories into analyzable datasets
For Omnidirectional Engineering - closing the causation loop
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pandas as pd
from datetime import datetime

# Git operations
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    print("⚠️ GitPython not installed. Install with: pip install GitPython")

# Code analysis
try:
    import ast
    AST_AVAILABLE = True
except ImportError:
    AST_AVAILABLE = False


class RepoIngester:
    """
    Convert repository into structured dataset for analysis
    """
    
    def __init__(self):
        self.repo_data = {
            "files": [],
            "structure": {},
            "dependencies": {},
            "commits": [],
            "metrics": {}
        }
    
    def ingest_repo(self, repo_path: str, include_history: bool = False) -> pd.DataFrame:
        """
        Ingest entire repository into structured dataset
        
        Args:
            repo_path: Path to repository (local or remote URL)
            include_history: Whether to analyze git history
            
        Returns:
            DataFrame with repository content and metadata
        """
        # Handle remote URLs
        if repo_path.startswith(("http://", "https://", "git@")):
            repo_path = self._clone_repo(repo_path)
        
        # Analyze repository
        self._analyze_structure(repo_path)
        self._extract_files(repo_path)
        
        if include_history and GIT_AVAILABLE:
            self._analyze_history(repo_path)
        
        # Convert to dataset
        df = self._create_dataset()
        
        return df, self._generate_summary()
    
    def _clone_repo(self, repo_url: str) -> str:
        """Clone remote repository to temporary directory"""
        import tempfile
        
        temp_dir = tempfile.mkdtemp(prefix="cascade_repo_")
        
        if GIT_AVAILABLE:
            git.Repo.clone_from(repo_url, temp_dir)
        
        return temp_dir
    
    def _analyze_structure(self, repo_path: str):
        """Analyze repository structure"""
        repo_path = Path(repo_path)
        
        # Build directory tree
        structure = {}
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories and common build dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and 
                      d not in ['node_modules', '__pycache__', 'target', 'build']]
            
            rel_path = Path(root).relative_to(repo_path)
            
            for file in files:
                if not file.startswith('.'):
                    file_path = rel_path / file
                    structure[str(file_path)] = {
                        "type": "file",
                        "size": os.path.getsize(os.path.join(root, file)),
                        "extension": Path(file).suffix.lower()
                    }
        
        self.repo_data["structure"] = structure
    
    def _extract_files(self, repo_path: str):
        """Extract content from all files"""
        repo_path = Path(repo_path)
        
        for file_path in self.repo_data["structure"].keys():
            full_path = repo_path / file_path
            
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                file_info = {
                    "path": file_path,
                    "content": content,
                    "size": len(content),
                    "lines": len(content.splitlines()),
                    "language": self._detect_language(file_path),
                    "type": self._classify_file(file_path, content),
                    "hash": hashlib.md5(content.encode()).hexdigest()[:16]
                }
                
                # Extract code-specific info
                if file_info["language"] == "python" and AST_AVAILABLE:
                    file_info.update(self._analyze_python(content))
                
                self.repo_data["files"].append(file_info)
                
            except Exception as e:
                self.repo_data["files"].append({
                    "path": file_path,
                    "content": "",
                    "error": str(e),
                    "type": "binary"
                })
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".php": "php",
            ".rb": "ruby",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".m": "matlab",
            ".sh": "shell",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".less": "less",
            ".xml": "xml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".md": "markdown",
            ".txt": "text",
            ".dockerfile": "dockerfile",
            "dockerfile": "dockerfile"
        }
        
        return language_map.get(ext, "unknown")
    
    def _classify_file(self, file_path: str, content: str) -> str:
        """Classify file type based on path and content"""
        path_lower = file_path.lower()
        
        # Configuration files
        if any(x in path_lower for x in ["config", "settings", ".env", "ini", "toml", "yaml", "yml"]):
            return "config"
        
        # Documentation
        if path_lower.endswith((".md", ".rst", ".txt")):
            return "documentation"
        
        # Tests
        if "test" in path_lower or "spec" in path_lower:
            return "test"
        
        # Dependencies
        if any(x in path_lower for x in ["requirements", "package", "pipfile", "yarn", "pom.xml"]):
            return "dependencies"
        
        # CI/CD
        if any(x in path_lower for x in [".github", "gitlab", "jenkins", "dockerfile"]):
            return "cicd"
        
        # Code
        if self._detect_language(file_path) != "unknown":
            return "code"
        
        return "other"
    
    def _analyze_python(self, content: str) -> Dict[str, Any]:
        """Analyze Python code structure"""
        try:
            tree = ast.parse(content)
            
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args]
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line": node.lineno
                    })
                elif isinstance(node, ast.Import):
                    imports.extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    imports.append(f"from {node.module}")
            
            return {
                "functions": functions,
                "classes": classes,
                "imports": imports,
                "complexity": len(functions) + len(classes)
            }
            
        except:
            return {"functions": [], "classes": [], "imports": [], "complexity": 0}
    
    def _analyze_history(self, repo_path: str):
        """Analyze git history for patterns"""
        try:
            repo = git.Repo(repo_path)
            
            commits = []
            for commit in repo.iter_commits(max_count=100):
                commits.append({
                    "hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": commit.author.name,
                    "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
                    "files_changed": len(commit.stats.files),
                    "insertions": commit.stats.total["insertions"],
                    "deletions": commit.stats.total["deletions"]
                })
            
            self.repo_data["commits"] = commits
            
        except Exception as e:
            print(f"Could not analyze git history: {e}")
    
    def _create_dataset(self) -> pd.DataFrame:
        """Create structured dataset from repository"""
        records = []
        
        for file_info in self.repo_data["files"]:
            # Split content into manageable chunks
            content = file_info.get("content", "")
            
            # Create records for analysis
            record = {
                # File metadata
                "file_path": file_info["path"],
                "file_type": file_info["type"],
                "language": file_info.get("language", "unknown"),
                "file_size": file_info.get("size", 0),
                "file_hash": file_info.get("hash", ""),
                
                # Content analysis
                "content": content,
                "line_count": file_info.get("lines", 0),
                
                # Code-specific metrics
                "function_count": len(file_info.get("functions", [])),
                "class_count": len(file_info.get("classes", [])),
                "import_count": len(file_info.get("imports", [])),
                "complexity": file_info.get("complexity", 0),
                
                # Timestamp
                "ingestion_timestamp": datetime.now().isoformat(),
                
                # Source type
                "source_type": "repository"
            }
            
            records.append(record)
        
        return pd.DataFrame(records)
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate repository analysis summary"""
        files = self.repo_data["files"]
        
        summary = {
            "total_files": len(files),
            "languages": {},
            "file_types": {},
            "total_lines": sum(f.get("lines", 0) for f in files),
            "total_functions": sum(len(f.get("functions", [])) for f in files),
            "total_classes": sum(len(f.get("classes", [])) for f in files),
            "commits_analyzed": len(self.repo_data.get("commits", []))
        }
        
        # Count languages
        for f in files:
            lang = f.get("language", "unknown")
            summary["languages"][lang] = summary["languages"].get(lang, 0) + 1
            ftype = f.get("type", "other")
            summary["file_types"][ftype] = summary["file_types"].get(ftype, 0) + 1
        
        return summary


def ingest_repository(repo_path: str, include_history: bool = False) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Convenience function to ingest repository
    
    Args:
        repo_path: Path or URL to repository
        include_history: Include git history analysis
        
    Returns:
        Tuple of (DataFrame, summary)
    """
    ingester = RepoIngester()
    return ingester.ingest_repo(repo_path, include_history)
