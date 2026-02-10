"""Utilities package for website audit tool."""

from .scraper import WebScraper, PageData
from .scoring import ModuleScore, ScoreItem, Recommendation, AuditReport, ConsultingOutcome, Impact, Effort
from .report import generate_html_report
from .logo import extract_logo_url, get_logo_as_base64
from .llm_client import LLMClient
from .screenshot import ScreenshotManager

__all__ = [
    'WebScraper', 'PageData',
    'ModuleScore', 'ScoreItem', 'Recommendation', 'AuditReport', 'ConsultingOutcome', 'Impact', 'Effort',
    'generate_html_report',
    'extract_logo_url', 'get_logo_as_base64',
    'LLMClient',
    'ScreenshotManager'
]
