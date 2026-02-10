from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from utils.scoring import AuditReport, Recommendation, MatrixPlacement
import math

def setup_style():
    """Configure plot style for Bhavsar Growth Consulting (Dark Mode)."""
    plt.style.use('dark_background')
    
    # Brand Colors
    # Background: #070B14
    # Card/Surface: #0D1321
    # Primary Blue: #3B82F6
    # Accent Cyan: #0EA5E9
    # Text: #F8FAFC
    # Muted: #8B99AD
    
    plt.rcParams.update({
        'figure.facecolor': '#070B14',
        'axes.facecolor': '#0D1321',    # Slightly lighter for contrast
        'axes.edgecolor': '#8B99AD',
        'axes.labelcolor': '#F8FAFC',
        'text.color': '#F8FAFC',
        'xtick.color': '#8B99AD',
        'ytick.color': '#8B99AD',
        'grid.color': '#1e293b',       # Very subtle grid
        'font.family': 'sans-serif',
        'font.sans-serif': ['Plus Jakarta Sans', 'Inter', 'Arial'],
        'font.size': 10,
        'axes.titlesize': 16,
        'axes.labelsize': 12
    })

def create_impact_effort_matrix(recommendations: list[Recommendation], output_path: str) -> str:
    """Generate and save Impact vs Effort matrix (Dark Mode)."""
    setup_style()
    fig, ax = plt.subplots(figsize=(10, 8)) # Wider for better text fit
    
    # Mapping: Low=1, Medium=2, High=3
    mapping = {'Low': 1, 'Medium': 2, 'High': 3}
    
    x_coords = []
    y_coords = []
    colors = []
    sizes = []
    
    for rec in recommendations:
        eff_val = mapping[rec.effort.value]
        imp_val = mapping[rec.impact.value]
        
        # Jitter
        jitter_x = (hash(rec.issue) % 20 - 10) / 40.0 
        jitter_y = (hash(rec.issue + "y") % 20 - 10) / 40.0
        
        x_coords.append(eff_val + jitter_x)
        y_coords.append(imp_val + jitter_y)
        
        # Brand Colors for Dots
        if rec.matrix_placement == MatrixPlacement.QUICK_WIN:
            colors.append('#22c55e') # Green
            sizes.append(250)
        elif rec.matrix_placement == MatrixPlacement.STRATEGIC_BET:
            colors.append('#3b82f6') # Brand Blue
            sizes.append(250)
        elif rec.matrix_placement == MatrixPlacement.LOW_HANGING:
            colors.append('#eab308') # Yellow
            sizes.append(150)
        else:
            colors.append('#ef4444') # Red
            sizes.append(100)

    # Plot
    ax.scatter(x_coords, y_coords, c=colors, s=sizes, alpha=0.9, edgecolors='#F8FAFC', linewidth=1.5)
    
    # Axes configuration
    # Effort: Low(1) -> High(3)
    # Impact: Low(1) -> High(3)
    
    ax.set_xlim(0.5, 3.5)
    ax.set_ylim(0.5, 3.5)
    
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(['Low', 'Medium', 'High'])
    ax.set_xlabel('Effort Required')
    
    ax.set_yticks([1, 2, 3])
    ax.set_yticklabels(['Low', 'Medium', 'High'])
    ax.set_ylabel('Business Impact')
    
    # Quadrant Dividers
    ax.axhline(y=2.0, color='#8B99AD', linestyle='--', alpha=0.3)
    ax.axvline(x=2.0, color='#8B99AD', linestyle='--', alpha=0.3)
    
    # Quadrant Labels (Brand Styled)
    # Top-Left (Low Effort, High Impact) -> Quick Wins
    ax.text(1.0, 3.3, "QUICK WINS", ha='center', va='center', fontweight='bold', color='#22c55e', fontsize=12)
    # Top-Right (High Effort, High Impact) -> Strategic Bets
    ax.text(3.0, 3.3, "STRATEGIC BETS", ha='center', va='center', fontweight='bold', color='#3b82f6', fontsize=12)
    # Bottom-Left (Low Effort, Low Impact) -> Low Hanging Fruit
    ax.text(1.0, 0.7, "LOW HANGING FRUIT", ha='center', va='center', fontweight='bold', color='#eab308', fontsize=12)
    # Bottom-Right (High Effort, Low Impact) -> Distractions
    ax.text(3.0, 0.7, "DISTRACTIONS", ha='center', va='center', fontweight='bold', color='#ef4444', fontsize=12)

    plt.grid(True, linestyle=':', alpha=0.2, color='#3B82F6')
    ax.set_title('Strategic Prioritization Matrix', color='#F8FAFC', pad=20)
    
    # Remove boarder spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#8B99AD')
    ax.spines['left'].set_color('#8B99AD')
    
    # Save
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, bbox_inches='tight', dpi=120, facecolor='#070B14')
    plt.close()
    return str(out)

def create_score_radar_chart(report: AuditReport, output_path: str) -> str:
    """Generate dark mode radar chart."""
    setup_style()
    
    # Prepare Data
    labels = []
    values = []
    
    for m in report.modules:
        if m.max_points > 0:
            # Wrap text manually for readability
            name = m.name.replace(" Analysis", "").replace(" & ", "\n")
            if len(name) > 15 and '\n' not in name:
                parts = name.split(' ')
                mid = len(parts)//2
                name = " ".join(parts[:mid]) + "\n" + " ".join(parts[mid:])
            labels.append(name)
            values.append(m.percentage)
            
    if not values:
        return ""

    # Close the loop
    values = np.concatenate((values, [values[0]]))
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False)
    angles = np.concatenate((angles, [angles[0]]))
    
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    
    # Background for polar
    ax.set_facecolor('#0D1321')
    
    # Plot Line
    ax.plot(angles, values, 'o-', linewidth=3, color='#0EA5E9', markerfacecolor='#F8FAFC')
    ax.fill(angles, values, alpha=0.3, color='#3B82F6')
    
    # Grids
    ax.set_thetagrids(angles[:-1] * 180/np.pi, labels)
    
    # Custom Grid settings for Polar
    ax.grid(color='#8B99AD', alpha=0.3, linestyle='--')
    ax.spines['polar'].set_color('#3B82F6')
    
    ax.set_ylim(0, 100)
    
    # Title
    plt.title(f'Audit Score Breakdown\nOverall: {report.overall_percentage:.1f}%', 
             y=1.08, color='#F8FAFC')
    
    # Save
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, bbox_inches='tight', dpi=120, facecolor='#070B14')
    plt.close()
    return str(out)
