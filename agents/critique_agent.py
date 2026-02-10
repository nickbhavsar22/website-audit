"""Critique Agent for reviewing and requesting revisions."""

from typing import List, Dict, Optional

from .base_agent import BaseAgent
from orchestrator.context_store import AgentStatus
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort


class CritiqueAgent(BaseAgent):
    """
    Final review agent that critiques other agents' work.

    Responsibilities:
    - Review all agent analyses for quality
    - Identify gaps and inconsistencies
    - Request revisions from agents that need improvement
    - Ensure overall report coherence
    """

    agent_name = "critique"
    agent_description = "Reviews and critiques all agent analyses"
    dependencies = [
        "positioning", "seo", "conversion", "content",
        "trust", "social", "segmentation", "resource_hub", "top5_pages"
    ]
    weight = 0  # No scoring weight - meta-agent

    # Minimum thresholds for passing critique
    QUALITY_THRESHOLDS = {
        "min_analysis_length": 100,  # Characters
        "min_score_items": 3,
        "min_recommendations": 2,
        "max_empty_notes": 2,  # Score items with empty notes
    }

    async def run(self) -> ModuleScore:
        """Execute critique of all agent analyses."""
        module = ModuleScore(name="Audit Critique", weight=0)

        critique_results = []
        revision_requests = []

        # Review each completed agent
        for agent_name in self.dependencies:
            analysis = self.context.get_analysis(agent_name)

            if not analysis or analysis.status != AgentStatus.COMPLETED:
                continue

            critique = self._critique_analysis(agent_name, analysis)
            critique_results.append(critique)

            if not critique['passed']:
                revision_requests.append({
                    'agent': agent_name,
                    'issues': critique['issues'],
                    'suggestions': critique['suggestions']
                })

        # Check for cross-agent consistency
        consistency_issues = self._check_consistency()
        if consistency_issues:
            critique_results.append({
                'agent': 'cross_agent',
                'passed': False,
                'issues': consistency_issues,
                'suggestions': ['Ensure messaging consistency across analyses']
            })

        # Build summary
        passed_count = sum(1 for c in critique_results if c.get('passed', False))
        total_count = len(critique_results)

        module.items.append(ScoreItem(
            name="Quality Review",
            description="Agents passing quality review",
            max_points=total_count,
            actual_points=passed_count,
            notes=f"{passed_count}/{total_count} agents passed critique"
        ))

        if revision_requests:
            module.items.append(ScoreItem(
                name="Revisions Needed",
                description="Agents requiring revision",
                max_points=0,
                actual_points=0,
                notes=f"{len(revision_requests)} agents flagged for revision"
            ))

        # Generate recommendations for revision
        for req in revision_requests:
            module.recommendations.append(Recommendation(
                issue=f"{req['agent']} analysis needs improvement: {', '.join(req['issues'][:2])}",
                recommendation=req['suggestions'][0] if req['suggestions'] else "Review and improve analysis",
                impact=Impact.MEDIUM,
                effort=Effort.LOW,
                category="Quality Assurance"
            ))

        module.analysis_text = self._generate_critique_summary(critique_results, revision_requests)

        module.raw_data = {
            'critique_results': critique_results,
            'revision_requests': revision_requests,
            'passed_count': passed_count,
            'total_count': total_count
        }

        # Request revisions through revision manager (if orchestrator provides it)
        # This would be handled by the orchestrator reading raw_data

        return module

    def _critique_analysis(self, agent_name: str, analysis) -> Dict:
        """Critique a single agent's analysis."""
        issues = []
        suggestions = []
        passed = True

        score = analysis.module_score
        if not score:
            return {
                'agent': agent_name,
                'passed': False,
                'issues': ['No module score produced'],
                'suggestions': ['Ensure agent produces valid ModuleScore']
            }

        # Check analysis text length
        if not score.analysis_text or len(score.analysis_text) < self.QUALITY_THRESHOLDS['min_analysis_length']:
            issues.append('Analysis text too short or missing')
            suggestions.append('Provide more detailed analysis explanation')
            passed = False

        # Check score items
        if len(score.items) < self.QUALITY_THRESHOLDS['min_score_items']:
            issues.append(f'Too few score items ({len(score.items)})')
            suggestions.append(f"Add more granular scoring criteria (minimum {self.QUALITY_THRESHOLDS['min_score_items']})")
            passed = False

        # Check for empty notes
        empty_notes = sum(1 for item in score.items if not item.notes or item.notes == 'Manual review recommended')
        if empty_notes > self.QUALITY_THRESHOLDS['max_empty_notes']:
            issues.append(f'{empty_notes} score items lack specific notes')
            suggestions.append('Add specific observations to each score item')

        # Check recommendations (if LLM was available)
        if self.llm.is_available() and len(score.recommendations) < self.QUALITY_THRESHOLDS['min_recommendations']:
            issues.append('Too few recommendations')
            suggestions.append(f"Provide at least {self.QUALITY_THRESHOLDS['min_recommendations']} actionable recommendations")

        # Check for suspiciously uniform scores
        if score.items:
            scores = [item.actual_points / item.max_points if item.max_points > 0 else 0 for item in score.items]
            if len(set(round(s, 1) for s in scores)) == 1 and len(scores) > 3:
                issues.append('All scores are identical - may indicate superficial analysis')
                suggestions.append('Differentiate scoring based on specific criteria')

        # Agent-specific checks
        specific_issues = self._agent_specific_critique(agent_name, score)
        issues.extend(specific_issues.get('issues', []))
        suggestions.extend(specific_issues.get('suggestions', []))
        if specific_issues.get('fail'):
            passed = False

        return {
            'agent': agent_name,
            'passed': passed and len(issues) <= 2,  # Allow up to 2 minor issues
            'issues': issues,
            'suggestions': suggestions,
            'score_percentage': score.percentage
        }

    def _agent_specific_critique(self, agent_name: str, score: ModuleScore) -> Dict:
        """Apply agent-specific critique rules."""
        result = {'issues': [], 'suggestions': [], 'fail': False}

        if agent_name == 'positioning':
            # Positioning should identify clear differentiators
            if not score.raw_data.get('strengths') and not score.raw_data.get('weaknesses'):
                result['issues'].append('No strengths/weaknesses identified')
                result['suggestions'].append('Identify specific positioning strengths and weaknesses')

        elif agent_name == 'seo':
            # SEO should have concrete metrics
            if not score.raw_data.get('avg_load_time'):
                result['issues'].append('Missing performance metrics')
                result['suggestions'].append('Include specific load time measurements')

        elif agent_name == 'competitor':
            # Competitor analysis should have comparison data
            if not score.raw_data.get('competitors'):
                result['issues'].append('No competitor data captured')
                result['fail'] = True

        elif agent_name == 'top5_pages':
            # Should have analyzed critical pages
            if not score.raw_data.get('pages_analyzed') or len(score.raw_data.get('pages_analyzed', [])) < 3:
                result['issues'].append('Too few critical pages analyzed')
                result['suggestions'].append('Ensure homepage, product, and pricing pages are analyzed')

        return result

    def _check_consistency(self) -> List[str]:
        """Check for consistency across agent analyses."""
        issues = []

        # Check that positioning insights align with content analysis
        pos_analysis = self.context.get_analysis('positioning')
        content_analysis = self.context.get_analysis('content')

        if pos_analysis and content_analysis:
            pos_score = pos_analysis.module_score
            content_score = content_analysis.module_score

            if pos_score and content_score:
                # Large score differential might indicate inconsistency
                diff = abs(pos_score.percentage - content_score.percentage)
                if diff > 30:
                    issues.append(f"Large score gap between positioning ({pos_score.percentage:.0f}%) and content ({content_score.percentage:.0f}%)")

        return issues

    def _generate_critique_summary(self, results: List[Dict], revision_requests: List[Dict]) -> str:
        """Generate summary of critique findings."""
        summary_parts = [
            "## Audit Quality Review\n",
            f"**Agents Reviewed:** {len(results)}",
            f"**Passed Quality Check:** {sum(1 for r in results if r.get('passed', False))}",
            f"**Flagged for Revision:** {len(revision_requests)}",
            ""
        ]

        if revision_requests:
            summary_parts.append("### Issues Found:\n")
            for req in revision_requests:
                summary_parts.append(f"**{req['agent'].title()}:**")
                for issue in req['issues'][:3]:
                    summary_parts.append(f"  - {issue}")
                summary_parts.append("")

        # Overall assessment
        pass_rate = sum(1 for r in results if r.get('passed', False)) / len(results) if results else 0

        if pass_rate >= 0.8:
            summary_parts.append("**Overall Assessment:** Good quality - minor improvements suggested")
        elif pass_rate >= 0.6:
            summary_parts.append("**Overall Assessment:** Acceptable - some revisions recommended")
        else:
            summary_parts.append("**Overall Assessment:** Needs improvement - multiple revisions required")

        return '\n'.join(summary_parts)

    def self_audit(self) -> bool:
        """Critique agent always passes self-audit."""
        return True
