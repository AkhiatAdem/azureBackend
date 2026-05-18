"""
core/utils.py
Utility functions for PDF ticket generation.
Uses python-qrcode + Pillow for high-resolution QR codes and
ReportLab for PDF layout/rendering.
"""

import qrcode
import qrcode.constants
from io import BytesIO
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A6
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, Image,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_qr_image(data: str, box_size: int = 12, border: int = 2) -> BytesIO:
    """
    Generate a high-resolution QR code PNG using python-qrcode.

    Args:
        data:     The string to encode (URL or plain text).
        box_size: Pixel size of each QR module.  Higher = sharper at large sizes.
        border:   Quiet-zone thickness in modules.

    Returns:
        A seeked BytesIO containing the PNG image bytes.
    """
    qr = qrcode.QRCode(
        version=None,                             # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30 % recovery
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img: PILImage.Image = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_ticket_pdf(
    movie_title: str,
    date,
    time,
    room_name: str,
    seats: str,
    ticket_uuid=None,
    base_url: str = "http://127.0.0.1:8000",
) -> BytesIO:
    """
    Generate a professional cinema-style PDF ticket on A6 paper.

    Args:
        movie_title:  Title of the movie.
        date:         Screening date (date or str).
        time:         Screening start time (int minutes or str).
        room_name:    Name of the hall / room.
        seats:        Comma-separated seat labels, e.g. "A1, A2".
        ticket_uuid:  UUID of the Ticket instance.  When provided, the QR code
                      encodes the verification URL.  Falls back to a hash-based
                      placeholder when None.
        base_url:     Base URL used to build the QR verification link.

    Returns:
        A seeked BytesIO containing the finished PDF bytes.
    """
    # ------------------------------------------------------------------ #
    # 1.  Build QR payload & image                                        #
    # ------------------------------------------------------------------ #
    if ticket_uuid is not None:
        qr_payload = f"{base_url}/tickets/{ticket_uuid}/verify/"
    else:
        qr_payload = f"CINEMA|{movie_title}|{seats}|{date}"

    qr_buf = _build_qr_image(qr_payload, box_size=12, border=2)

    # ------------------------------------------------------------------ #
    # 2.  Colour palette                                                  #
    # ------------------------------------------------------------------ #
    DARK_BG     = colors.HexColor("#0D0D0D")
    CARD_BG     = colors.HexColor("#1A1A2E")
    ACCENT      = colors.HexColor("#E50914")   # cinema red
    GOLD        = colors.HexColor("#F5C518")   # IMDb-style gold
    TEXT_WHITE  = colors.white
    TEXT_MUTED  = colors.HexColor("#9E9E9E")
    DIVIDER     = colors.HexColor("#2C2C3E")

    # ------------------------------------------------------------------ #
    # 3.  Typography styles                                               #
    # ------------------------------------------------------------------ #
    brand_style = ParagraphStyle(
        "Brand",
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=ACCENT,
        letterSpacing=3,
        spaceAfter=0,
    )
    tagline_style = ParagraphStyle(
        "Tagline",
        fontName="Helvetica",
        fontSize=6,
        textColor=TEXT_MUTED,
        spaceAfter=0,
    )
    hero_style = ParagraphStyle(
        "Hero",
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=TEXT_WHITE,
        leading=22,
        spaceAfter=2,
    )
    label_style = ParagraphStyle(
        "Label",
        fontName="Helvetica-Bold",
        fontSize=6,
        textColor=TEXT_MUTED,
        letterSpacing=1.5,
        spaceAfter=1,
    )
    value_style = ParagraphStyle(
        "Value",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=TEXT_WHITE,
        leading=13,
    )
    seat_style = ParagraphStyle(
        "Seat",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=GOLD,
        leading=24,
    )
    fine_print_style = ParagraphStyle(
        "FinePrint",
        fontName="Helvetica",
        fontSize=5.5,
        textColor=TEXT_MUTED,
        leading=7,
    )
    scan_label_style = ParagraphStyle(
        "ScanLabel",
        fontName="Helvetica-Bold",
        fontSize=6,
        textColor=ACCENT,
        letterSpacing=1.5,
        alignment=1,   # centred
    )

    # ------------------------------------------------------------------ #
    # 4.  Page background callback                                        #
    # ------------------------------------------------------------------ #
    def draw_background(canvas, doc):
        """Paint the dark cinema-card background on every page."""
        canvas.saveState()
        w, h = A6

        # Outermost fill
        canvas.setFillColor(DARK_BG)
        canvas.rect(0, 0, w, h, fill=1, stroke=0)

        # Inner card with rounded corners
        canvas.setFillColor(CARD_BG)
        canvas.roundRect(4 * mm, 4 * mm, w - 8 * mm, h - 8 * mm,
                         radius=5, fill=1, stroke=0)

        # Top accent strip
        canvas.setFillColor(ACCENT)
        canvas.roundRect(4 * mm, h - 14 * mm, w - 8 * mm, 10 * mm,
                         radius=5, fill=1, stroke=0)

        # Decorative side notches (tear-line circles)
        canvas.setFillColor(DARK_BG)
        mid_y = 38 * mm
        canvas.circle(0, mid_y, 4 * mm, fill=1, stroke=0)
        canvas.circle(w, mid_y, 4 * mm, fill=1, stroke=0)

        canvas.restoreState()

    # ------------------------------------------------------------------ #
    # 5.  Build flowable elements                                         #
    # ------------------------------------------------------------------ #
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A6,
        rightMargin=9 * mm,
        leftMargin=9 * mm,
        topMargin=16 * mm,   # leave room for accent strip
        bottomMargin=7 * mm,
    )

    elements = []

    # — Brand header (sits just below accent strip) —
    elements.append(Paragraph("✦ PREMIUM CINEMA PASS", brand_style))
    elements.append(Paragraph("Your digital ticket — keep it safe", tagline_style))
    elements.append(Spacer(1, 5 * mm))

    # — Movie title —
    elements.append(Paragraph(movie_title.upper(), hero_style))
    elements.append(Spacer(1, 3 * mm))

    # — Info grid: DATE | TIME | HALL —
    def info_cell(label_text, value_text):
        return [
            Paragraph(label_text, label_style),
            Paragraph(value_text, value_style),
        ]

    # Format time nicely: stored as minutes from midnight
    try:
        total_minutes = int(time)
        h_part, m_part = divmod(total_minutes, 60)
        time_display = f"{h_part:02d}:{m_part:02d}"
    except (TypeError, ValueError):
        time_display = str(time)

    info_data = [
        [
            Paragraph("DATE", label_style),
            Paragraph("TIME", label_style),
            Paragraph("HALL", label_style),
        ],
        [
            Paragraph(str(date), value_style),
            Paragraph(time_display, value_style),
            Paragraph(room_name, value_style),
        ],
    ]
    usable_width = A6[0] - 18 * mm   # total width minus margins
    col_w = usable_width / 3
    info_table = Table(info_data, colWidths=[col_w, col_w, col_w])
    info_table.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ("TOPPADDING",  (0, 0), (-1, -1), 0),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4 * mm))

    # — Seats —
    elements.append(Paragraph("SEAT(S)", label_style))
    elements.append(Paragraph(seats, seat_style))
    elements.append(Spacer(1, 4 * mm))

    # — Tear-line divider with notch hint —
    elements.append(HRFlowable(
        width="100%",
        thickness=0.8,
        color=DIVIDER,
        dash=(3, 3),
    ))
    elements.append(Spacer(1, 3 * mm))

    # — QR code + caption — centred using a single-cell table —
    qr_size = 55   # points (~19 mm) — large enough for easy scanning
    qr_image = Image(qr_buf, width=qr_size, height=qr_size)

    qr_cell_content = [
        qr_image,
        Paragraph("SCAN TO VERIFY", scan_label_style),
        Paragraph(
            "Non-transferable · Valid for one entry only",
            fine_print_style,
        ),
    ]

    # Right column: fine print text
    right_col = [
        Spacer(1, 4),
        Paragraph("TICKET ID", label_style),
        Paragraph(
            str(ticket_uuid)[:18] + "…" if ticket_uuid else "N/A",
            fine_print_style,
        ),
        Spacer(1, 6),
        Paragraph(
            "Present this ticket at the entrance. "
            "Screenshot or printout accepted.",
            fine_print_style,
        ),
    ]

    footer_data = [[qr_cell_content, right_col]]
    footer_table = Table(
        footer_data,
        colWidths=[qr_size + 6, usable_width - qr_size - 6],
    )
    footer_table.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    elements.append(footer_table)

    # ------------------------------------------------------------------ #
    # 6.  Build & return                                                  #
    # ------------------------------------------------------------------ #
    doc.build(elements, onFirstPage=draw_background, onLaterPages=draw_background)
    buffer.seek(0)
    return buffer