import os
import io
import time
from pathlib import Path
from typing import Optional, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from utils.scoring import AuditReport
from utils.charts import create_impact_effort_matrix, create_score_radar_chart
from jinja2 import Template

SCOPES = ['https://www.googleapis.com/auth/drive']

class GDocsClient:
    def __init__(self, service_account_path: str):
        self.creds = service_account.Credentials.from_service_account_file(
            service_account_path, scopes=SCOPES
        )
        self.service = build('drive', 'v3', credentials=self.creds)

    def upload_image(self, file_path: str, folder_id: Optional[str] = None) -> str:
        """Upload image to Drive and return webViewLink."""
        path = Path(file_path)
        file_metadata = {'name': path.name}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(file_path, mimetype='image/png')
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webContentLink, webViewLink'
        ).execute()
        
        # Crucial: verify that the conversion process can read this link.
        # usually webContentLink works for import if authenticated.
        return file.get('webContentLink')

    def create_report_doc(self, report: AuditReport, folder_id: Optional[str] = None) -> str:
        """
        Create a Google Doc report by uploading HTML with embedded image links.
        
        Steps:
        1. Create charts locally.
        2. Upload charts to Drive.
        3. Generate HTML referencing Drive image links.
        4. Upload HTML to Drive as Google Doc.
        """
        # 1. Create Folder for this report run
        folder_metadata = {
            'name': f"{report.company_name} Audit - {int(time.time())}",
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if folder_id:
            folder_metadata['parents'] = [folder_id]
            
        folder = self.service.files().create(body=folder_metadata, fields='id').execute()
        report_folder_id = folder.get('id')
        print(f"Created folder: {report_folder_id}")

        # 2. Generate and Upload Charts
        # Matrix
        matrix_path = "output/chart_matrix.png"
        create_impact_effort_matrix(report.get_all_recommendations(), matrix_path)
        matrix_url = self.upload_image(matrix_path, report_folder_id)

        # Radar
        radar_path = "output/chart_radar.png"
        create_score_radar_chart(report, radar_path)
        radar_url = self.upload_image(radar_path, report_folder_id)

        # 3. Generate HTML Content for the Doc
        # We use a simpler template than the main HTML report, focused on Doc readability
        doc_content = self._render_gdoc_html(report, matrix_url, radar_url)
        
        # Write temp file
        temp_html = "output/temp_gdoc_import.html"
        with open(temp_html, "w", encoding='utf-8') as f:
            f.write(doc_content)

        # 4. Upload as Google Doc
        file_metadata = {
            'name': f"{report.company_name} Website Audit Report",
            'mimeType': 'application/vnd.google-apps.document',
            'parents': [report_folder_id]
        }
        media = MediaFileUpload(temp_html, mimetype='text/html')
        
        doc_file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        return doc_file.get('webViewLink')

    def _render_gdoc_html(self, report: AuditReport, matrix_url: str, radar_url: str) -> str:
        """Render simple HTML for Google Doc conversion."""
        # Using inline styles because external CSS often gets lost in conversion
        template_str = """
        <html>
        <body style="font-family: Arial; font-size: 11pt; color: #333;">
            <h1 style="color: #2c3e50; font-size: 24pt;">{{ report.company_name }} Website Audit</h1>
            <p style="color: #7f8c8d;">Date: {{ report.audit_date }} | Analyst: {{ report.analyst_name }}</p>
            
            <h2 style="color: #e67e22; border-bottom: 2px solid #e67e22; padding-top: 20px;">Executive Summary</h2>
            <p><strong>Overall Grade:</strong> <span style="font-size: 14pt; color: {{ report.outcome_color }}">{{ report.overall_grade.value }}</span> ({{ report.overall_outcome.value }})</p>
            
            {% if report.strategic_friction %}
            <div style="background-color: #f8f9fa; padding: 15px; border-left: 5px solid #e74c3c; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #c0392b;">Strategic Friction: {{ report.strategic_friction.title }}</h3>
                <p><strong>Symptom:</strong> {{ report.strategic_friction.primary_symptom }}</p>
                <p><strong>Impact:</strong> {{ report.strategic_friction.business_impact }}</p>
            </div>
            {% endif %}

            <h3>Score Breakdown</h3>
            <img src="{{ radar_url }}" style="width: 400px; height: auto;" />

            <h2 style="color: #2980b9; border-bottom: 2px solid #2980b9; padding-top: 20px;">Detailed Analysis</h2>
            
            {% for module in report.modules %}
            <h3 style="color: #2c3e50;">{{ module.name }} - Grade: {{ module.grade.value }}</h3>
            <p><em>{{ module.outcome.value }}</em></p>
            
            <ul>
                {% for item in module.items %}
                <li>
                    <strong>{{ item.name }}:</strong> {{ item.actual_points }}/{{ item.max_points }}
                    <br><em>{{ item.notes }}</em>
                </li>
                {% endfor %}
            </ul>
            
            <h4>Analysis</h4>
            <p>{{ module.analysis_text | replace('\n', '<br>') }}</p>
            
            {% if module.recommendations %}
            <h4>Top Recommendations</h4>
            <ul>
                {% for rec in module.recommendations[:3] %}
                <li><strong>{{ rec.recommendation }}</strong> (Impact: {{ rec.impact.value }}, Effort: {{ rec.effort.value }})</li>
                {% endfor %}
            </ul>
            {% endif %}
            
            <hr style="border: 0; border-top: 1px solid #eee;">
            {% endfor %}

            <h2 style="color: #27ae60; border-bottom: 2px solid #27ae60; padding-top: 20px;">Prioritization Matrix</h2>
            <p>Visualizing high-impact actions versus effort required.</p>
            <img src="{{ matrix_url }}" style="width: 500px; height: auto;" />

            <h3>Quick Wins (High Impact, Low Effort)</h3>
            <ul>
            {% for rec in quick_wins %}
                <li>
                    <strong>{{ rec.category }}:</strong> {{ rec.recommendation }} 
                    <br><span style="color: #27ae60;">{{ rec.business_impact }}</span>
                </li>
            {% endfor %}
            </ul>

        </body>
        </html>
        """
        template = Template(template_str)
        return template.render(
            report=report,
            matrix_url=matrix_url,
            radar_url=radar_url,
            quick_wins=report.get_quick_wins(5)
        )
