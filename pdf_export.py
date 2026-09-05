"""
pdf_export.py
-------------
Generates a professional, shareable PDF of a travel itinerary using
ReportLab. All content comes from the itinerary dict produced by
itinerary_generator.py - this module only handles layout/formatting.
"""

import io
from typing import Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _currency(value) -> str:
    """Format a number as a plain, readable amount (no assumed currency symbol
    beyond what the itinerary itself already uses in its text fields)."""
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def build_pdf(itinerary: Dict) -> bytes:
    """
    Build the itinerary PDF and return it as raw bytes, ready to hand to a
    Streamlit download_button or write to disk.

    Raises any ReportLab/layout exception to the caller - app.py is
    responsible for catching it and showing a friendly error message.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Travel Itinerary",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=22, spaceAfter=6)
    h2 = ParagraphStyle("H2Custom", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1f4e79"))
    h3 = ParagraphStyle("H3Custom", parent=styles["Heading3"], spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#2e75b6"))
    body = ParagraphStyle("BodyCustom", parent=styles["BodyText"], fontSize=10, leading=14)
    small_italic = ParagraphStyle("SmallItalic", parent=styles["BodyText"], fontSize=8.5, textColor=colors.grey, leading=11)

    trip = itinerary.get("trip_summary", {}) or {}
    budget = itinerary.get("budget_summary", {}) or {}
    days = itinerary.get("days", []) or []
    tips = itinerary.get("travel_tips", []) or []

    story = []

    # ---- Title / trip header -------------------------------------------------
    destination = trip.get("destination", "Your Trip")
    story.append(Paragraph(f"Travel Itinerary: {destination}", title_style))
    story.append(
        Paragraph(
            "All costs, durations, and travel times shown are ESTIMATES only, unless "
            "verified through a current external source. Please confirm prices, opening "
            "hours, and availability before you travel.",
            small_italic,
        )
    )
    story.append(Spacer(1, 10))

    summary_rows = [
        ["Destination", str(trip.get("destination", "-"))],
        ["Starting Location", str(trip.get("starting_location", "-"))],
        ["Travel Dates", str(trip.get("travel_dates", "-"))],
        ["Duration", f"{trip.get('duration_days', '-')} day(s)"],
        ["Travelers", str(trip.get("travelers", "-"))],
        ["Travel Style", str(trip.get("travel_style", "-"))],
        ["Interests", ", ".join(trip.get("interests", []) or []) or "-"],
        ["Food Preferences", str(trip.get("food_preferences", "-"))],
        ["Transportation", str(trip.get("transportation", "-"))],
        ["Budget", _currency(trip.get("budget", 0))],
    ]
    summary_table = Table(summary_rows, colWidths=[4.5 * cm, 11 * cm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1f4e79")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#1f4e79"), thickness=1))

    # ---- Day-by-day itinerary --------------------------------------------------
    for day in days:
        story.append(Paragraph(f"Day {day.get('day_number', '?')}", h2))

        for slot_key, slot_label, emoji in (
            ("morning", "Morning", "Morning"),
            ("afternoon", "Afternoon", "Afternoon"),
            ("evening", "Evening", "Evening"),
        ):
            slot = day.get(slot_key, {}) or {}
            story.append(Paragraph(f"{emoji}: {slot.get('activity', '-')}", h3))
            details = (
                f"Location: {slot.get('location', '-')} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Duration: {slot.get('duration', '-')} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Estimated Cost: {_currency(slot.get('cost', 0))}"
            )
            story.append(Paragraph(details, body))

        food = day.get("food", {}) or {}
        story.append(Paragraph("Food Recommendations", h3))
        food_lines = "<br/>".join(
            f"<b>{meal.capitalize()}:</b> {desc}" for meal, desc in food.items() if desc
        )
        if food_lines:
            story.append(Paragraph(food_lines, body))

        transport = day.get("transportation", {}) or {}
        story.append(Paragraph("Transportation", h3))
        story.append(
            Paragraph(
                f"Recommended: {transport.get('recommended', '-')} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Travel Time: {transport.get('travel_time', '-')} &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Estimated Cost: {_currency(transport.get('cost', 0))}",
                body,
            )
        )

        logistics = day.get("logistics") or []
        if logistics:
            story.append(Paragraph("Route: " + "  &#8594;  ".join(str(s) for s in logistics), small_italic))

        story.append(Paragraph(f"<b>Daily Estimated Cost: {_currency(day.get('daily_estimated_cost', 0))}</b>", body))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#dddddd"), thickness=0.5))

    # ---- Budget summary ---------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Budget Summary (Estimates)", h2))

    budget_rows = [["Category", "Estimated Amount"]]
    for label, key in (
        ("Accommodation", "accommodation"),
        ("Food", "food"),
        ("Transportation", "transportation"),
        ("Activities", "activities"),
        ("Shopping", "shopping"),
        ("Miscellaneous", "miscellaneous"),
    ):
        budget_rows.append([label, _currency(budget.get(key, 0))])
    budget_rows.append(["Estimated Total", _currency(budget.get("estimated_total", 0))])
    budget_rows.append(["User Budget", _currency(budget.get("user_budget", 0))])
    budget_rows.append(["Remaining", _currency(budget.get("remaining", 0))])

    budget_table = Table(budget_rows, colWidths=[8 * cm, 7 * cm])
    budget_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -3), (-1, -3), 1, colors.HexColor("#1f4e79")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ]
        )
    )
    story.append(budget_table)

    remaining = budget.get("remaining", 0)
    if isinstance(remaining, (int, float)) and remaining < 0:
        story.append(Spacer(1, 8))
        story.append(
            Paragraph(
                f"<font color='red'><b>Warning:</b> The estimated total exceeds the user's "
                f"budget by {_currency(abs(remaining))}.</font>",
                body,
            )
        )

    # ---- Travel tips -------------------------------------------------------------
    if tips:
        story.append(Spacer(1, 16))
        story.append(Paragraph("Travel Tips", h2))
        for tip in tips:
            story.append(Paragraph(f"- {tip}", body))

    story.append(Spacer(1, 16))
    story.append(
        Paragraph(
            "Generated by the Generative AI Travel Itinerary Planner. Verify all prices, "
            "opening hours, and availability before you travel.",
            small_italic,
        )
    )

    doc.build(story)
    return buffer.getvalue()


def safe_filename(destination: str) -> str:
    """Turn a destination string into a safe PDF filename, e.g. 'Hyderabad, India' -> 'travel_itinerary_hyderabad.pdf'."""
    slug = "".join(c.lower() if c.isalnum() else "_" for c in (destination or "trip"))
    slug = "_".join(filter(None, slug.split("_")))[:40] or "trip"
    return f"travel_itinerary_{slug}.pdf"
