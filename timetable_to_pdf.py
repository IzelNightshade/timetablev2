import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def load_timetable(json_file):
    """Load timetable data from JSON file."""
    with open(json_file, 'r') as f:
        return json.load(f)

def create_class_table(class_name, slots):
    """Convert timetable slots into a formatted table (Days=Rows, Periods=Columns)."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods_per_day = 8

    # Prepare header (Period 1, Period 2, etc.)
    header = ["Day"] + [f"Period {i+1}" for i in range(periods_per_day)]
    data = [header]

    # Fill data for each day
    for day in days:
        day_row = [day]
        for period in range(periods_per_day):
            slot = days.index(day) * periods_per_day + period
            subjects = slots.get(str(slot), [])
            subject = ", ".join(subjects) if subjects else "Free"
            day_row.append(subject)
        data.append(day_row)

    # Style the table
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),  # Header row
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  # Data rows
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])

    # Adjust column widths (first column narrower for days)
    col_widths = [60] + [80] * periods_per_day  # Day column + 8 period columns
    table = Table(data, colWidths=col_widths)
    table.setStyle(style)
    return table

def generate_pdf(timetable, output_file="timetable.pdf"):
    """Generate a landscape PDF with one page per class."""
    doc = SimpleDocTemplate(output_file, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []

    for class_name, slots in timetable.items():
        # Add class title
        title = Paragraph(f"<b>📅 {class_name} Timetable</b>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Add the timetable table
        table = create_class_table(class_name, slots)
        elements.append(table)
        elements.append(Spacer(1, 24))  # Add space before next class

        # Add page break for next class
        elements.append(Spacer(1, 1))  # Small spacer to force new page

    # Build the PDF
    doc.build(elements)
    print(f"✅ PDF generated: {output_file}")

if __name__ == "__main__":
    # Load the timetable JSON
    timetable = load_timetable("timetable_output.json")

    # Generate PDF
    generate_pdf(timetable)