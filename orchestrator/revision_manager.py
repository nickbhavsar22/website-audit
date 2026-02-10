"""Revision cycle manager for agent self-auditing."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from .context_store import ContextStore, AgentStatus


@dataclass
class RevisionRequest:
    """Request for an agent to revise its analysis."""
    agent_name: str
    reason: str
    suggested_improvements: List[str]
    requested_at: str = ""
    priority: int = 1  # 1=high, 2=medium, 3=low


@dataclass
class RevisionResult:
    """Result of a revision attempt."""
    agent_name: str
    cycle: int
    success: bool
    improvements_made: List[str]
    remaining_issues: List[str]
    completed_at: str = ""


class RevisionManager:
    """
    Manages revision cycles for agent self-auditing.

    The CritiqueAgent can request revisions from other agents.
    This manager tracks revision requests and results.
    """

    def __init__(self, max_revisions: int = 3):
        self.max_revisions = max_revisions
        self.revision_requests: Dict[str, List[RevisionRequest]] = {}
        self.revision_results: Dict[str, List[RevisionResult]] = {}
        self.current_cycle: int = 0

    def can_request_revision(self, agent_name: str) -> bool:
        """Check if an agent can be requested to revise."""
        results = self.revision_results.get(agent_name, [])
        return len(results) < self.max_revisions

    def request_revision(
        self,
        agent_name: str,
        reason: str,
        suggested_improvements: List[str],
        priority: int = 1
    ) -> Optional[RevisionRequest]:
        """
        Request a revision from an agent.

        Returns the request if valid, None if max revisions reached.
        """
        if not self.can_request_revision(agent_name):
            return None

        request = RevisionRequest(
            agent_name=agent_name,
            reason=reason,
            suggested_improvements=suggested_improvements,
            requested_at=datetime.now().isoformat(),
            priority=priority
        )

        if agent_name not in self.revision_requests:
            self.revision_requests[agent_name] = []
        self.revision_requests[agent_name].append(request)

        return request

    def record_revision_result(
        self,
        agent_name: str,
        success: bool,
        improvements_made: List[str],
        remaining_issues: List[str] = None
    ) -> RevisionResult:
        """Record the result of a revision attempt."""
        if agent_name not in self.revision_results:
            self.revision_results[agent_name] = []

        cycle = len(self.revision_results[agent_name]) + 1

        result = RevisionResult(
            agent_name=agent_name,
            cycle=cycle,
            success=success,
            improvements_made=improvements_made,
            remaining_issues=remaining_issues or [],
            completed_at=datetime.now().isoformat()
        )

        self.revision_results[agent_name].append(result)
        return result

    def get_pending_revisions(self) -> List[RevisionRequest]:
        """Get all pending revision requests sorted by priority."""
        pending = []
        for agent_name, requests in self.revision_requests.items():
            results = self.revision_results.get(agent_name, [])
            # If fewer results than requests, there are pending revisions
            if len(requests) > len(results):
                pending.append(requests[len(results)])
        return sorted(pending, key=lambda r: r.priority)

    def get_revision_history(self, agent_name: str) -> Dict:
        """Get revision history for an agent."""
        return {
            'requests': self.revision_requests.get(agent_name, []),
            'results': self.revision_results.get(agent_name, []),
            'remaining_revisions': self.max_revisions - len(
                self.revision_results.get(agent_name, [])
            )
        }

    def start_new_cycle(self):
        """Start a new revision cycle."""
        self.current_cycle += 1

    def get_cycle_summary(self) -> Dict:
        """Get summary of the current revision state."""
        total_requests = sum(len(r) for r in self.revision_requests.values())
        total_results = sum(len(r) for r in self.revision_results.values())
        successful = sum(
            1 for results in self.revision_results.values()
            for r in results if r.success
        )

        return {
            'current_cycle': self.current_cycle,
            'max_revisions': self.max_revisions,
            'total_revision_requests': total_requests,
            'total_revisions_completed': total_results,
            'successful_revisions': successful,
            'pending_revisions': len(self.get_pending_revisions()),
            'agents_revised': list(self.revision_results.keys())
        }

    def should_continue_revising(self, context: ContextStore) -> bool:
        """
        Determine if revision cycles should continue.

        Returns False if:
        - Max revisions reached for all flagged agents
        - All analyses pass self-audit
        - No pending revision requests
        """
        if self.current_cycle >= self.max_revisions:
            return False

        pending = self.get_pending_revisions()
        if not pending:
            return False

        # Check if any pending agent can still be revised
        for request in pending:
            if self.can_request_revision(request.agent_name):
                return True

        return False

    def get_critique_summary_for_agent(self, agent_name: str) -> str:
        """Generate a summary of critique feedback for an agent."""
        history = self.get_revision_history(agent_name)

        if not history['requests']:
            return "No revision requests for this agent."

        summary_parts = []
        for i, request in enumerate(history['requests'], 1):
            summary_parts.append(f"Revision {i} requested: {request.reason}")
            if i <= len(history['results']):
                result = history['results'][i - 1]
                if result.success:
                    summary_parts.append(f"  -> Resolved: {', '.join(result.improvements_made)}")
                else:
                    summary_parts.append(f"  -> Partial: {', '.join(result.remaining_issues)}")

        return '\n'.join(summary_parts)
