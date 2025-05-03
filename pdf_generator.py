# pdf_generator.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import textwrap

def create_pdf(text_content, filename):
    """Creates a simple PDF document with the provided text."""
    print(f"Creating PDF: {filename}...")
    try:
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter
        margin = inch
        textobject = c.beginText(margin, height - margin) # Start near top left
        textobject.setFont('Times-Roman', 12)
        textobject.setLeading(14) # Set line spacing

        # Wrap text
        available_width = width - 2 * margin
        # Estimate chars per line based on font size (adjust 0.6 factor as needed)
        wrapper = textwrap.TextWrapper(width=int(available_width / (0.6 * 10)), replace_whitespace=False, break_long_words=False, break_on_hyphens=False)

        lines = []
        for paragraph in text_content.split('\n'):
            wrapped_lines = wrapper.wrap(paragraph)
            if not wrapped_lines: # Handle empty lines (original newlines)
                lines.append('')
            else:
                lines.extend(wrapped_lines)
            # Add a blank line between original paragraphs for spacing, unless it was the last one
            if paragraph and text_content.split('\n')[-1] != paragraph:
                 lines.append('')


        for line in lines:
            # Check if text object needs a new page
            if textobject.getY() < margin + textobject.getLeading():
                c.drawText(textobject) # Draw text accumulated so far
                c.showPage() # End current page, start new one
                textobject = c.beginText(margin, height - margin) # Reset text object
                textobject.setFont('Times-Roman', 12)
                textobject.setLeading(14)

            textobject.textLine(line)

        c.drawText(textobject) # Draw any remaining text
        c.save()
        print("PDF created successfully.")
    except Exception as e:
        print(f"Error creating PDF: {e}") 