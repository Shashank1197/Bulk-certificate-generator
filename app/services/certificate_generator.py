import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget


def draw_corner_ornament(c: canvas.Canvas, x: float, y: float, size: float = 18.0) -> None:
    """Draw an elegant geometric corner ornament."""
    c.saveState()
    c.setStrokeColor(colors.HexColor("#C59B27"))
    c.setFillColor(colors.HexColor("#C59B27"))
    c.setLineWidth(1)
    # Diamond
    p = c.beginPath()
    p.moveTo(x, y - size / 2)
    p.lineTo(x + size / 2, y)
    p.lineTo(x, y + size / 2)
    p.lineTo(x - size / 2, y)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def draw_signature_flourish(c: canvas.Canvas, x: float, y: float) -> None:
    """Draw a stylized vector signature flourish."""
    c.saveState()
    c.setStrokeColor(colors.HexColor("#0D2040"))
    c.setLineWidth(1.5)
    c.setLineCap(1)  # Round cap
    p = c.beginPath()
    p.moveTo(x, y)
    p.curveTo(x + 20, y + 25, x + 35, y - 10, x + 60, y + 18)
    p.curveTo(x + 75, y + 30, x + 85, y - 5, x + 110, y + 10)
    p.curveTo(x + 120, y + 15, x + 130, y - 8, x + 150, y + 2)
    c.drawPath(p, fill=0, stroke=1)
    c.restoreState()


def generate_certificate_pdf(
    certificate_id: str,
    recipient_name: str,
    event_name: str,
    issuer_name: str,
    issue_date: str,
    certificate_title: str,
    custom_attributes: Optional[Dict[str, Any]],
    output_path: str,
    verification_url: str,
) -> Tuple[str, int]:
    """
    Generate a high-resolution, vector-based PDF certificate.

    Args:
        certificate_id: Unique UUID or ID string for the certificate.
        recipient_name: Name of the recipient.
        event_name: Name of the course, workshop, or event.
        issuer_name: Institution or authority issuing the certificate.
        issue_date: Date string displayed on the certificate.
        certificate_title: Title heading (e.g. 'Certificate of Completion').
        custom_attributes: Optional dictionary of extra information (e.g. grade, score).
        output_path: Target filesystem path to save the generated PDF.
        verification_url: URL embedded into the QR code for public verification.

    Returns:
        Tuple of (output_file_path, file_size_in_bytes)
    """
    parent_dir = Path(output_path).parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    width, height = landscape(letter)  # 792 x 612 pt
    c = canvas.Canvas(output_path, pagesize=(width, height))

    # 1. Background Fill - Elegant Cream Parchment
    c.setFillColor(colors.HexColor("#FCFBF9"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # 2. Decorative Double Borders
    # Outer Deep Navy border
    c.setStrokeColor(colors.HexColor("#0D2040"))
    c.setLineWidth(4.5)
    margin_outer = 22
    c.rect(margin_outer, margin_outer, width - 2 * margin_outer, height - 2 * margin_outer, fill=0, stroke=1)

    # Inner Gold border
    c.setStrokeColor(colors.HexColor("#C59B27"))
    c.setLineWidth(1.5)
    margin_inner = 28
    c.rect(margin_inner, margin_inner, width - 2 * margin_inner, height - 2 * margin_inner, fill=0, stroke=1)

    # Hairline accent border
    c.setStrokeColor(colors.HexColor("#DFC15D"))
    c.setLineWidth(0.5)
    margin_hairline = 33
    c.rect(margin_hairline, margin_hairline, width - 2 * margin_hairline, height - 2 * margin_hairline, fill=0, stroke=1)

    # 3. Corner Ornaments
    draw_corner_ornament(c, margin_inner, margin_inner)
    draw_corner_ornament(c, width - margin_inner, margin_inner)
    draw_corner_ornament(c, margin_inner, height - margin_inner)
    draw_corner_ornament(c, width - margin_inner, height - margin_inner)

    # 4. Top Organization / Issuer Branding
    c.setFillColor(colors.HexColor("#0D2040"))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, height - 75, issuer_name.upper())

    # Gold separator line under issuer
    c.setStrokeColor(colors.HexColor("#C59B27"))
    c.setLineWidth(1.5)
    c.line(width / 2 - 80, height - 85, width / 2 + 80, height - 85)
    draw_corner_ornament(c, width / 2, height - 85, size=8)

    # 5. Certificate Main Title
    c.setFillColor(colors.HexColor("#0D2040"))
    c.setFont("Times-Bold", 28)
    c.drawCentredString(width / 2, height - 128, certificate_title.upper())

    # 6. "PROUDLY PRESENTED TO"
    c.setFillColor(colors.HexColor("#718096"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, height - 165, "THIS IS PROUDLY PRESENTED TO")

    # 7. Recipient Name
    c.setFillColor(colors.HexColor("#0D2040"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width / 2, height - 215, recipient_name)

    # Gold underline beneath recipient name
    name_width = c.stringWidth(recipient_name, "Helvetica-Bold", 30)
    underline_half = max(name_width / 2 + 25, 120)
    c.setStrokeColor(colors.HexColor("#C59B27"))
    c.setLineWidth(1.5)
    c.line(width / 2 - underline_half, height - 225, width / 2 + underline_half, height - 225)
    draw_corner_ornament(c, width / 2, height - 225, size=7)

    # 8. Achievement Text
    c.setFillColor(colors.HexColor("#4A5568"))
    c.setFont("Times-Italic", 13)
    c.drawCentredString(
        width / 2,
        height - 265,
        "for successfully completing and demonstrating commendable performance in",
    )

    # 9. Event / Course Name
    c.setFillColor(colors.HexColor("#0D2040"))
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 298, event_name)

    # 10. Custom Attributes (e.g. Grade, Honors, Hours)
    if custom_attributes and isinstance(custom_attributes, dict):
        attr_strings = [f"{k.capitalize()}: {v}" for k, v in custom_attributes.items() if v is not None]
        if attr_strings:
            badge_text = " • ".join(attr_strings)
            c.setFillColor(colors.HexColor("#C59B27"))
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(width / 2, height - 328, badge_text)

    # 11. Footer Section
    # Left Block: Issue Date & Certificate ID
    c.setFillColor(colors.HexColor("#2D3748"))
    c.setFont("Helvetica", 10)
    c.drawString(60, 115, f"Date of Issue: {issue_date}")

    c.setFillColor(colors.HexColor("#718096"))
    c.setFont("Helvetica", 8.5)
    c.drawString(60, 95, f"Certificate ID: {certificate_id}")
    c.drawString(60, 80, "Verify status online via QR code")

    # Center Block: Verification QR Code Widget
    qr_size = 62
    qr_x = (width / 2) - (qr_size / 2)
    qr_y = 65
    try:
        qr_widget = QrCodeWidget(verification_url)
        qr_widget.barWidth = qr_size
        qr_widget.barHeight = qr_size
        d = Drawing(qr_size, qr_size)
        d.add(qr_widget)
        d.drawOn(c, qr_x, qr_y)

        c.setFillColor(colors.HexColor("#718096"))
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(width / 2, qr_y - 12, "Scan to Verify Authenticity")
    except Exception:
        # Graceful fallback if QR widget fails
        c.setFillColor(colors.HexColor("#718096"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2, qr_y + 20, "[ Official Verification Seal ]")

    # Right Block: Signatory
    sig_x = width - 210
    draw_signature_flourish(c, sig_x, 112)

    c.setStrokeColor(colors.HexColor("#A0AEC0"))
    c.setLineWidth(1)
    c.line(sig_x, 105, sig_x + 150, 105)

    c.setFillColor(colors.HexColor("#0D2040"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(sig_x + 75, 90, "Authorized Signatory")

    c.setFillColor(colors.HexColor("#718096"))
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(sig_x + 75, 76, issuer_name)

    # Finish and save
    c.save()

    file_size = os.path.getsize(output_path)
    return output_path, file_size
