"""Structured error types for the website audit system."""

class AuditError(Exception):
    """Base exception for audit errors."""
    pass

class AgentError(AuditError):
    """Error raised by an agent during analysis."""
    def __init__(self, agent_name: str, message: str):
        self.agent_name = agent_name
        super().__init__(f"Agent '{agent_name}': {message}")

class LLMError(AuditError):
    """Error related to LLM API calls."""
    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"LLM ({provider}): {message}")

class ScrapingError(AuditError):
    """Error during web scraping."""
    def __init__(self, url: str, message: str):
        self.url = url
        super().__init__(f"Scraping '{url}': {message}")

class ValidationError(AuditError):
    """Error for invalid input (URLs, config, etc.)."""
    pass


class LLMResponseValidationError(LLMError):
    """LLM response missing expected fields."""
    def __init__(self, missing_fields, raw_response="", message=""):
        self.missing_fields = missing_fields
        self.raw_response = raw_response
        super().__init__(
            provider="unknown",
            message=message or f"LLM response missing fields: {', '.join(missing_fields)}"
        )


class PartialResponseError(LLMError):
    """LLM response valid JSON but missing expected fields."""
    def __init__(self, missing_fields, response=None, message=""):
        self.missing_fields = missing_fields
        self.response = response or {}
        super().__init__(
            provider="unknown",
            message=message or f"Partial LLM response, missing: {', '.join(missing_fields)}"
        )
