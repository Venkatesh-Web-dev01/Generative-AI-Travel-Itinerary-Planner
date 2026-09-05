"""
app.py
------
Streamlit UI and session-state orchestration for the Generative AI Travel
Itinerary Planner.

Run with:
    streamlit run app.py
"""

import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import calendar_export
import pdf_export
from itinerary_generator import generate_itinerary, modify_itinerary

# ---------------------------------------------------------------------------
# 0. App configuration & environment setup
# ---------------------------------------------------------------------------
load_dotenv()  # picks up GOOGLE_API_KEY / GEMINI_MODEL from a local .env file, if present

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DESTINATIONS_PATH = os.path.join(APP_DIR, "data", "sample_destinations.csv")

INTEREST_OPTIONS = [
    "Adventure", "History", "Culture", "Food", "Shopping", "Beaches", "Nature",
    "Photography", "Nightlife", "Museums", "Architecture", "Family activities",
    "Religious sites",
]

st.set_page_config(page_title="AI Travel Itinerary Planner", page_icon="✈️", layout="wide")
st.title("✈️ Generative AI Travel Itinerary Planner")
st.caption(
    "Describe your trip, get a personalized day-by-day itinerary, refine it by chatting, "
    "then export it as a PDF or calendar file."
)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
def init_state():
    defaults = {
        "itinerary": None,
        "trip_inputs": None,
        "start_date": None,
        "chat_history": [],  # list of {"role": "user"/"assistant", "content": str}
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
@st.cache_data
def load_sample_destinations() -> pd.DataFrame:
    try:
        return pd.read_csv(SAMPLE_DESTINATIONS_PATH)
    except Exception:
        return pd.DataFrame(columns=["destination", "country", "famous_for", "suggested_duration_days", "typical_daily_budget_inr"])


def validate_inputs(destination, duration_days, budget, travelers) -> str:
    """Return an error message string, or '' if everything looks valid."""
    if not destination or not destination.strip():
        return "Please enter a destination."
    if duration_days is None or duration_days < 1:
        return "Trip duration must be at least 1 day."
    if budget is None or budget < 0:
        return "Budget cannot be negative."
    if travelers is None or travelers < 1:
        return "Number of travelers must be at least 1."
    return ""


def money(value) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# 1. Trip Planning Form (sidebar)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🧳 Trip Details")

    sample_df = load_sample_destinations()
    quick_pick_options = ["Custom (type below)"] + sample_df["destination"].tolist() if not sample_df.empty else ["Custom (type below)"]
    quick_pick = st.selectbox("Popular destination (optional)", quick_pick_options)

    default_destination = "" if quick_pick == "Custom (type below)" else quick_pick
    destination = st.text_input("Destination", value=default_destination, placeholder="e.g. Hyderabad, India")
    starting_location = st.text_input("Starting Location", placeholder="e.g. Mumbai, India")

    col_a, col_b = st.columns(2)
    with col_a:
        start_date = st.date_input("Start Date", value=date.today() + timedelta(days=30))
    with col_b:
        duration_days = st.number_input("Duration (days)", min_value=1, max_value=30, value=4, step=1)

    end_date = start_date + timedelta(days=int(duration_days) - 1)
    st.caption(f"📅 Travel Dates: {start_date.isoformat()} → {end_date.isoformat()}")

    budget = st.number_input("Total Budget", min_value=0, value=25000, step=500)
    travelers = st.number_input("Number of Travelers", min_value=1, value=2, step=1)

    st.subheader("Interests")
    interests = st.multiselect("Select interests", INTEREST_OPTIONS, default=["History", "Food"])

    travel_style = st.selectbox("Travel Style", ["Relaxed", "Balanced", "Packed"], index=1)
    food_preferences = st.selectbox("Food Preference", ["Local", "Vegetarian", "Vegan", "Any"], index=3)
    accommodation = st.selectbox("Accommodation Preference", ["Budget", "Mid-range", "Luxury", "Any"], index=3)
    transportation = st.selectbox("Transportation Preference", ["Public Transport", "Taxi", "Rental Car"], index=1)

    st.divider()
    st.subheader("🔑 Gemini API Key")
    env_key_present = bool(os.getenv("GOOGLE_API_KEY"))
    api_key = st.text_input(
        "Enter your Gemini API key (optional)",
        type="password",
        help="Leave blank to use GOOGLE_API_KEY from your .env file, or the offline demo generator if none is set.",
    )
    if not api_key and env_key_present:
        st.caption("✅ Using GOOGLE_API_KEY found in your environment/.env file.")
    elif not api_key and not env_key_present:
        st.caption("ℹ️ No API key found — a demo/fallback itinerary will be generated instead.")


# ---------------------------------------------------------------------------
# 2. Generate My Itinerary
# ---------------------------------------------------------------------------
st.header("Generate My Itinerary")
generate_clicked = st.button("🪄 Generate My Itinerary", type="primary")

if generate_clicked:
    error_message = validate_inputs(destination, duration_days, budget, travelers)
    if error_message:
        st.error(f"⚠️ {error_message}")
    else:
        trip_inputs = {
            "destination": destination.strip(),
            "starting_location": starting_location.strip(),
            "duration_days": int(duration_days),
            "travel_dates": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "budget": float(budget),
            "currency": "",
            "travelers": int(travelers),
            "interests": interests,
            "travel_style": travel_style,
            "food_preferences": food_preferences,
            "accommodation": accommodation,
            "transportation": transportation,
        }
        with st.spinner("Planning your trip..."):
            try:
                itinerary = generate_itinerary(trip_inputs, api_key)
            except Exception as exc:  # noqa: BLE001 - never crash the app over a generation failure
                st.error(f"⚠️ Something went wrong while generating your itinerary: {exc}")
                itinerary = None

        if itinerary:
            st.session_state["itinerary"] = itinerary
            st.session_state["trip_inputs"] = trip_inputs
            st.session_state["start_date"] = start_date
            st.session_state["chat_history"] = []
            st.success("✅ Your itinerary is ready! Scroll down to view it.")


# ---------------------------------------------------------------------------
# 3. Display the itinerary
# ---------------------------------------------------------------------------
itinerary = st.session_state.get("itinerary")

if itinerary:
    trip = itinerary.get("trip_summary", {})
    budget_summary = itinerary.get("budget_summary", {})
    days = itinerary.get("days", [])
    tips = itinerary.get("travel_tips", [])

    st.divider()
    st.header("🌍 Your Trip")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Destination", trip.get("destination", "-"))
    c2.metric("Duration", f"{trip.get('duration_days', '-')} days")
    c3.metric("Travelers", trip.get("travelers", "-"))
    c4.metric("Budget", money(trip.get("budget", 0)))
    st.caption(
        f"📅 {trip.get('travel_dates', '-')}  •  🎯 Interests: {', '.join(trip.get('interests', []) or []) or '-'}  •  "
        f"🚕 {trip.get('transportation', '-')}  •  🍽️ {trip.get('food_preferences', '-')}"
    )

    # ---- Budget warning -----------------------------------------------------
    remaining = budget_summary.get("remaining", 0)
    if isinstance(remaining, (int, float)) and remaining < 0:
        st.warning(
            f"⚠️ Estimated trip cost exceeds your budget by **{money(abs(remaining))}**. "
            f"Try telling the chat below: *\"Make it cheaper.\"*"
        )

    # ---- Day-by-day itinerary -------------------------------------------------
    for day in days:
        st.subheader(f"Day {day.get('day_number', '?')}")
        st.markdown("─" * 24)

        morning = day.get("morning", {})
        afternoon = day.get("afternoon", {})
        evening = day.get("evening", {})
        food = day.get("food", {})
        transport = day.get("transportation", {})

        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"**🌅 Morning — {morning.get('activity', '-')}**")
            st.caption(
                f"📍 {morning.get('location', '-')} · ⏱️ {morning.get('duration', '-')} · "
                f"💰 {money(morning.get('cost', 0))} (estimate)"
            )
            if food.get("breakfast"):
                st.markdown(f"**🍳 Breakfast:** {food.get('breakfast')}")

            st.markdown(f"**🌆 Afternoon — {afternoon.get('activity', '-')}**")
            st.caption(
                f"📍 {afternoon.get('location', '-')} · ⏱️ {afternoon.get('duration', '-')} · "
                f"💰 {money(afternoon.get('cost', 0))} (estimate)"
            )
            if food.get("lunch"):
                st.markdown(f"**🍛 Lunch:** {food.get('lunch')}")

            st.markdown(f"**🌙 Evening — {evening.get('activity', '-')}**")
            st.caption(
                f"📍 {evening.get('location', '-')} · ⏱️ {evening.get('duration', '-')} · "
                f"💰 {money(evening.get('cost', 0))} (estimate)"
            )
            if food.get("dinner"):
                st.markdown(f"**🍽️ Dinner:** {food.get('dinner')}")

        with col2:
            st.markdown("**🚗 Transportation**")
            st.caption(
                f"{transport.get('recommended', '-')}\n\n"
                f"⏱️ {transport.get('travel_time', '-')}\n\n"
                f"💰 {money(transport.get('cost', 0))} (estimate)"
            )
            logistics = day.get("logistics") or []
            if logistics:
                st.markdown("**🗺️ Route**")
                st.caption(" → ".join(str(s) for s in logistics))

        st.markdown(f"**Estimated Cost for Day {day.get('day_number', '?')}: {money(day.get('daily_estimated_cost', 0))}**")
        st.divider()

    # ---- Budget summary table -----------------------------------------------
    st.subheader("💰 Budget Summary (Estimates)")
    budget_rows = [
        ("Accommodation", budget_summary.get("accommodation", 0)),
        ("Food", budget_summary.get("food", 0)),
        ("Transportation", budget_summary.get("transportation", 0)),
        ("Activities", budget_summary.get("activities", 0)),
        ("Shopping", budget_summary.get("shopping", 0)),
        ("Miscellaneous", budget_summary.get("miscellaneous", 0)),
        ("Estimated Total", budget_summary.get("estimated_total", 0)),
        ("User Budget", budget_summary.get("user_budget", 0)),
        ("Remaining", budget_summary.get("remaining", 0)),
    ]
    budget_df = pd.DataFrame(budget_rows, columns=["Category", "Amount"])
    budget_df["Amount"] = budget_df["Amount"].apply(money)
    st.table(budget_df.set_index("Category"))

    # ---- Travel tips ----------------------------------------------------------
    if tips:
        st.subheader("💡 Travel Tips")
        for tip in tips:
            st.markdown(f"- {tip}")

    st.caption(
        "🛈 All costs, durations, opening hours, and travel times shown are ESTIMATES only, "
        "unless verified through a current external source. Please confirm details before you travel."
    )

    # -------------------------------------------------------------------------
    # 4. AI Travel Chat Interface
    # -------------------------------------------------------------------------
    st.divider()
    st.header("💬 Modify Your Trip")
    st.caption(
        "Try things like: \"Make day 2 less packed\", \"Add more food spots\", "
        "\"Reduce the budget to ₹20,000\", \"Add a beach activity on day 3\"."
    )

    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_message = st.chat_input("Type your request...")

    if user_message:
        st.session_state["chat_history"].append({"role": "user", "content": user_message})
        with st.spinner("Updating your itinerary..."):
            try:
                result = modify_itinerary(st.session_state["itinerary"], user_message, api_key)
                st.session_state["itinerary"] = result["updated_itinerary"]
                assistant_reply = result["assistant_reply"]
            except Exception as exc:  # noqa: BLE001
                assistant_reply = f"⚠️ Sorry, I couldn't apply that change: {exc}"
        st.session_state["chat_history"].append({"role": "assistant", "content": assistant_reply})
        st.rerun()

    # -------------------------------------------------------------------------
    # 5. Export & Regenerate
    # -------------------------------------------------------------------------
    st.divider()
    col_pdf, col_ics, col_regen = st.columns(3)

    with col_pdf:
        try:
            pdf_bytes = pdf_export.build_pdf(st.session_state["itinerary"])
            st.download_button(
                "📄 Download PDF",
                data=pdf_bytes,
                file_name=pdf_export.safe_filename(trip.get("destination", "trip")),
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"⚠️ Couldn't generate the PDF: {exc}")

    with col_ics:
        try:
            trip_start_date = st.session_state.get("start_date") or date.today()
            ics_content = calendar_export.build_ics(st.session_state["itinerary"], trip_start_date)
            st.download_button(
                "📅 Export Calendar",
                data=ics_content.encode("utf-8"),
                file_name=calendar_export.safe_filename(trip.get("destination", "trip")),
                mime="text/calendar",
                use_container_width=True,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"⚠️ Couldn't generate the calendar file: {exc}")

    with col_regen:
        if st.button("🔄 Regenerate", use_container_width=True):
            trip_inputs = st.session_state.get("trip_inputs")
            if trip_inputs:
                with st.spinner("Regenerating your itinerary..."):
                    try:
                        st.session_state["itinerary"] = generate_itinerary(trip_inputs, api_key)
                        st.session_state["chat_history"] = []
                        st.success("✅ Itinerary regenerated.")
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"⚠️ Couldn't regenerate the itinerary: {exc}")
else:
    st.info("👈 Fill in your trip details in the sidebar, then click **Generate My Itinerary** to get started.")
