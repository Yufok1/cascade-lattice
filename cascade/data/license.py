"""
SPDX License Tracking for CASCADE

Industry standard license tracking based on:
- SPDX (Software Package Data Exchange) - Linux Foundation
- HuggingFace Dataset Cards license field
- Croissant metadata license property

License Compatibility Rules:
- Permissive (MIT, Apache-2.0) → Can derive into restrictive
- Copyleft (GPL-3.0) → Derivatives must also be copyleft
- NonCommercial (CC-BY-NC-*) → Propagates non-commercial restriction
- ShareAlike (CC-BY-SA-*) → Derivatives must use same license
- NoDerivatives (CC-BY-ND-*) → Cannot create derivatives

References:
- https://spdx.org/licenses/
- https://creativecommons.org/licenses/
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any


class LicenseCategory(Enum):
    """License categories for compatibility analysis."""
    PERMISSIVE = "permissive"           # MIT, Apache, BSD
    WEAK_COPYLEFT = "weak-copyleft"     # LGPL, MPL
    STRONG_COPYLEFT = "strong-copyleft" # GPL, AGPL
    CREATIVE_COMMONS = "creative-commons"
    PUBLIC_DOMAIN = "public-domain"     # CC0, Unlicense
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


class LicenseRestriction(Enum):
    """License restrictions that propagate to derivatives."""
    NONE = "none"
    ATTRIBUTION = "attribution"          # Must credit original
    SHARE_ALIKE = "share-alike"         # Derivatives same license
    NON_COMMERCIAL = "non-commercial"   # No commercial use
    NO_DERIVATIVES = "no-derivatives"   # Cannot modify
    COPYLEFT = "copyleft"               # Must open source derivatives


@dataclass
class SPDXLicense:
    """
    SPDX License Information.
    
    Based on SPDX License List: https://spdx.org/licenses/
    """
    id: str                              # SPDX identifier (e.g., "MIT", "Apache-2.0")
    name: str                            # Full name
    category: LicenseCategory = LicenseCategory.UNKNOWN
    restrictions: Set[LicenseRestriction] = field(default_factory=set)
    osi_approved: bool = False           # Open Source Initiative approved
    fsf_libre: bool = False              # FSF Free/Libre
    url: Optional[str] = None            # License text URL
    
    def allows_commercial(self) -> bool:
        """Check if license allows commercial use."""
        return LicenseRestriction.NON_COMMERCIAL not in self.restrictions
    
    def allows_derivatives(self) -> bool:
        """Check if license allows creating derivatives."""
        return LicenseRestriction.NO_DERIVATIVES not in self.restrictions
    
    def requires_attribution(self) -> bool:
        """Check if license requires attribution."""
        return LicenseRestriction.ATTRIBUTION in self.restrictions
    
    def requires_share_alike(self) -> bool:
        """Check if license requires same license for derivatives."""
        return (
            LicenseRestriction.SHARE_ALIKE in self.restrictions or
            LicenseRestriction.COPYLEFT in self.restrictions
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "spdx_id": self.id,
            "name": self.name,
            "category": self.category.value,
            "restrictions": [r.value for r in self.restrictions],
            "osi_approved": self.osi_approved,
            "fsf_libre": self.fsf_libre,
            "url": self.url,
        }


# SPDX License Registry - Common ML/Data licenses
SPDX_LICENSES: Dict[str, SPDXLicense] = {
    # Public Domain
    "CC0-1.0": SPDXLicense(
        id="CC0-1.0",
        name="Creative Commons Zero v1.0 Universal",
        category=LicenseCategory.PUBLIC_DOMAIN,
        restrictions=set(),
        osi_approved=False,
        fsf_libre=True,
        url="https://creativecommons.org/publicdomain/zero/1.0/",
    ),
    "Unlicense": SPDXLicense(
        id="Unlicense",
        name="The Unlicense",
        category=LicenseCategory.PUBLIC_DOMAIN,
        restrictions=set(),
        osi_approved=True,
        fsf_libre=True,
        url="https://unlicense.org/",
    ),
    
    # Permissive
    "MIT": SPDXLicense(
        id="MIT",
        name="MIT License",
        category=LicenseCategory.PERMISSIVE,
        restrictions={LicenseRestriction.ATTRIBUTION},
        osi_approved=True,
        fsf_libre=True,
        url="https://opensource.org/licenses/MIT",
    ),
    "Apache-2.0": SPDXLicense(
        id="Apache-2.0",
        name="Apache License 2.0",
        category=LicenseCategory.PERMISSIVE,
        restrictions={LicenseRestriction.ATTRIBUTION},
        osi_approved=True,
        fsf_libre=True,
        url="https://www.apache.org/licenses/LICENSE-2.0",
    ),
    "BSD-2-Clause": SPDXLicense(
        id="BSD-2-Clause",
        name='BSD 2-Clause "Simplified" License',
        category=LicenseCategory.PERMISSIVE,
        restrictions={LicenseRestriction.ATTRIBUTION},
        osi_approved=True,
        fsf_libre=True,
        url="https://opensource.org/licenses/BSD-2-Clause",
    ),
    "BSD-3-Clause": SPDXLicense(
        id="BSD-3-Clause",
        name='BSD 3-Clause "New" or "Revised" License',
        category=LicenseCategory.PERMISSIVE,
        restrictions={LicenseRestriction.ATTRIBUTION},
        osi_approved=True,
        fsf_libre=True,
        url="https://opensource.org/licenses/BSD-3-Clause",
    ),
    
    # Creative Commons
    "CC-BY-4.0": SPDXLicense(
        id="CC-BY-4.0",
        name="Creative Commons Attribution 4.0",
        category=LicenseCategory.CREATIVE_COMMONS,
        restrictions={LicenseRestriction.ATTRIBUTION},
        osi_approved=False,
        fsf_libre=True,
        url="https://creativecommons.org/licenses/by/4.0/",
    ),
    "CC-BY-SA-4.0": SPDXLicense(
        id="CC-BY-SA-4.0",
        name="Creative Commons Attribution ShareAlike 4.0",
        category=LicenseCategory.CREATIVE_COMMONS,
        restrictions={LicenseRestriction.ATTRIBUTION, LicenseRestriction.SHARE_ALIKE},
        osi_approved=False,
        fsf_libre=True,
        url="https://creativecommons.org/licenses/by-sa/4.0/",
    ),
    "CC-BY-NC-4.0": SPDXLicense(
        id="CC-BY-NC-4.0",
        name="Creative Commons Attribution NonCommercial 4.0",
        category=LicenseCategory.CREATIVE_COMMONS,
        restrictions={LicenseRestriction.ATTRIBUTION, LicenseRestriction.NON_COMMERCIAL},
        osi_approved=False,
        fsf_libre=False,
        url="https://creativecommons.org/licenses/by-nc/4.0/",
    ),
    "CC-BY-NC-SA-4.0": SPDXLicense(
        id="CC-BY-NC-SA-4.0",
        name="Creative Commons Attribution NonCommercial ShareAlike 4.0",
        category=LicenseCategory.CREATIVE_COMMONS,
        restrictions={
            LicenseRestriction.ATTRIBUTION,
            LicenseRestriction.NON_COMMERCIAL,
            LicenseRestriction.SHARE_ALIKE,
        },
        osi_approved=False,
        fsf_libre=False,
        url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
    ),
    "CC-BY-ND-4.0": SPDXLicense(
        id="CC-BY-ND-4.0",
        name="Creative Commons Attribution NoDerivatives 4.0",
        category=LicenseCategory.CREATIVE_COMMONS,
        restrictions={LicenseRestriction.ATTRIBUTION, LicenseRestriction.NO_DERIVATIVES},
        osi_approved=False,
        fsf_libre=False,
        url="https://creativecommons.org/licenses/by-nd/4.0/",
    ),
    
    # Weak Copyleft
    "LGPL-3.0": SPDXLicense(
        id="LGPL-3.0",
        name="GNU Lesser General Public License v3.0",
        category=LicenseCategory.WEAK_COPYLEFT,
        restrictions={LicenseRestriction.ATTRIBUTION, LicenseRestriction.COPYLEFT},
        osi_approved=True,
        fsf_libre=True,
        url="https://www.gnu.org/licenses/lgpl-3.0.html",
    ),
    "MPL-2.0": SPDXLicense(
        id="MPL-2.0",
        name="Mozilla Public License 2.0",
        category=LicenseCategory.WEAK_COPYLEFT,
        restrictions={LicenseRestriction.ATTRIBUTION, LicenseRestriction.COPYLEFT},
        osi_approved=True,
        fsf_libre=True,
        url="https://www.mozilla.org/en-US/MPL/2.0/",
    ),
    
    # Strong Copyleft
    "GPL-3.0": SPDXLicense(
        id="GPL-3.0",
        name="GNU General Public License v3.0",
        category=LicenseCategory.STRONG_COPYLEFT,
        restrictions={LicenseRestriction.ATTRIBUTION, LicenseRestriction.COPYLEFT},
        osi_approved=True,
        fsf_libre=True,
        url="https://www.gnu.org/licenses/gpl-3.0.html",
    ),
    "AGPL-3.0": SPDXLicense(
        id="AGPL-3.0",
        name="GNU Affero General Public License v3.0",
        category=LicenseCategory.STRONG_COPYLEFT,
        restrictions={LicenseRestriction.ATTRIBUTION, LicenseRestriction.COPYLEFT},
        osi_approved=True,
        fsf_libre=True,
        url="https://www.gnu.org/licenses/agpl-3.0.html",
    ),
    
    # ML-Specific
    "OpenRAIL": SPDXLicense(
        id="OpenRAIL",
        name="Open RAIL License",
        category=LicenseCategory.PERMISSIVE,
        restrictions={LicenseRestriction.ATTRIBUTION},
        osi_approved=False,
        fsf_libre=False,
        url="https://huggingface.co/blog/open_rail",
    ),
    "OpenRAIL-M": SPDXLicense(
        id="OpenRAIL-M",
        name="Open RAIL-M License",
        category=LicenseCategory.PERMISSIVE,
        restrictions={LicenseRestriction.ATTRIBUTION},
        osi_approved=False,
        fsf_libre=False,
        url="https://www.licenses.ai/blog/2022/8/26/bigscience-open-rail-m-license",
    ),
    
    # Special
    "other": SPDXLicense(
        id="other",
        name="Other/Custom License",
        category=LicenseCategory.UNKNOWN,
        restrictions=set(),
        osi_approved=False,
        fsf_libre=False,
        url=None,
    ),
    "unknown": SPDXLicense(
        id="unknown",
        name="Unknown License",
        category=LicenseCategory.UNKNOWN,
        restrictions=set(),
        osi_approved=False,
        fsf_libre=False,
        url=None,
    ),
}


def get_license(spdx_id: str) -> SPDXLicense:
    """
    Get license by SPDX identifier.
    
    Args:
        spdx_id: SPDX license identifier (case-insensitive)
    
    Returns:
        SPDXLicense object (unknown if not found)
    """
    # Normalize common variants
    normalized = spdx_id.strip()
    
    # Direct lookup
    if normalized in SPDX_LICENSES:
        return SPDX_LICENSES[normalized]
    
    # Case-insensitive lookup
    for key, license in SPDX_LICENSES.items():
        if key.lower() == normalized.lower():
            return license
    
    # Common aliases
    aliases = {
        "mit": "MIT",
        "apache": "Apache-2.0",
        "apache2": "Apache-2.0",
        "gpl": "GPL-3.0",
        "gpl3": "GPL-3.0",
        "lgpl": "LGPL-3.0",
        "bsd": "BSD-3-Clause",
        "cc0": "CC0-1.0",
        "cc-by": "CC-BY-4.0",
        "cc-by-sa": "CC-BY-SA-4.0",
        "cc-by-nc": "CC-BY-NC-4.0",
        "cc-by-nc-sa": "CC-BY-NC-SA-4.0",
        "cc-by-nd": "CC-BY-ND-4.0",
        "unlicense": "Unlicense",
        "public domain": "CC0-1.0",
        "openrail": "OpenRAIL",
    }
    
    lower_id = normalized.lower().replace("_", "-").replace(" ", "-")
    if lower_id in aliases:
        return SPDX_LICENSES[aliases[lower_id]]
    
    # Return unknown
    return SPDX_LICENSES["unknown"]


@dataclass
class LicenseCompatibility:
    """Result of license compatibility check."""
    compatible: bool
    derived_license: Optional[SPDXLicense] = None
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    attribution_required: List[str] = field(default_factory=list)  # Source IDs requiring attribution


class LicenseAnalyzer:
    """
    Analyze license compatibility for dataset derivation.
    
    Rules:
    1. No-Derivatives: Cannot create derivatives
    2. Share-Alike: Must use same license
    3. Copyleft: Must use compatible copyleft license
    4. Non-Commercial: Restriction propagates
    5. Attribution: Must credit all sources
    """
    
    # License compatibility matrix (can this → derive into that?)
    # Rows: source license category, Columns: derived license category
    COMPATIBILITY_MATRIX = {
        LicenseCategory.PUBLIC_DOMAIN: {
            LicenseCategory.PUBLIC_DOMAIN: True,
            LicenseCategory.PERMISSIVE: True,
            LicenseCategory.CREATIVE_COMMONS: True,
            LicenseCategory.WEAK_COPYLEFT: True,
            LicenseCategory.STRONG_COPYLEFT: True,
            LicenseCategory.PROPRIETARY: True,
        },
        LicenseCategory.PERMISSIVE: {
            LicenseCategory.PUBLIC_DOMAIN: False,
            LicenseCategory.PERMISSIVE: True,
            LicenseCategory.CREATIVE_COMMONS: True,
            LicenseCategory.WEAK_COPYLEFT: True,
            LicenseCategory.STRONG_COPYLEFT: True,
            LicenseCategory.PROPRIETARY: True,
        },
        LicenseCategory.CREATIVE_COMMONS: {
            LicenseCategory.PUBLIC_DOMAIN: False,
            LicenseCategory.PERMISSIVE: False,  # Depends on specific CC
            LicenseCategory.CREATIVE_COMMONS: True,  # Depends on specific CC
            LicenseCategory.WEAK_COPYLEFT: False,
            LicenseCategory.STRONG_COPYLEFT: False,
            LicenseCategory.PROPRIETARY: False,
        },
        LicenseCategory.WEAK_COPYLEFT: {
            LicenseCategory.PUBLIC_DOMAIN: False,
            LicenseCategory.PERMISSIVE: False,
            LicenseCategory.CREATIVE_COMMONS: False,
            LicenseCategory.WEAK_COPYLEFT: True,
            LicenseCategory.STRONG_COPYLEFT: True,
            LicenseCategory.PROPRIETARY: False,
        },
        LicenseCategory.STRONG_COPYLEFT: {
            LicenseCategory.PUBLIC_DOMAIN: False,
            LicenseCategory.PERMISSIVE: False,
            LicenseCategory.CREATIVE_COMMONS: False,
            LicenseCategory.WEAK_COPYLEFT: False,
            LicenseCategory.STRONG_COPYLEFT: True,
            LicenseCategory.PROPRIETARY: False,
        },
    }
    
    def check_compatibility(
        self,
        source_licenses: List[Tuple[str, str]],  # List of (entity_id, spdx_id)
        target_license: Optional[str] = None,
    ) -> LicenseCompatibility:
        """
        Check if source licenses allow derivation.
        
        Args:
            source_licenses: List of (entity_id, license_id) tuples
            target_license: Intended license for derived work (optional)
        
        Returns:
            LicenseCompatibility result
        """
        if not source_licenses:
            return LicenseCompatibility(
                compatible=True,
                derived_license=SPDX_LICENSES["unknown"],
            )
        
        issues = []
        warnings = []
        attribution_required = []
        
        # Collect all restrictions
        all_restrictions: Set[LicenseRestriction] = set()
        licenses = []
        
        for entity_id, spdx_id in source_licenses:
            lic = get_license(spdx_id)
            licenses.append((entity_id, lic))
            all_restrictions.update(lic.restrictions)
            
            # Track attribution requirements
            if lic.requires_attribution():
                attribution_required.append(entity_id)
        
        # Check No-Derivatives
        for entity_id, lic in licenses:
            if LicenseRestriction.NO_DERIVATIVES in lic.restrictions:
                issues.append(
                    f"Cannot derive from '{entity_id}': license '{lic.id}' prohibits derivatives"
                )
        
        if issues:
            return LicenseCompatibility(
                compatible=False,
                issues=issues,
                warnings=warnings,
                attribution_required=attribution_required,
            )
        
        # Determine derived license
        derived = self._compute_derived_license(licenses, all_restrictions)
        
        # Check target license compatibility
        if target_license:
            target = get_license(target_license)
            if not self._can_relicense(derived, target):
                issues.append(
                    f"Cannot license derived work as '{target.id}': "
                    f"must use '{derived.id}' or compatible license"
                )
        
        # Add warnings
        if LicenseRestriction.NON_COMMERCIAL in all_restrictions:
            warnings.append("Derived work restricted to non-commercial use only")
        
        if LicenseRestriction.SHARE_ALIKE in all_restrictions:
            warnings.append(f"Derived work must use ShareAlike-compatible license: {derived.id}")
        
        if LicenseRestriction.COPYLEFT in all_restrictions:
            warnings.append(f"Derived work must use copyleft license: {derived.id}")
        
        return LicenseCompatibility(
            compatible=len(issues) == 0,
            derived_license=derived,
            issues=issues,
            warnings=warnings,
            attribution_required=attribution_required,
        )
    
    def _compute_derived_license(
        self,
        licenses: List[Tuple[str, SPDXLicense]],
        all_restrictions: Set[LicenseRestriction],
    ) -> SPDXLicense:
        """
        Compute the most restrictive license for derived work.
        
        The derived license is the "lowest common denominator" that
        satisfies all source license requirements.
        """
        # Priority: Strong Copyleft > Weak Copyleft > CC-SA > CC-NC > Permissive > Public Domain
        
        has_strong_copyleft = any(
            lic.category == LicenseCategory.STRONG_COPYLEFT
            for _, lic in licenses
        )
        has_weak_copyleft = any(
            lic.category == LicenseCategory.WEAK_COPYLEFT
            for _, lic in licenses
        )
        has_share_alike = LicenseRestriction.SHARE_ALIKE in all_restrictions
        has_non_commercial = LicenseRestriction.NON_COMMERCIAL in all_restrictions
        
        # Strong copyleft dominates
        if has_strong_copyleft:
            for _, lic in licenses:
                if lic.category == LicenseCategory.STRONG_COPYLEFT:
                    return lic
        
        # Weak copyleft next
        if has_weak_copyleft:
            for _, lic in licenses:
                if lic.category == LicenseCategory.WEAK_COPYLEFT:
                    return lic
        
        # CC with restrictions
        if has_share_alike and has_non_commercial:
            return SPDX_LICENSES["CC-BY-NC-SA-4.0"]
        elif has_share_alike:
            return SPDX_LICENSES["CC-BY-SA-4.0"]
        elif has_non_commercial:
            return SPDX_LICENSES["CC-BY-NC-4.0"]
        
        # Most permissive with attribution
        if LicenseRestriction.ATTRIBUTION in all_restrictions:
            # Check if any source requires specific license
            for _, lic in licenses:
                if lic.category == LicenseCategory.CREATIVE_COMMONS:
                    return lic
            return SPDX_LICENSES["CC-BY-4.0"]
        
        # Public domain
        return SPDX_LICENSES["CC0-1.0"]
    
    def _can_relicense(self, source: SPDXLicense, target: SPDXLicense) -> bool:
        """Check if source license allows relicensing to target."""
        # Same license is always OK
        if source.id == target.id:
            return True
        
        # No relicensing from copyleft to non-copyleft
        if LicenseRestriction.COPYLEFT in source.restrictions:
            if LicenseRestriction.COPYLEFT not in target.restrictions:
                return False
        
        # No relicensing from share-alike to non-share-alike
        if LicenseRestriction.SHARE_ALIKE in source.restrictions:
            if LicenseRestriction.SHARE_ALIKE not in target.restrictions:
                return False
        
        # Non-commercial must propagate
        if LicenseRestriction.NON_COMMERCIAL in source.restrictions:
            if LicenseRestriction.NON_COMMERCIAL not in target.restrictions:
                return False
        
        return True
    
    def generate_attribution(
        self,
        sources: List[Tuple[str, str, str]],  # (entity_id, license_id, name)
    ) -> str:
        """
        Generate attribution text for derived work.
        
        Args:
            sources: List of (entity_id, license_id, name) tuples
        
        Returns:
            Attribution text
        """
        lines = [
            "## Attribution",
            "",
            "This dataset is derived from the following sources:",
            "",
        ]
        
        for entity_id, license_id, name in sources:
            lic = get_license(license_id)
            if lic.requires_attribution():
                line = f"- **{name}** (`{entity_id}`)"
                if lic.url:
                    line += f" - Licensed under [{lic.id}]({lic.url})"
                else:
                    line += f" - Licensed under {lic.id}"
                lines.append(line)
        
        if len(lines) == 4:  # No attributions needed
            return ""
        
        lines.append("")
        return "\n".join(lines)


# Singleton analyzer
_analyzer = LicenseAnalyzer()


def check_license_compatibility(
    sources: List[Tuple[str, str]],
    target: Optional[str] = None,
) -> LicenseCompatibility:
    """
    Convenience function to check license compatibility.
    
    Args:
        sources: List of (entity_id, license_id) tuples
        target: Intended license for derived work
    
    Returns:
        LicenseCompatibility result
    """
    return _analyzer.check_compatibility(sources, target)


def get_derived_license(sources: List[str]) -> SPDXLicense:
    """
    Get the appropriate license for a work derived from given sources.
    
    Args:
        sources: List of SPDX license identifiers
    
    Returns:
        SPDXLicense for the derived work
    """
    result = _analyzer.check_compatibility([
        (f"source_{i}", lic) for i, lic in enumerate(sources)
    ])
    return result.derived_license or SPDX_LICENSES["unknown"]
