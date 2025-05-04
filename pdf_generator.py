# pdf_generator.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer, HRFlowable, BaseDocTemplate, Frame, PageTemplate, ListFlowable, ListItem
from reportlab.lib import colors
import textwrap # Keep for basic wrapping if needed elsewhere
from reportlab.lib.enums import TA_LEFT
import re

def create_pdf(query: str, generation_date: str, analysis_result: str, analyzed_docs: list[dict], filename: str):
    """Creates a PDF report including query, date, analysis, and references page."""
    print(f"Creating PDF: {filename}...")
    try:
        # Use BaseDocTemplate for proper flowable handling from the start
        doc = BaseDocTemplate(filename, pagesize=letter)
        width, height = letter
        margin = inch
        frame = Frame(margin, margin, width - 2 * margin, height - 2 * margin, id='normal')
        template = PageTemplate(id='main', frames=[frame])
        doc.addPageTemplates([template])

        styles = getSampleStyleSheet()
        # Define some basic styles
        title_style = styles['h1']
        heading_style = styles['h2']
        normal_style = styles['BodyText']
        # Create a list item style
        list_item_style = styles['BodyText']
        list_item_style.leftIndent = 18 # Indent list items

        story = []

        # Function to apply basic Markdown replacements to ReportLab tags
        def apply_markdown_to_reportlab(text):
            # Bold (**) and (__)
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
            # Italic (*) and (_)
            # Use negative lookarounds to avoid interfering with list markers
            text = re.sub(r'(?<!\*)\*(?!\*|\s)(.*?)(?<!\s)\*(?!\*)', r'<i>\1</i>', text)
            text = re.sub(r'(?<!_)_(?!_)(.*?)(?<!_)_(?!_)', r'<i>\1</i>', text)
            # Inline code (`)
            text = re.sub(r'`(.*?)`', r'<font name="Courier">\1</font>', text)
            # Replace newlines with <br/> tags
            text = text.replace('\n', '<br/>')
            return text

        # Helper function to add styled paragraphs with Markdown handling
        def add_paragraph(text, style, space_after=0.1):
            # Basic Markdown list detection
            lines = text.split('\n')
            list_items = []
            current_paragraph_text = ""

            for line in lines:
                stripped_line = line.strip()
                if stripped_line.startswith(('* ', '- ')):
                    if current_paragraph_text:
                        # Apply Markdown replacements before creating Paragraph
                        processed_text = apply_markdown_to_reportlab(current_paragraph_text.strip())
                        p = Paragraph(processed_text, style)
                        story.append(p)
                        story.append(Spacer(1, 0.05*inch))
                        current_paragraph_text = ""
                    item_text = stripped_line[2:].strip()
                    # Apply Markdown replacements to list item text
                    processed_item_text = apply_markdown_to_reportlab(item_text)
                    list_items.append(ListItem(Paragraph(processed_item_text, list_item_style), leftIndent=18, bulletColor='black'))
                elif re.match(r'^\d+\. ', stripped_line):
                    if current_paragraph_text:
                         # Apply Markdown replacements before creating Paragraph
                        processed_text = apply_markdown_to_reportlab(current_paragraph_text.strip())
                        p = Paragraph(processed_text, style)
                        story.append(p)
                        story.append(Spacer(1, 0.05*inch))
                        current_paragraph_text = ""
                    item_text = stripped_line.split('.', 1)[1].strip()
                    # Apply Markdown replacements to list item text
                    processed_item_text = apply_markdown_to_reportlab(item_text)
                    list_items.append(ListItem(Paragraph(processed_item_text, list_item_style), leftIndent=18, bulletColor='black'))
                else:
                    if list_items:
                        list_flowable = ListFlowable(list_items, bulletType='bullet', start='-', leftIndent=18)
                        story.append(list_flowable)
                        story.append(Spacer(1, 0.1*inch))
                        list_items = []
                    current_paragraph_text += line + "\n"

            # Add any remaining normal paragraph text
            if current_paragraph_text:
                # Apply Markdown replacements before creating Paragraph
                processed_text = apply_markdown_to_reportlab(current_paragraph_text.strip())
                p = Paragraph(processed_text, style)
                story.append(p)

            # Add final list if text ended with list items
            if list_items:
                 list_flowable = ListFlowable(list_items, bulletType='bullet', start='-', leftIndent=18)
                 story.append(list_flowable)

            # Add final space
            story.append(Spacer(1, space_after * inch))

        def add_heading(text, style):
            story.append(Spacer(1, 0.2*inch))
            p = Paragraph(text, style)
            story.append(p)
            story.append(Spacer(1, 0.1*inch))

        # --- PDF Content ---
        add_heading("Blog Post Analysis Report", title_style)
        add_paragraph(f"Report Generated: {generation_date}", normal_style)
        add_paragraph(f"<b>Analysis Query:</b> {query}", normal_style, space_after=0.2) # Add more space after query

        add_heading("Generated Analysis", heading_style)
        # Process the analysis result using the paragraph handler which attempts Markdown
        add_paragraph(analysis_result, normal_style)

        # --- References Section (at the end) ---
        add_heading("References", heading_style)
        if analyzed_docs:
            ref_items = []
            for i, doc_ref in enumerate(analyzed_docs):
                title = doc_ref.get('title', 'N/A')
                doc_date = doc_ref.get('date', 'N/A')
                url = doc_ref.get('url', '#')

                # Format reference string with clickable link
                ref_text = f"<b>{title}</b> ({doc_date})<br/>"
                if url and url != '#':
                    ref_text += f'<link href="{url}" color="blue"><u>{url}</u></link>'
                else:
                    ref_text += "URL not available"

                # Add as a ListItem - Use Paragraph for rich text
                ref_paragraph = Paragraph(ref_text, normal_style)
                # Let ListFlowable handle the numbering; remove explicit value
                ref_items.append(ListItem(ref_paragraph, leftIndent=18)) # Removed value=f'{i+1}.'

            # Add the list of references to the story
            ref_list_flowable = ListFlowable(ref_items, bulletType='1', leftIndent=18)
            story.append(ref_list_flowable)
            story.append(Spacer(1, 0.2*inch))
        else:
            add_paragraph("No specific documents were referenced for this analysis.", normal_style)

        # Build the PDF
        doc.build(story)
        print("PDF created successfully.")

    except Exception as e:
        print(f"Error creating PDF: {e}")
        import traceback
        traceback.print_exc()

# Regex import needed for numbered list detection
import re
Paragraph.matches = lambda self, pattern: re.match(pattern, self.text) 