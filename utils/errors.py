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
