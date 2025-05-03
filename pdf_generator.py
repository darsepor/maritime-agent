# pdf_generator.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, HRFlowable, BaseDocTemplate, Frame, PageTemplate
from reportlab.lib import colors
import textwrap # Keep for basic wrapping if needed elsewhere

def create_pdf(query: str, generation_date: str, analysis_result: str, analyzed_docs: list[dict], filename: str):
    """Creates a PDF report including query, date, analyzed docs (with links), and analysis."""
    print(f"Creating PDF: {filename}...")
    try:
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter
        margin = inch

        styles = getSampleStyleSheet()
        # Define some basic styles
        title_style = styles['h1']
        heading_style = styles['h2']
        normal_style = styles['BodyText']
        code_style = styles['Code'] # For URL

        # Helper function to draw flowables and handle page breaks
        story = []
        def add_paragraph(text, style):
            p = Paragraph(text.replace('\n', '<br/>'), style)
            story.append(p)
            story.append(Spacer(1, 0.1*inch))

        def add_heading(text, style):
            story.append(Spacer(1, 0.2*inch))
            p = Paragraph(text, style)
            story.append(p)
            story.append(Spacer(1, 0.1*inch))

        # --- PDF Content --- 
        add_heading("Blog Post Analysis Report", title_style)
        add_paragraph(f"Report Generated: {generation_date}", normal_style)
        add_paragraph(f"<b>Analysis Query:</b> {query}", normal_style)

        add_heading("Analyzed Documents", heading_style)
        if analyzed_docs:
            for i, doc in enumerate(analyzed_docs):
                title = doc.get('title', 'N/A')
                doc_date = doc.get('date', 'N/A')
                url = doc.get('url', '#')
                content = doc.get('content', '')

                story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
                story.append(Spacer(1, 0.1*inch))
                add_paragraph(f"<b>Document {i+1}: {title}</b>", styles['h3'])
                add_paragraph(f"<i>Date:</i> {doc_date}", normal_style)
                # Create clickable URL using Paragraph flowable and <link> tag
                if url and url != '#':
                     add_paragraph(f'<i>URL:</i> <link href="{url}" color="blue"><u>{url}</u></link>', normal_style)
                else:
                     add_paragraph(f"<i>URL:</i> Not Available", normal_style)
                # Remove document content section
                # add_paragraph("<i>Content:</i>", normal_style)
                # add_paragraph(content, normal_style) # Content is wrapped by Paragraph
                story.append(Spacer(1, 0.2*inch))
        else:
            add_paragraph("No specific documents were identified or retrieved for this analysis.", normal_style)

        add_heading("Generated Analysis", heading_style)
        add_paragraph(analysis_result, normal_style)

        # Build the PDF using SimpleDocTemplate for better flowable handling
        # This automatically handles page breaks
        doc_template = canvas.Canvas(filename, pagesize=letter)
        frame = Frame(margin, margin, width - 2 * margin, height - 2 * margin, id='normal')
        template = BaseDocTemplate(filename, pagesize=letter)
        template.addPageTemplates([PageTemplate(id='main', frames=[frame])])

        template.build(story)
        print("PDF created successfully.")

    except Exception as e:
        print(f"Error creating PDF: {e}")
        import traceback
        traceback.print_exc() 