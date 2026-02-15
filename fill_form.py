import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
import io


def load_field_coordinates(json_path):
    """Load field coordinates and values from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(f"Loaded fields: {data}")
        return data


# Default styling
DEFAULT_FONT_SIZE = 10
DEFAULT_BOLD = True
DEFAULT_COLOR = (0, 0, 0.5)  # Navy blue (RGB)


def create_text_overlay(fields, page_width, page_height):
    """Create a PDF with text at the specified coordinates."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
    for field in fields:
        field_name = field.get("field")
        start = field.get("start")
        value = field.get("value", "")
        spacing = field.get("spacing")  # Optional: spacing between characters
        font_size = field.get("font_size", DEFAULT_FONT_SIZE)
        is_bold = field.get("bold", DEFAULT_BOLD)
        field_type = field.get("type", "text")  # text, checkbox
        
        if start and value:
            x, y = start[0], start[1]
            # PDF coordinates start from bottom-left, so we need to flip y
            pdf_y = page_height - y
            
            # Set font based on bold preference
            font_name = "Helvetica-Bold" if is_bold else "Helvetica"
            can.setFont(font_name, font_size)
            
            # Set color (navy blue by default)
            can.setFillColorRGB(*DEFAULT_COLOR)
            
            # Handle checkbox type differently
            if field_type == "checkbox":
                # Draw a clear X or checkmark for checkboxes
                can.setFont("Helvetica-Bold", font_size)
                print(f"Filling checkbox '{field_name}' with '{value}' at ({x}, {pdf_y})")
                can.drawString(x, pdf_y, str(value))
            elif spacing:
                # Draw each character with spacing (for fields with individual boxes)
                print(f"Filling '{field_name}' with '{value}' at ({x}, {pdf_y}) [size={font_size}, spacing={spacing}]")
                for i, char in enumerate(str(value)):
                    can.drawString(x + (i * spacing), pdf_y, char)
            else:
                print(f"Filling '{field_name}' with '{value}' at ({x}, {pdf_y}) [size={font_size}]")
                can.drawString(x, pdf_y, str(value))
        else:
            print(f"Skipping field '{field_name}': start={start}, value={value}")
    
    can.save()
    packet.seek(0)
    return packet


def fill_pdf_form(input_pdf_path, output_pdf_path, json_path):
    """Fill the PDF form with values from the JSON file."""
    # Load field coordinates and values
    fields = load_field_coordinates(json_path)
    
    # Read the original PDF
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    # Get the first page dimensions
    first_page = reader.pages[0]
    page_width = float(first_page.mediabox.width)
    page_height = float(first_page.mediabox.height)
    
    print(f"PDF page size: {page_width} x {page_height}")
    
    # Create overlay with text
    overlay_packet = create_text_overlay(fields, page_width, page_height)
    overlay_reader = PdfReader(overlay_packet)
    overlay_page = overlay_reader.pages[0]
    
    # Merge overlay with each page of the original PDF
    for i, page in enumerate(reader.pages):
        if i == 0:  # Only apply overlay to first page
            page.merge_page(overlay_page)
        writer.add_page(page)
    
    # Write the output PDF
    with open(output_pdf_path, 'wb') as output_file:
        writer.write(output_file)
    
    print(f"Filled PDF saved to: {output_pdf_path}")


if __name__ == "__main__":
    # File paths
    input_pdf = "forms/Pay-in-Slip.pdf"
    output_pdf = "forms/Pay-in-Slip_filled.pdf"
    json_file = "field_coordinates.json"
    
    fill_pdf_form(input_pdf, output_pdf, json_file)
