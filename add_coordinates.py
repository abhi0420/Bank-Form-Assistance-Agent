"""
PDF Coordinate Layout Generator
Adds a coordinate grid to help manually identify positions in a PDF.
Uses PDF-native coordinates: Origin (0,0) at TOP-LEFT, Y increases downward.
These coordinates can be used DIRECTLY with PyMuPDF without conversion.
"""

import fitz  # PyMuPDF
from pathlib import Path


# ============ CONFIGURATION ============
INPUT_PDF = "forms/Pay-in-slip.pdf"  # <-- Change this to your PDF file path
GRID_SPACING = 50                       # Spacing between grid lines (in points)
MAJOR_GRID_SPACING = 100                # Spacing for major/labeled grid lines
FONT_SIZE = 7                           # Font size for coordinate labels
# =======================================


def add_coordinate_grid(input_pdf: str):
    """Add coordinate grid to PDF using PDF-native coordinates (origin at top-left)."""
    
    input_path = Path(input_pdf)
    output_pdf = str(input_path.parent / f"{input_path.stem}_with_coordinates.pdf")
    
    doc = fitz.open(input_pdf)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        width = page.rect.width
        height = page.rect.height
        
        shape = page.new_shape()
        
        # Draw vertical grid lines
        x = 0
        while x <= width:
            is_major = (x % MAJOR_GRID_SPACING == 0)
            color = (0.5, 0.5, 0.5) if is_major else (0.8, 0.8, 0.8)
            line_width = 0.5 if is_major else 0.25
            shape.draw_line(fitz.Point(x, 0), fitz.Point(x, height))
            shape.finish(color=color, width=line_width)
            x += GRID_SPACING
        
        # Draw horizontal grid lines
        y = 0
        while y <= height:
            is_major = (y % MAJOR_GRID_SPACING == 0)
            color = (0.5, 0.5, 0.5) if is_major else (0.8, 0.8, 0.8)
            line_width = 0.5 if is_major else 0.25
            shape.draw_line(fitz.Point(0, y), fitz.Point(width, y))
            shape.finish(color=color, width=line_width)
            y += GRID_SPACING
        
        shape.commit()
        
        # Add coordinate labels at major grid intersections
        # PDF-native: origin at top-left, Y increases downward
        x = 0
        while x <= width:
            y = 0
            while y <= height:
                # Only label at major grid intersections
                if x % MAJOR_GRID_SPACING == 0 and y % MAJOR_GRID_SPACING == 0:
                    coord_text = f"({int(x)},{int(y)})"
                    text_point = fitz.Point(x + 2, y + FONT_SIZE + 2)
                    
                    page.insert_text(
                        text_point,
                        coord_text,
                        fontsize=FONT_SIZE,
                        color=(1, 0, 0),  # Red
                        fontname="helv",
                    )
                
                y += GRID_SPACING
            x += GRID_SPACING
        
        # Add X-axis labels along the top edge (with background for visibility)
        x = 0
        while x <= width:
            if x % MAJOR_GRID_SPACING == 0:
                # Draw a small white background rectangle for readability
                label_rect = fitz.Rect(x, 0, x + 25, 12)
                shape = page.new_shape()
                shape.draw_rect(label_rect)
                shape.finish(color=(0.8, 0.8, 1), fill=(1, 1, 1), width=0.3)
                shape.commit()
                
                page.insert_text(
                    fitz.Point(x + 2, 10),
                    str(int(x)),
                    fontsize=8,
                    color=(0, 0, 0.8),  # Blue
                    fontname="helv",
                )
            x += MAJOR_GRID_SPACING
        
        # Add Y-axis labels along the left edge (with background for visibility)
        y = 0
        while y <= height:
            if y % MAJOR_GRID_SPACING == 0:
                # Draw a small white background rectangle for readability
                label_rect = fitz.Rect(0, y, 30, y + 12)
                shape = page.new_shape()
                shape.draw_rect(label_rect)
                shape.finish(color=(0.8, 0.8, 1), fill=(1, 1, 1), width=0.3)
                shape.commit()
                
                # Add the Y label
                page.insert_text(
                    fitz.Point(2, y + 10),
                    str(int(y)),
                    fontsize=8,
                    color=(0, 0, 0.8),  # Blue
                    fontname="helv",
                )
            y += MAJOR_GRID_SPACING
        
        # Add page info
        page.insert_text(
            fitz.Point(width - 180, 25),
            f"Page {page_num + 1} | {int(width)} x {int(height)} pts",
            fontsize=9,
            color=(0, 0, 0),
            fontname="helv",
        )
        
        # Origin indicator at top-left
        page.insert_text(
            fitz.Point(35, 22),
            "Origin (0,0)",
            fontsize=8,
            color=(0, 0.6, 0),  # Green
            fontname="helv",
        )
        
        # Axis direction indicators
        page.insert_text(
            fitz.Point(width - 40, 25),
            "X →",
            fontsize=9,
            color=(0, 0.5, 0),
            fontname="helv",
        )
        
        page.insert_text(
            fitz.Point(5, height - 10),
            "Y ↓",
            fontsize=9,
            color=(0, 0.5, 0),
            fontname="helv",
        )
    
    doc.save(output_pdf)
    doc.close()
    
    print(f"✓ Coordinate grid added!")
    print(f"  Input:  {input_pdf}")
    print(f"  Output: {output_pdf}")
    print(f"  Grid: {GRID_SPACING}pts | Labels every: {MAJOR_GRID_SPACING}pts")
    print(f"\n  Coordinate system (PDF-native / PyMuPDF compatible):")
    print(f"  - Origin (0,0) at TOP-LEFT corner")
    print(f"  - X increases → (rightward)")
    print(f"  - Y increases ↓ (downward)")
    print(f"\n  Use these coordinates DIRECTLY in PyMuPDF!")


if __name__ == "__main__":
    add_coordinate_grid(INPUT_PDF)
