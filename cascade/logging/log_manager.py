"""
CASCADE Log Manager
Orchestrates the tsunami of data into ordered causation troops.

Manages log levels, routing, and the beautiful display of system truth.
"""

import os
import sys
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .kleene_logger import KleeneLogger, LogLevel
from .interpretive_logger import InterpretiveLogger, ImpactLevel


class LogMode(Enum):
    """The two modes of logging excellence"""
    KLEENE = "kleene"      # Mathematical precision
    INTERPRETIVE = "interpretive"  # Human stories
    DUAL = "dual"          # Both simultaneously


@dataclass
class LogConfig:
    """Configuration for logging behavior"""
    mode: LogMode = LogMode.DUAL
    min_level_kleene: LogLevel = LogLevel.INFO
    min_level_interpretive: ImpactLevel = ImpactLevel.LOW
    show_metrics: bool = True
    show_timestamps: bool = True
    color_output: bool = True
    file_output: bool = False
    max_file_size_mb: int = 100


class CascadeLogManager:
    """The conductor of your causation orchestra"""
    
    def __init__(self, config: Optional[LogConfig] = None):
        self.config = config or LogConfig()
        self.kleene_loggers: Dict[str, KleeneLogger] = {}
        self.interpretive_loggers: Dict[str, InterpretiveLogger] = {}
        self.start_time = time.time()
        self.operation_count = 0
        
        # Initialize display
        self._setup_display()
        
    def _setup_display(self):
        """Setup beautiful terminal output"""
        if self.config.color_output:
            # Enable ANSI colors
            sys.stdout.reconfigure(encoding='utf-8')
        
        # Print header
        self._print_header()
    
    def _print_header(self):
        """Print beautiful cascade header with colors"""
        # ANSI color codes
        colors = {
            "WAVE": "\033[94m",      # Bright blue
            "BRIDGE": "\033[96m",    # Cyan
            "BOLD": "\033[1m",
            "DIM": "\033[2m",
            "RESET": "\033[0m",
            "GREEN": "\033[32m",
            "YELLOW": "\033[33m",
        }
        
        wave = colors["WAVE"]
        bridge = colors["BRIDGE"]
        bold = colors["BOLD"]
        dim = colors["DIM"]
        reset = colors["RESET"]
        green = colors["GREEN"]
        yellow = colors["YELLOW"]
        
        print(f"\n{bold}{'='*80}{reset}")
        print(f"{wave}🌊{reset} {bold}CASCADE // TRUTH INFRASTRUCTURE{reset} {bridge}🧠{reset}")
        print(f"{bold}{'='*80}{reset}")
        print(f"{bold}Mode:{reset} {green}{self.config.mode.value.upper()}{reset}")
        print(f"{bold}Started:{reset} {dim}{time.strftime('%Y-%m-%d %H:%M:%S')}{reset}")
        print(f"{bold}{'='*80}{reset}\n")
    
    def register_component(self, component: str, system: str = "CASCADE"):
        """Register a component for logging"""
        if self.config.mode in [LogMode.KLEENE, LogMode.DUAL]:
            kleene = KleeneLogger(component)
            self.kleene_loggers[component] = kleene
            
        if self.config.mode in [LogMode.INTERPRETIVE, LogMode.DUAL]:
            interpretive = InterpretiveLogger(system)
            self.interpretive_loggers[system] = interpretive
    
    def log_operation(self, component: str, operation: str, 
                     level: LogLevel = LogLevel.INFO,
                     impact: ImpactLevel = ImpactLevel.LOW,
                     details: Optional[Dict] = None):
        """Log an operation across all active loggers"""
        self.operation_count += 1
        
        if self.config.mode in [LogMode.KLEENE, LogMode.DUAL]:
            if component in self.kleene_loggers:
                self.kleene_loggers[component].log(
                    level, operation,
                    state_before=details.get("before") if details else None,
                    state_after=details.get("after") if details else None,
                    fixed_point=details.get("fixed_point", False) if details else False,
                    iterations=details.get("iterations", 0) if details else 0
                )
        
        if self.config.mode in [LogMode.INTERPRETIVE, LogMode.DUAL]:
            # Find interpretive logger for component
            system = details.get("system", "CASCADE") if details else "CASCADE"
            if system in self.interpretive_loggers:
                self.interpretive_loggers[system].log(
                    impact, component, operation,
                    context=details.get("context", "") if details else "",
                    consequence=details.get("consequence", "") if details else "",
                    metrics=details.get("metrics", {}) if details else {},
                    recommendation=details.get("recommendation") if details else None
                )
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get beautiful session statistics"""
        total_kleene = sum(len(logger.entries) for logger in self.kleene_loggers.values())
        total_interpretive = sum(len(logger.entries) for logger in self.interpretive_loggers.values())
        
        return {
            "uptime_seconds": time.time() - self.start_time,
            "operations": self.operation_count,
            "kleene_entries": total_kleene,
            "interpretive_entries": total_interpretive,
            "active_components": len(self.kleene_loggers),
            "active_systems": len(self.interpretive_loggers)
        }
    
    def print_summary(self):
        """Print beautiful session summary with colors"""
        stats = self.get_session_stats()
        
        # ANSI color codes
        colors = {
            "BOLD": "\033[1m",
            "DIM": "\033[2m",
            "RESET": "\033[0m",
            "CYAN": "\033[36m",
            "GREEN": "\033[32m",
            "YELLOW": "\033[33m",
            "BLUE": "\033[34m",
            "MAGENTA": "\033[35m",
        }
        
        bold = colors["BOLD"]
        dim = colors["DIM"]
        reset = colors["RESET"]
        cyan = colors["CYAN"]
        green = colors["GREEN"]
        yellow = colors["YELLOW"]
        blue = colors["BLUE"]
        magenta = colors["MAGENTA"]
        
        print(f"\n{bold}{'='*80}{reset}")
        print(f"{cyan}📊 CASCADE SESSION SUMMARY{reset}")
        print(f"{bold}{'='*80}{reset}")
        print(f"{bold}Uptime:{reset} {stats['uptime_seconds']:.1f} seconds")
        print(f"{bold}Operations:{reset} {green}{stats['operations']:,}{reset}")
        print(f"{bold}Kleene Entries:{reset} {yellow}{stats['kleene_entries']:,}{reset}")
        print(f"{bold}Interpretive Entries:{reset} {blue}{stats['interpretive_entries']:,}{reset}")
        print(f"{bold}Active Components:{reset} {magenta}{stats['active_components']}{reset}")
        print(f"{bold}Active Systems:{reset} {magenta}{stats['active_systems']}{reset}")
        
        if stats['kleene_entries'] > 0:
            # Get session hash from first logger
            first_logger = next(iter(self.kleene_loggers.values()))
            print(f"{bold}Session Hash:{reset} {dim}{first_logger.get_session_hash()}{reset}")
        
        print(f"{bold}{'='*80}{reset}")
    
    def set_mode(self, mode: LogMode):
        """Switch logging mode dynamically"""
        old_mode = self.config.mode
        self.config.mode = mode
        
        print(f"\n🔄 Logging mode changed: {old_mode.value} → {mode.value}")
    
    def enable_file_logging(self, filepath: str):
        """Enable logging to file"""
        self.config.file_output = True
        # TODO: Implement file logging
        print(f"📁 File logging enabled: {filepath}")


# Global log manager instance
_log_manager: Optional[CascadeLogManager] = None


def init_logging(config: Optional[LogConfig] = None) -> CascadeLogManager:
    """Initialize the global CASCADE logging system"""
    global _log_manager
    _log_manager = CascadeLogManager(config)
    return _log_manager


def get_log_manager() -> CascadeLogManager:
    """Get the global log manager"""
    global _log_manager
    if _log_manager is None:
        _log_manager = CascadeLogManager()
    return _log_manager


def log(component: str, operation: str, context: str = "", consequence: str = "", 
         metrics: Dict[str, Any] = None, impact: str = "LOW", **kwargs):
    """Quick log operation - convenience function"""
    manager = get_log_manager()
    manager.log_operation(component, operation, 
                         details={
                             "context": context,
                             "consequence": consequence,
                             "metrics": metrics or {},
                             "impact": impact,
                             **kwargs
                         })


def log_fixed_point(component: str, operation: str, iterations: int, **kwargs):
    """Log successful fixed point"""
    log(component, operation, 
        level=LogLevel.INFO,
        impact=ImpactLevel.LOW,
        details={
            "fixed_point": True,
            "iterations": iterations,
            **kwargs
        })


def log_error(component: str, operation: str, error: str, **kwargs):
    """Log error condition"""
    log(component, f"{operation}_error",
        level=LogLevel.ERROR,
        impact=ImpactLevel.HIGH,
        details={
            "context": f"Operation failed: {error}",
            "consequence": "System may be degraded",
            "metrics": {"error": error},
            **kwargs
        })


def log_performance(component: str, metric: str, value: float, threshold: float):
    """Log performance warning"""
    log(component, f"performance_{metric}",
        level=LogLevel.WARNING,
        impact=ImpactLevel.MEDIUM,
        details={
            "context": f"Performance metric {metric} exceeded threshold",
            "consequence": "May impact system performance",
            "metrics": {metric: value, "threshold": threshold},
            "recommendation": f"Optimize {metric} or scale resources"
        })
