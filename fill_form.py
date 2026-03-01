import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
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
DEFAULT_FONT_FAMILY = "Helvetica"


def hex_to_rgb(hex_color):
    """Convert '#RRGGBB' to (r, g, b) floats 0-1."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def resolve_font_name(family, bold):
    """Map a font family + bold flag to a reportlab font name."""
    fonts = {
        'Helvetica':   ('Helvetica',       'Helvetica-Bold'),
        'Courier':     ('Courier',         'Courier-Bold'),
        'Times-Roman': ('Times-Roman',     'Times-Bold'),
    }
    pair = fonts.get(family, fonts['Helvetica'])
    return pair[1] if bold else pair[0]


def create_text_overlay(fields, page_width, page_height, pdf_settings=None):
    """Create a PDF with text at the specified coordinates."""
    pdf_settings = pdf_settings or {}
    
    # Resolve global settings from frontend (with defaults)
    global_family = pdf_settings.get('font_family', DEFAULT_FONT_FAMILY)
    global_size   = pdf_settings.get('font_size', DEFAULT_FONT_SIZE)
    global_bold   = pdf_settings.get('bold', DEFAULT_BOLD)
    global_color  = hex_to_rgb(pdf_settings['color']) if 'color' in pdf_settings else DEFAULT_COLOR
    
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
    for field in fields:
        field_name = field.get("field")
        start = field.get("start")
        value = field.get("value", "")
        spacing = field.get("spacing")  # Optional: spacing between characters
        font_size = field.get("font_size", global_size)
        is_bold = field.get("bold", global_bold)
        field_type = field.get("type", "text")
        
        if start and value:
            x, y = start[0], start[1]
            # PDF coordinates start from bottom-left, so we need to flip y
            pdf_y = page_height - y
            
            # Set font using global family + per-field bold/size
            font_name = resolve_font_name(global_family, is_bold)
            can.setFont(font_name, font_size)
            
            # Set color from settings
            can.setFillColorRGB(*global_color)
            
            # Handle checkbox type differently
            if field_type == "checkbox":
                # Draw a clear X or checkmark for checkboxes
                can.setFont("Helvetica-Bold", font_size)
                print(f"Filling checkbox '{field_name}' with '{value}' at ({x}, {pdf_y})")
                can.drawString(x, pdf_y, str(value))
            elif field.get("multiline"):
                # Multiline: word-wrap text within bounding box
                end = field.get("end", start)
                box_width = abs(end[0] - start[0])
                box_height = abs(end[1] - start[1])
                line_spacing = field.get("line_spacing", font_size * 1.3)
                
                # Word-wrap the text to fit the available width
                lines = simpleSplit(str(value), font_name, font_size, box_width)
                
                # Calculate max lines that fit in the bounding box
                max_lines = max(1, int(box_height / line_spacing) + 1) if box_height > 0 else len(lines)
                lines = lines[:max_lines]
                
                print(f"Filling multiline '{field_name}' with {len(lines)} lines at ({x}, {pdf_y}) [box={box_width}x{box_height}, spacing={line_spacing}]")
                for i, line in enumerate(lines):
                    can.drawString(x, pdf_y - (i * line_spacing), line)
            elif spacing:
                # Draw each character with spacing (for fields with individual boxes)
                print(f"Filling '{field_name}' with '{value}' at ({x}, {pdf_y}) [size={font_size}, spacing={spacing}]")
                for i, char in enumerate(str(value)):
                    can.drawString(x + (i * spacing), pdf_y, char)
            else:
                print(f"Filling '{field_name}' with '{value}' at ({x}, {pdf_y}) [size={font_size}]")
                can.drawString(x, pdf_y, str(value))
        else:
            print(f"Skipping field '{field_name}' due to missing coordinates or value.")
    
    can.save()
    packet.seek(0)
    return packet


def fill_pdf_form(input_pdf_path, output_pdf_path, json_path, form_name="Pay-in-Slip"):
    """Fill the PDF form with values from the JSON file."""
    # Load field coordinates and values
    forms = load_field_coordinates(json_path)

    fields = None
    for form in forms:
        if form.get("form_name") == form_name:
            fields = form.get("form_fields")
            print(f"Found fields for form '{form_name}': {fields}")
            break
    
    if not fields:
        print(f"No fields found for form '{form_name}'")
        return
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
    return output_pdf_path


def fill_pdf_from_chatbot(chatbot_values, json_path="field_coordinates.json", form_name="Pay-in-Slip",
                         input_pdf=None, output_pdf=None, pdf_settings=None):
    """
    Fill PDF using values collected from chatbot.
    
    Args:
        chatbot_values: dict of field_name -> value from chatbot
        json_path: path to field coordinates JSON
        form_name: name of form in JSON
        input_pdf: source PDF path (auto-detected from JSON if None)
        output_pdf: output PDF path (auto-generated if None)
    """
    # Load field coordinates from JSON
    forms = load_field_coordinates(json_path)
    
    fields = None
    form_data = None
    for form in forms:
        if form.get("form_name") == form_name:
            form_data = form
            fields = form.get("form_fields")
            break
    
    if not fields:
        print(f"No fields found for form '{form_name}'")
        return None
    
    # Get PDF paths from JSON or use provided ones
    if input_pdf is None:
        input_pdf = form_data.get("pdf_path", f"forms/{form_name}.pdf")
    if output_pdf is None:
        output_pdf = input_pdf.replace(".pdf", "_filled.pdf")
    
    # Merge chatbot values with field coordinates
    for field in fields:
        field_name = field.get("field")
        if field_name in chatbot_values:
            field["value"] = chatbot_values[field_name]
    
    # Read the original PDF
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    
    first_page = reader.pages[0]
    page_width = float(first_page.mediabox.width)
    page_height = float(first_page.mediabox.height)
    
    print(f"PDF page size: {page_width} x {page_height}")
    
    # Create overlay with text
    overlay_packet = create_text_overlay(fields, page_width, page_height, pdf_settings)
    overlay_reader = PdfReader(overlay_packet)
    overlay_page = overlay_reader.pages[0]
    
    # Merge overlay with original PDF
    for i, page in enumerate(reader.pages):
        if i == 0:
            page.merge_page(overlay_page)
        writer.add_page(page)
    
    # Write output
    with open(output_pdf, 'wb') as output_file:
        writer.write(output_file)
    
    print(f"\n✅ Filled PDF saved to: {output_pdf}")
    return output_pdf


if __name__ == "__main__":
    # File paths
    input_pdf = "forms/Pay-in-Slip.pdf"
    output_pdf = "forms/Pay-in-Slip_filled.pdf"
    json_file = "field_coordinates.json"
    
    fill_pdf_form(input_pdf, output_pdf, json_file, form_name="Pay-in-Slip")
