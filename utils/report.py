"""HTML Report Generation Utility."""

import re
from pathlib import Path
from jinja2 import Environment, BaseLoader
from markupsafe import Markup
from utils.scoring import AuditReport


def markdown_to_html(text):
    """Convert basic markdown to HTML (lists, bold, links)."""
    if not text:
        return ""
    text = str(text)
    # Convert **bold** to <strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Convert [link text](url) to <a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # Convert lines
    lines = text.split('\n')
    html_lines = []
    in_ul = False
    in_ol = False
    for line in lines:
        stripped = line.strip()
        is_bullet = stripped.startswith('- ') or stripped.startswith('* ')
        is_ordered = bool(re.match(r'^\d+\.\s', stripped))

        if is_bullet:
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            if not in_ul:
                html_lines.append('<ul>')
                in_ul = True
            html_lines.append(f'<li>{stripped[2:]}</li>')
        elif is_ordered:
            if in_ul:
                html_lines.append('</ul>')
                in_ul = False
            if not in_ol:
                html_lines.append('<ol>')
                in_ol = True
            content = re.sub(r'^\d+\.\s', '', stripped)
            html_lines.append(f'<li>{content}</li>')
        else:
            if in_ul:
                html_lines.append('</ul>')
                in_ul = False
            if in_ol:
                html_lines.append('</ol>')
                in_ol = False
            if stripped:
                html_lines.append(f'<p>{stripped}</p>')
    if in_ul:
        html_lines.append('</ul>')
    if in_ol:
        html_lines.append('</ol>')
    return '\n'.join(html_lines)


def get_template() -> str:
    """Load the HTML template."""
    template_path = Path(__file__).parent.parent / "templates" / "report.html"
    if template_path.exists():
        return template_path.read_text(encoding='utf-8')
    return ""


def _create_jinja_env():
    """Create a Jinja2 Environment with custom filters."""
    env = Environment(loader=BaseLoader())
    env.filters['markdown_to_html'] = lambda text: Markup(markdown_to_html(text))
    return env


def generate_html_report(report: AuditReport, output_path: str, context=None) -> str:
    """
    Generate HTML report from audit data.

    Args:
        report: AuditReport object with all module scores
        output_path: Path to save the HTML report
        context: Optional ContextStore for additional data (screenshots, segments, etc.)

    Returns:
        Path to generated report
    """
    template_str = get_template()
    env = _create_jinja_env()
    template = env.from_string(template_str)

    # Find competitor module if present
    competitor_module = None
    for m in report.modules:
        if 'Competitive' in m.name or 'Competitor' in m.name:
            competitor_module = m
            break

    # Get critical pages, segments, and social links from context if available
    critical_pages = []
    identified_segments = []
    social_links = {}

    if context:
        critical_pages = getattr(context, 'critical_pages', [])
        identified_segments = getattr(context, 'identified_segments', [])
        social_links = getattr(context, 'social_links', {})

    # Prepare template context
    template_context = {
        'report': report,
        'company_name': report.company_name,
        'company_website': report.company_website,
        'audit_date': report.audit_date,
        'analyst_name': report.analyst_name,
        'analyst_company': getattr(report, 'analyst_company', 'Bhavsar Growth Consulting'),
        'client_logo': getattr(report, 'client_logo', ''),
        'analyst_logo': getattr(report, 'analyst_logo', ''),
        # new 2.0 fields
        'deep_research': report.get_module_by_name('deep_research'),
        'prompt_visibility': report.get_module_by_name('prompt_visibility'),
        'social_listening': report.get_module_by_name('social_listening'),
        'strategic_friction': getattr(report, 'strategic_friction', None),
        'overall_outcome': report.overall_outcome.value,
        'outcome_color': report.outcome_color,
        'overall_percentage': report.overall_percentage,
        'modules': report.modules,
        'top_strengths': report.get_top_strengths(3),
        'critical_gaps': report.get_critical_gaps(5), # Increased to 5
        'matrix_recommendations': report.get_matrix_recommendations(),
        'all_recommendations': report.get_all_recommendations(),
        'competitor_module': competitor_module,
        'critical_pages': critical_pages,
        'identified_segments': identified_segments,
        'primary_segment': getattr(context, 'primary_segment', ''),
        'primary_segment_justification': getattr(context, 'primary_segment_justification', ''),
        'primary_segment_priority': getattr(context, 'primary_segment_priority', ''),
        'social_links': social_links,
    }

    html_content = template.render(**template_context)

    # Write to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_content, encoding='utf-8')

    return str(output_file)
