"""
PII Detection for CASCADE

Industry standard PII (Personally Identifiable Information) detection
based on Microsoft Presidio patterns and common PII taxonomies.

References:
- Microsoft Presidio: https://github.com/microsoft/presidio
- NIST PII Guide: https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-122.pdf
- GDPR Article 4 (personal data definition)

PII Categories:
1. Direct Identifiers: Name, SSN, passport, driver's license
2. Quasi-Identifiers: Age, ZIP code, gender, dates
3. Sensitive Data: Health, financial, biometric

Detection Methods:
- Regex patterns (fast, high precision for structured PII)
- Context-aware detection (surrounding words improve accuracy)
- Checksum validation (SSN, credit cards, etc.)
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Tuple


class PIIType(Enum):
    """Types of PII that can be detected."""
    # Direct Identifiers
    PERSON_NAME = "PERSON_NAME"
    EMAIL = "EMAIL"
    PHONE_NUMBER = "PHONE_NUMBER"
    SSN = "SSN"                        # Social Security Number
    CREDIT_CARD = "CREDIT_CARD"
    IBAN = "IBAN"                      # International Bank Account Number
    IP_ADDRESS = "IP_ADDRESS"
    MAC_ADDRESS = "MAC_ADDRESS"
    PASSPORT = "PASSPORT"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    
    # Quasi-Identifiers
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    AGE = "AGE"
    ZIPCODE = "ZIPCODE"
    ADDRESS = "ADDRESS"
    
    # Sensitive Data
    MEDICAL_RECORD = "MEDICAL_RECORD"
    API_KEY = "API_KEY"
    AWS_KEY = "AWS_KEY"
    PASSWORD = "PASSWORD"
    CRYPTO_WALLET = "CRYPTO_WALLET"
    
    # Location
    GPS_COORDINATES = "GPS_COORDINATES"
    
    # URLs and IDs
    URL = "URL"
    USERNAME = "USERNAME"


class PIISeverity(Enum):
    """Severity levels for PII findings."""
    CRITICAL = "critical"   # Direct identifier, immediate re-identification risk
    HIGH = "high"           # Sensitive data, significant privacy risk
    MEDIUM = "medium"       # Quasi-identifier, re-identification when combined
    LOW = "low"             # Minimal risk, contextual sensitivity


@dataclass
class PIIMatch:
    """A detected PII instance."""
    pii_type: PIIType
    severity: PIISeverity
    value: str              # The matched text (may be redacted for display)
    start: int              # Start position in text
    end: int                # End position in text
    confidence: float       # 0.0 to 1.0
    context: str = ""       # Surrounding text for context
    field_name: str = ""    # Column/field where found
    row_index: int = -1     # Row index if applicable
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.pii_type.value,
            "severity": self.severity.value,
            "value_preview": self._redact(self.value),
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "field_name": self.field_name,
            "row_index": self.row_index,
        }
    
    def _redact(self, value: str, show_chars: int = 4) -> str:
        """Partially redact the value for display."""
        if len(value) <= show_chars:
            return "*" * len(value)
        return value[:show_chars] + "*" * (len(value) - show_chars)


@dataclass
class PIIPattern:
    """A pattern for detecting PII."""
    pii_type: PIIType
    severity: PIISeverity
    pattern: Pattern
    confidence: float = 0.85
    validator: Optional[Callable[[str], bool]] = None  # Additional validation
    context_patterns: List[str] = field(default_factory=list)  # Boost confidence if context matches


@dataclass
class PIIScanResult:
    """Result of scanning content for PII."""
    total_matches: int = 0
    matches_by_type: Dict[str, int] = field(default_factory=dict)
    matches_by_severity: Dict[str, int] = field(default_factory=dict)
    matches_by_field: Dict[str, int] = field(default_factory=dict)
    sample_matches: List[PIIMatch] = field(default_factory=list)  # First N matches
    fields_with_pii: Set[str] = field(default_factory=set)
    high_risk_fields: Set[str] = field(default_factory=set)  # Fields with CRITICAL/HIGH PII
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_matches": self.total_matches,
            "matches_by_type": self.matches_by_type,
            "matches_by_severity": self.matches_by_severity,
            "matches_by_field": self.matches_by_field,
            "fields_with_pii": list(self.fields_with_pii),
            "high_risk_fields": list(self.high_risk_fields),
            "sample_matches": [m.to_dict() for m in self.sample_matches[:10]],
        }
    
    def has_critical_pii(self) -> bool:
        """Check if any critical PII was found."""
        return self.matches_by_severity.get("critical", 0) > 0
    
    def has_high_risk_pii(self) -> bool:
        """Check if any high-risk PII was found."""
        return (
            self.matches_by_severity.get("critical", 0) > 0 or
            self.matches_by_severity.get("high", 0) > 0
        )
    
    @property  
    def summary(self) -> str:
        """Human-readable summary."""
        if self.total_matches == 0:
            return "No PII detected"
        
        lines = [f"Found {self.total_matches} PII instance(s):"]
        for sev in ["critical", "high", "medium", "low"]:
            count = self.matches_by_severity.get(sev, 0)
            if count > 0:
                lines.append(f"  • {sev.upper()}: {count}")
        
        if self.high_risk_fields:
            lines.append(f"  ⚠ High-risk fields: {', '.join(self.high_risk_fields)}")
        
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def validate_luhn(card_number: str) -> bool:
    """
    Validate credit card using Luhn algorithm.
    
    Used by Visa, MasterCard, American Express, etc.
    """
    digits = [int(d) for d in re.sub(r'\D', '', card_number)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    
    # Luhn checksum
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    
    return checksum % 10 == 0


def validate_ssn(ssn: str) -> bool:
    """
    Validate US Social Security Number format.
    
    SSN format: AAA-BB-CCCC
    - AAA: Area number (001-899, excluding 666)
    - BB: Group number (01-99)
    - CCCC: Serial number (0001-9999)
    """
    clean = re.sub(r'\D', '', ssn)
    if len(clean) != 9:
        return False
    
    area = int(clean[:3])
    group = int(clean[3:5])
    serial = int(clean[5:])
    
    # Invalid patterns
    if area == 0 or area == 666 or area >= 900:
        return False
    if group == 0:
        return False
    if serial == 0:
        return False
    
    # Known invalid SSNs (advertising, testing)
    invalid_ssns = {
        "078051120",  # Woolworth promotional
        "219099999",  # Advertising
    }
    if clean in invalid_ssns:
        return False
    
    return True


def validate_iban(iban: str) -> bool:
    """
    Validate IBAN using MOD-97 checksum.
    """
    clean = re.sub(r'\s', '', iban).upper()
    if len(clean) < 15 or len(clean) > 34:
        return False
    
    # Move country code and check digits to end
    rearranged = clean[4:] + clean[:4]
    
    # Convert letters to numbers (A=10, B=11, etc.)
    numeric = ""
    for char in rearranged:
        if char.isdigit():
            numeric += char
        else:
            numeric += str(ord(char) - ord('A') + 10)
    
    # MOD 97 check
    return int(numeric) % 97 == 1


# ═══════════════════════════════════════════════════════════════════════════════
# PII PATTERNS (Based on Microsoft Presidio)
# ═══════════════════════════════════════════════════════════════════════════════

PII_PATTERNS: List[PIIPattern] = [
    # Email - RFC 5322 simplified
    PIIPattern(
        pii_type=PIIType.EMAIL,
        severity=PIISeverity.HIGH,
        pattern=re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        ),
        confidence=0.95,
        context_patterns=["email", "e-mail", "contact", "mail"],
    ),
    
    # Phone Number - International formats
    PIIPattern(
        pii_type=PIIType.PHONE_NUMBER,
        severity=PIISeverity.MEDIUM,
        pattern=re.compile(
            r'''
            (?:
                \+?1?[-.\s]?                           # Country code
                \(?[2-9]\d{2}\)?[-.\s]?                # Area code
                [2-9]\d{2}[-.\s]?                      # Exchange
                \d{4}                                   # Subscriber
            |
                \+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]? # International
                \d{1,4}[-.\s]?\d{1,9}
            )
            ''',
            re.VERBOSE
        ),
        confidence=0.75,
        context_patterns=["phone", "tel", "mobile", "cell", "call", "fax"],
    ),
    
    # SSN - US Social Security Number
    PIIPattern(
        pii_type=PIIType.SSN,
        severity=PIISeverity.CRITICAL,
        pattern=re.compile(
            r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b'
        ),
        confidence=0.85,
        validator=validate_ssn,
        context_patterns=["ssn", "social security", "tax id", "taxpayer"],
    ),
    
    # Credit Card - Major card formats
    PIIPattern(
        pii_type=PIIType.CREDIT_CARD,
        severity=PIISeverity.CRITICAL,
        pattern=re.compile(
            r'''
            \b(?:
                4[0-9]{12}(?:[0-9]{3})?               # Visa
            |
                5[1-5][0-9]{14}                       # MasterCard
            |
                3[47][0-9]{13}                        # American Express
            |
                6(?:011|5[0-9]{2})[0-9]{12}           # Discover
            |
                (?:2131|1800|35\d{3})\d{11}           # JCB
            )\b
            |
            \b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b  # Spaced format
            ''',
            re.VERBOSE
        ),
        confidence=0.90,
        validator=validate_luhn,
        context_patterns=["card", "credit", "visa", "mastercard", "amex", "payment"],
    ),
    
    # IP Address - IPv4
    PIIPattern(
        pii_type=PIIType.IP_ADDRESS,
        severity=PIISeverity.MEDIUM,
        pattern=re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        ),
        confidence=0.90,
        context_patterns=["ip", "address", "server", "host", "client"],
    ),
    
    # IP Address - IPv6
    PIIPattern(
        pii_type=PIIType.IP_ADDRESS,
        severity=PIISeverity.MEDIUM,
        pattern=re.compile(
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'
        ),
        confidence=0.90,
    ),
    
    # MAC Address
    PIIPattern(
        pii_type=PIIType.MAC_ADDRESS,
        severity=PIISeverity.LOW,
        pattern=re.compile(
            r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'
        ),
        confidence=0.95,
    ),
    
    # IBAN - International Bank Account Number
    PIIPattern(
        pii_type=PIIType.IBAN,
        severity=PIISeverity.CRITICAL,
        pattern=re.compile(
            r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]?){0,16}\b',
            re.IGNORECASE
        ),
        confidence=0.85,
        validator=validate_iban,
        context_patterns=["iban", "bank", "account", "transfer"],
    ),
    
    # API Key patterns
    PIIPattern(
        pii_type=PIIType.API_KEY,
        severity=PIISeverity.CRITICAL,
        pattern=re.compile(
            r'''
            (?:
                sk[-_]live[-_][a-zA-Z0-9]{24,}       # Stripe
            |
                sk[-_]test[-_][a-zA-Z0-9]{24,}       # Stripe test
            |
                pk[-_]live[-_][a-zA-Z0-9]{24,}       # Stripe public
            |
                ghp_[a-zA-Z0-9]{36}                   # GitHub PAT
            |
                gho_[a-zA-Z0-9]{36}                   # GitHub OAuth
            |
                github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}  # GitHub fine-grained
            |
                xox[baprs]-[a-zA-Z0-9-]{10,}         # Slack
            |
                ya29\.[a-zA-Z0-9_-]+                  # Google OAuth
            )
            ''',
            re.VERBOSE
        ),
        confidence=0.95,
        context_patterns=["api", "key", "token", "secret", "auth"],
    ),
    
    # AWS Access Key
    PIIPattern(
        pii_type=PIIType.AWS_KEY,
        severity=PIISeverity.CRITICAL,
        pattern=re.compile(
            r'\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b'
        ),
        confidence=0.95,
        context_patterns=["aws", "amazon", "key", "access"],
    ),
    
    # Crypto Wallet - Bitcoin
    PIIPattern(
        pii_type=PIIType.CRYPTO_WALLET,
        severity=PIISeverity.HIGH,
        pattern=re.compile(
            r'\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b'
        ),
        confidence=0.80,
        context_patterns=["bitcoin", "btc", "wallet", "crypto"],
    ),
    
    # Crypto Wallet - Ethereum
    PIIPattern(
        pii_type=PIIType.CRYPTO_WALLET,
        severity=PIISeverity.HIGH,
        pattern=re.compile(
            r'\b0x[a-fA-F0-9]{40}\b'
        ),
        confidence=0.80,
        context_patterns=["ethereum", "eth", "wallet", "crypto"],
    ),
    
    # GPS Coordinates
    PIIPattern(
        pii_type=PIIType.GPS_COORDINATES,
        severity=PIISeverity.MEDIUM,
        pattern=re.compile(
            r'[-+]?(?:[1-8]?\d(?:\.\d+)?|90(?:\.0+)?)\s*,\s*[-+]?(?:180(?:\.0+)?|(?:(?:1[0-7]\d)|(?:[1-9]?\d))(?:\.\d+)?)'
        ),
        confidence=0.70,
        context_patterns=["location", "coordinates", "lat", "lng", "gps"],
    ),
    
    # Date of Birth patterns
    PIIPattern(
        pii_type=PIIType.DATE_OF_BIRTH,
        severity=PIISeverity.MEDIUM,
        pattern=re.compile(
            r'\b(?:0?[1-9]|1[0-2])[/\-.](?:0?[1-9]|[12]\d|3[01])[/\-.](?:19|20)\d{2}\b'
        ),
        confidence=0.60,  # Low base - needs context
        context_patterns=["birth", "dob", "born", "birthday", "date of birth"],
    ),
    
    # US ZIP Code
    PIIPattern(
        pii_type=PIIType.ZIPCODE,
        severity=PIISeverity.LOW,
        pattern=re.compile(
            r'\b\d{5}(?:-\d{4})?\b'
        ),
        confidence=0.50,  # Low - needs context
        context_patterns=["zip", "postal", "address", "code"],
    ),
    
    # URL (can contain sensitive info in path/query)
    PIIPattern(
        pii_type=PIIType.URL,
        severity=PIISeverity.LOW,
        pattern=re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            re.IGNORECASE
        ),
        confidence=0.70,
    ),
]


class PIIScanner:
    """
    Scanner for detecting PII in text and datasets.
    
    Uses regex patterns with optional validation and context boosting.
    """
    
    def __init__(
        self,
        patterns: List[PIIPattern] = None,
        min_confidence: float = 0.5,
        context_boost: float = 0.1,
    ):
        """
        Initialize scanner.
        
        Args:
            patterns: Custom patterns (defaults to PII_PATTERNS)
            min_confidence: Minimum confidence to report (0.0-1.0)
            context_boost: Confidence boost when context matches
        """
        self.patterns = patterns or PII_PATTERNS
        self.min_confidence = min_confidence
        self.context_boost = context_boost
    
    def scan_text(
        self,
        text: str,
        field_name: str = "",
        row_index: int = -1,
    ) -> List[PIIMatch]:
        """
        Scan text for PII.
        
        Args:
            text: Text to scan
            field_name: Optional field name for tracking
            row_index: Optional row index for tracking
        
        Returns:
            List of PIIMatch objects
        """
        if not text or not isinstance(text, str):
            return []
        
        matches = []
        text_lower = text.lower()
        
        for pattern in self.patterns:
            for match in pattern.pattern.finditer(text):
                value = match.group()
                confidence = pattern.confidence
                
                # Validate if validator provided
                if pattern.validator:
                    if not pattern.validator(value):
                        continue
                
                # Context boost
                if pattern.context_patterns:
                    for ctx in pattern.context_patterns:
                        if ctx in text_lower:
                            confidence = min(1.0, confidence + self.context_boost)
                            break
                
                # Apply minimum confidence filter
                if confidence >= self.min_confidence:
                    # Get surrounding context (50 chars each side)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]
                    
                    matches.append(PIIMatch(
                        pii_type=pattern.pii_type,
                        severity=pattern.severity,
                        value=value,
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                        context=context,
                        field_name=field_name,
                        row_index=row_index,
                    ))
        
        return matches
    
    def scan_dict(
        self,
        data: Dict[str, List[Any]],
        sample_size: int = 1000,
    ) -> PIIScanResult:
        """
        Scan a columnar dict for PII.
        
        Args:
            data: Dict of column_name -> values
            sample_size: Max rows to scan per column
        
        Returns:
            PIIScanResult with aggregated findings
        """
        result = PIIScanResult()
        
        for field_name, values in data.items():
            if not values:
                continue
            
            # Sample values
            sample = values[:sample_size]
            
            for row_idx, value in enumerate(sample):
                if not isinstance(value, str):
                    value = str(value) if value is not None else ""
                
                matches = self.scan_text(value, field_name, row_idx)
                
                for match in matches:
                    result.total_matches += 1
                    
                    # Count by type
                    type_name = match.pii_type.value
                    result.matches_by_type[type_name] = result.matches_by_type.get(type_name, 0) + 1
                    
                    # Count by severity
                    sev = match.severity.value
                    result.matches_by_severity[sev] = result.matches_by_severity.get(sev, 0) + 1
                    
                    # Count by field
                    result.matches_by_field[field_name] = result.matches_by_field.get(field_name, 0) + 1
                    
                    # Track fields
                    result.fields_with_pii.add(field_name)
                    if match.severity in [PIISeverity.CRITICAL, PIISeverity.HIGH]:
                        result.high_risk_fields.add(field_name)
                    
                    # Keep samples
                    if len(result.sample_matches) < 100:
                        result.sample_matches.append(match)
        
        return result
    
    def scan_dataset(
        self,
        dataset,
        sample_size: int = 1000,
    ) -> PIIScanResult:
        """
        Scan a HuggingFace Dataset or DatasetDict for PII.
        
        Args:
            dataset: HuggingFace Dataset or DatasetDict
            sample_size: Max rows to scan
        
        Returns:
            PIIScanResult with aggregated findings
        """
        # Handle DatasetDict (multiple splits)
        if hasattr(dataset, 'keys') and callable(dataset.keys):
            combined = PIIScanResult()
            for split_name in dataset.keys():
                split_result = self.scan_dataset(dataset[split_name], sample_size)
                # Merge results
                combined.total_matches += split_result.total_matches
                for k, v in split_result.matches_by_type.items():
                    combined.matches_by_type[k] = combined.matches_by_type.get(k, 0) + v
                for k, v in split_result.matches_by_severity.items():
                    combined.matches_by_severity[k] = combined.matches_by_severity.get(k, 0) + v
                for k, v in split_result.matches_by_field.items():
                    combined.matches_by_field[k] = combined.matches_by_field.get(k, 0) + v
                combined.fields_with_pii.update(split_result.fields_with_pii)
                combined.high_risk_fields.update(split_result.high_risk_fields)
                combined.sample_matches.extend(split_result.sample_matches[:20])
            return combined
        
        # Single Dataset
        result = PIIScanResult()
        
        # Get column names
        if hasattr(dataset, 'features'):
            columns = list(dataset.features.keys())
        elif hasattr(dataset, 'column_names'):
            columns = dataset.column_names
        else:
            return result
        
        # Sample rows
        num_rows = len(dataset) if hasattr(dataset, '__len__') else sample_size
        sample_indices = range(min(sample_size, num_rows))
        
        for idx in sample_indices:
            row = dataset[idx]
            for col in columns:
                value = row.get(col) if isinstance(row, dict) else getattr(row, col, None)
                if not isinstance(value, str):
                    value = str(value) if value is not None else ""
                
                matches = self.scan_text(value, col, idx)
                
                for match in matches:
                    result.total_matches += 1
                    
                    type_name = match.pii_type.value
                    result.matches_by_type[type_name] = result.matches_by_type.get(type_name, 0) + 1
                    
                    sev = match.severity.value
                    result.matches_by_severity[sev] = result.matches_by_severity.get(sev, 0) + 1
                    
                    result.matches_by_field[col] = result.matches_by_field.get(col, 0) + 1
                    
                    result.fields_with_pii.add(col)
                    if match.severity in [PIISeverity.CRITICAL, PIISeverity.HIGH]:
                        result.high_risk_fields.add(col)
                    
                    if len(result.sample_matches) < 100:
                        result.sample_matches.append(match)
        
        return result


# Singleton scanner
_scanner = PIIScanner()


def scan_for_pii(
    data,
    sample_size: int = 1000,
    min_confidence: float = 0.5,
) -> PIIScanResult:
    """
    Convenience function to scan data for PII.
    
    Args:
        data: Text, dict, or HuggingFace Dataset
        sample_size: Max rows to scan
        min_confidence: Minimum confidence threshold
    
    Returns:
        PIIScanResult with findings
    """
    scanner = PIIScanner(min_confidence=min_confidence)
    
    if isinstance(data, str):
        matches = scanner.scan_text(data)
        result = PIIScanResult(
            total_matches=len(matches),
            sample_matches=matches,
        )
        for m in matches:
            result.matches_by_type[m.pii_type.value] = result.matches_by_type.get(m.pii_type.value, 0) + 1
            result.matches_by_severity[m.severity.value] = result.matches_by_severity.get(m.severity.value, 0) + 1
        return result
    
    if isinstance(data, dict):
        return scanner.scan_dict(data, sample_size)
    
    # Assume HuggingFace Dataset
    return scanner.scan_dataset(data, sample_size)


def quick_pii_check(data, sample_size: int = 100) -> bool:
    """
    Quick check if data contains any PII.
    
    Returns True if PII is found, False otherwise.
    """
    result = scan_for_pii(data, sample_size=sample_size, min_confidence=0.7)
    return result.total_matches > 0
