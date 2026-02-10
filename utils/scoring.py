"""Scoring and grading utilities for marketing audit."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class AuditModule(Enum):
    """Categories for audit modules."""
    POSITIONING = "Positioning & Messaging"
    SEO = "SEO & Visibility" 
    CONVERSION = "Conversion & UX"
    CONTENT = "Content Strategy"
    TRUST = "Trust & Credibility"
    SOCIAL = "Social & Community"
    SEGMENTATION = "Segmentation"
    RESOURCE_HUB = "Resource Hub"
    TOP_PAGES = "Critical Pages"
    COMPETITOR = "Competitive Landscape"


class Grade(Enum):
    """Letter grades for assignments."""
    A_PLUS = "A+" # 97-100
    A = "A"       # 93-96
    A_MINUS = "A-"# 90-92
    B_PLUS = "B+" # 87-89
    B = "B"       # 83-86
    B_MINUS = "B-"# 80-82
    C_PLUS = "C+" # 77-79
    C = "C"       # 73-76
    C_MINUS = "C-"# 70-72
    D = "D"       # 60-69
    F = "F"       # < 60

class ConsultingOutcome(Enum):
    """Outcomes replacing simple A-F grades."""
    AUTHORITY = "Market Authority"           # A+ (95-100)
    LEADER = "Category Leader"              # A  (90-94)
    CONTENDER = "Strong Contender"          # B  (80-89)
    RISK_DILUTION = "Market Dilution Risk"  # C  (70-79) - Was Traffic but no conversion
    RISK_COMMODITY = "Commodotized Player"  # D  (60-69) - Was Content but no diff
    GAP_AUTHORITY = "Critical Authority Gap" # F  (<60)   - Was Trust Gap
    GAP_CONVERSION = "Revenue Leak"         # F  (<60)   - Was Conversion Gap
    GAP_VISIBILITY = "Invisible Player"     # F  (<60)   - Was SEO Gap


class Impact(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Effort(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class MatrixPlacement(Enum):
    """Placement in the Impact/Effort 2x2 Matrix."""
    QUICK_WIN = "Quick Win"           # High Impact, Low Effort
    STRATEGIC_BET = "Strategic Bet"   # High Impact, High Effort
    LOW_HANGING = "Low Hanging Fruit" # Low Impact, Low Effort
    DISTRACTION = "Distraction"       # Low Impact, High Effort


class KPIImpact(Enum):
    """Business KPI that a recommendation impacts."""
    CLOSE_RATE = "Close Rate"
    WEBSITE_TRAFFIC = "Website Traffic"
    LEAD_CONVERSION = "Lead Conversion"
    PIPELINE_VELOCITY = "Pipeline Velocity"
    BRAND_AWARENESS = "Brand Awareness"
    CUSTOMER_TRUST = "Customer Trust"
    ENGAGEMENT = "Engagement"
    SEO_RANKING = "SEO Ranking"
    BOUNCE_RATE = "Bounce Rate"
    TIME_ON_SITE = "Time on Site"


@dataclass
class Recommendation:
    """A single recommendation with impact/effort scoring."""
    issue: str
    recommendation: str
    impact: Impact
    effort: Effort
    business_impact: str = ""   # The "So What?" statement
    category: str = ""
    page_url: str = ""
    kpi_impact: Optional[KPIImpact] = None

    @property
    def priority_score(self) -> int:
        """Calculate priority score (higher is better)."""
        impact_scores = {Impact.HIGH: 3, Impact.MEDIUM: 2, Impact.LOW: 1}
        effort_scores = {Effort.HIGH: 1, Effort.MEDIUM: 2, Effort.LOW: 3}
        return impact_scores[self.impact] * effort_scores[self.effort]

    @property
    def matrix_placement(self) -> MatrixPlacement:
        """Determine placement in the 2x2 matrix."""
        if self.impact == Impact.HIGH:
            return MatrixPlacement.QUICK_WIN if self.effort == Effort.LOW else MatrixPlacement.STRATEGIC_BET
        else:
            return MatrixPlacement.LOW_HANGING if self.effort == Effort.LOW else MatrixPlacement.DISTRACTION

    @property
    def priority_stars(self) -> str:
        """Return star rating for priority."""
        score = self.priority_score
        if score >= 9:
            return "★★★★★"
        elif score >= 6:
            return "★★★★"
        elif score >= 4:
            return "★★★"
        elif score >= 2:
            return "★★"
        else:
            return "★"


@dataclass
class ScoreItem:
    """Individual scoring criterion."""
    name: str
    description: str
    max_points: int
    actual_points: int = 0
    notes: str = ""
    recommendation: str = ""  # Specific fix for this item
    business_impact: str = "" # The "So What" of this specific score item
    page_url: str = ""        # Specific page URL where the issue was observed


@dataclass
class ModuleScore:
    """Score for an entire audit module."""
    name: str
    weight: float = 1.0
    items: List[ScoreItem] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    analysis_text: str = ""
    raw_data: Dict = field(default_factory=dict)

    @property
    def max_points(self) -> int:
        return sum(item.max_points for item in self.items)

    @property
    def actual_points(self) -> int:
        return sum(item.actual_points for item in self.items)

    @property
    def percentage(self) -> float:
        if self.max_points == 0:
            return 0.0
        return (self.actual_points / self.max_points) * 100

    @property
    def weighted_points(self) -> float:
        return self.actual_points * self.weight

    @property
    def weighted_max(self) -> float:
        return self.max_points * self.weight

    @property
    def outcome(self) -> ConsultingOutcome:
        """Map percentage to consulting outcome."""
        pct = self.percentage
        if pct >= 95:
            return ConsultingOutcome.AUTHORITY
        elif pct >= 90:
            return ConsultingOutcome.LEADER
        elif pct >= 80:
            return ConsultingOutcome.CONTENDER
        elif pct >= 70:
            return ConsultingOutcome.RISK_DILUTION
        elif pct >= 60:
            return ConsultingOutcome.RISK_COMMODITY
        else:
            # Context-aware failure
            name_lower = self.name.lower()
            if "trust" in name_lower or "social" in name_lower:
                return ConsultingOutcome.GAP_AUTHORITY
            elif "conversion" in name_lower:
                return ConsultingOutcome.GAP_CONVERSION
            else:
                return ConsultingOutcome.GAP_VISIBILITY

    @property
    def grade(self) -> Grade:
        """Map percentage to letter grade."""
        pct = self.percentage
        if pct >= 97: return Grade.A_PLUS
        if pct >= 93: return Grade.A
        if pct >= 90: return Grade.A_MINUS
        if pct >= 87: return Grade.B_PLUS
        if pct >= 83: return Grade.B
        if pct >= 80: return Grade.B_MINUS
        if pct >= 77: return Grade.C_PLUS
        if pct >= 73: return Grade.C
        if pct >= 70: return Grade.C_MINUS
        if pct >= 60: return Grade.D
        return Grade.F

    @property
    def outcome_color(self) -> str:
        """Return color class for outcome display."""
        colors = {
            ConsultingOutcome.AUTHORITY: "#15803d",      # green-700
            ConsultingOutcome.LEADER: "#22c55e",         # green-500
            ConsultingOutcome.CONTENDER: "#84cc16",      # lime-500
            ConsultingOutcome.RISK_DILUTION: "#eab308",  # yellow-500
            ConsultingOutcome.RISK_COMMODITY: "#f97316", # orange-500
            ConsultingOutcome.GAP_AUTHORITY: "#ef4444",  # red-500
            ConsultingOutcome.GAP_CONVERSION: "#dc2626", # red-600
            ConsultingOutcome.GAP_VISIBILITY: "#b91c1c", # red-700
        }
        return colors.get(self.outcome, "#6b7280")


@dataclass
class StrategicFrictionPoint:
    """The root cause of growth stagnation identified by the Orchestrator."""
    title: str
    description: str
    primary_symptom: str
    business_impact: str


@dataclass
class AuditReport:
    """Complete audit report with all module scores."""
    company_name: str
    company_website: str
    audit_date: str
    analyst_name: str = ""
    analyst_company: str = "Bhavsar Growth Consulting"
    client_logo: str = ""
    analyst_logo: str = ""
    modules: List[ModuleScore] = field(default_factory=list)
    strategic_friction: Optional[StrategicFrictionPoint] = None

    @property
    def total_weighted_points(self) -> float:
        return sum(m.weighted_points for m in self.modules)

    def get_module_by_name(self, name: str) -> Optional[ModuleScore]:
        """Get a specific module by name."""
        for m in self.modules:
            if m.name == name:
                return m
        return None

    @property
    def total_weighted_max(self) -> float:
        return sum(m.weighted_max for m in self.modules)

    @property
    def overall_percentage(self) -> float:
        if self.total_weighted_max == 0:
            return 0.0
        return (self.total_weighted_points / self.total_weighted_max) * 100

    @property
    def overall_outcome(self) -> ConsultingOutcome:
        pct = self.overall_percentage
        if pct >= 95:
            return ConsultingOutcome.AUTHORITY
        elif pct >= 90:
            return ConsultingOutcome.LEADER
        elif pct >= 80:
            return ConsultingOutcome.CONTENDER
        elif pct >= 70:
            return ConsultingOutcome.RISK_DILUTION
        elif pct >= 60:
            return ConsultingOutcome.RISK_COMMODITY
        else:
            return ConsultingOutcome.GAP_AUTHORITY # Default fail to authority gap

    @property
    def overall_grade(self) -> Grade:
        """Map overall percentage to letter grade."""
        pct = self.overall_percentage
        if pct >= 97: return Grade.A_PLUS
        if pct >= 93: return Grade.A
        if pct >= 90: return Grade.A_MINUS
        if pct >= 87: return Grade.B_PLUS
        if pct >= 83: return Grade.B
        if pct >= 80: return Grade.B_MINUS
        if pct >= 77: return Grade.C_PLUS
        if pct >= 73: return Grade.C
        if pct >= 70: return Grade.C_MINUS
        if pct >= 60: return Grade.D
        return Grade.F

    @property
    def outcome_color(self) -> str:
        # Re-use logic from ModuleScore, could abstract
        colors = {
            ConsultingOutcome.AUTHORITY: "#15803d",
            ConsultingOutcome.LEADER: "#22c55e",
            ConsultingOutcome.CONTENDER: "#84cc16",
            ConsultingOutcome.RISK_DILUTION: "#eab308",
            ConsultingOutcome.RISK_COMMODITY: "#f97316",
            ConsultingOutcome.GAP_AUTHORITY: "#ef4444",
            ConsultingOutcome.GAP_CONVERSION: "#dc2626",
            ConsultingOutcome.GAP_VISIBILITY: "#b91c1c",
        }
        return colors.get(self.overall_outcome, "#6b7280")

    def get_all_recommendations(self) -> List[Recommendation]:
        """Get all recommendations sorted by priority."""
        all_recs = []
        for module in self.modules:
            for rec in module.recommendations:
                rec.category = module.name
                all_recs.append(rec)
        return sorted(all_recs, key=lambda r: r.priority_score, reverse=True)

    def get_matrix_recommendations(self) -> Dict[str, List[Recommendation]]:
        """Group recommendations by 2x2 matrix quadrant."""
        matrix = {
            MatrixPlacement.QUICK_WIN.value: [],
            MatrixPlacement.STRATEGIC_BET.value: [],
            MatrixPlacement.LOW_HANGING.value: [],
            MatrixPlacement.DISTRACTION.value: []
        }
        for rec in self.get_all_recommendations():
            matrix[rec.matrix_placement.value].append(rec)
        return matrix

    def get_top_strengths(self, n: int = 3) -> List[str]:
        """Get top scoring areas."""
        items = []
        for module in self.modules:
            for item in module.items:
                if item.max_points > 0:
                    pct = (item.actual_points / item.max_points) * 100
                    if pct >= 80:
                        items.append((f"{module.name}: {item.name}", pct, item.notes))
        items.sort(key=lambda x: x[1], reverse=True)
        return [f"{item[0]} - {item[2]}" if item[2] else item[0] for item in items[:n]]

    def get_critical_gaps(self, n: int = 3) -> List[str]:
        """Get lowest scoring areas."""
        items = []
        for module in self.modules:
            for item in module.items:
                if item.max_points > 0:
                    pct = (item.actual_points / item.max_points) * 100
                    if pct < 60:
                        items.append((f"{module.name}: {item.name}", pct, item.notes))
        items.sort(key=lambda x: x[1])
        return [f"{item[0]} - {item[2]}" if item[2] else item[0] for item in items[:n]]

    def get_quick_wins(self, n: int = 3) -> List[Recommendation]:
        """Get high-impact, low-effort recommendations."""
        matrix = self.get_matrix_recommendations()
        wins = matrix[MatrixPlacement.QUICK_WIN.value]
        if len(wins) < n:
            wins.extend(matrix[MatrixPlacement.LOW_HANGING.value]) # Fallback to low effort
        return wins[:n]

