"""
itinerary_generator.py
-----------------------
All AI logic for the Travel Itinerary Planner lives here:

  - generate_itinerary(...)   -> builds a brand-new day-by-day itinerary
  - modify_itinerary(...)     -> updates an EXISTING itinerary based on a
                                  natural-language chat instruction, while
                                  preserving everything the user didn't ask
                                  to change
  - a fully offline fallback generator/modifier used whenever no Gemini API
    key is configured, the API call fails, or the response can't be parsed

The itinerary is represented as a plain Python dict (JSON-serializable) with
this shape:

{
  "trip_summary": {
      "destination": str, "starting_location": str, "duration_days": int,
      "travel_dates": str, "travelers": int, "budget": number,
      "travel_style": str, "interests": [str, ...],
      "food_preferences": str, "transportation": str
  },
  "days": [
      {
        "day_number": int,
        "morning": {"activity": str, "location": str, "duration": str, "cost": number},
        "afternoon": {...},
        "evening": {...},
        "food": {"breakfast": str, "lunch": str, "dinner": str},
        "transportation": {"recommended": str, "travel_time": str, "cost": number},
        "logistics": [str, ...],           # ordered stops for the day, e.g. ["Hotel", "Charminar", ...]
        "daily_estimated_cost": number
      },
      ...
  ],
  "budget_summary": {
      "accommodation": number, "food": number, "transportation": number,
      "activities": number, "shopping": number, "miscellaneous": number,
      "estimated_total": number, "user_budget": number, "remaining": number
  },
  "travel_tips": [str, ...]
}
"""

import json
import os
import re
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

REQUIRED_TOP_KEYS = ("trip_summary", "days", "budget_summary", "travel_tips")
REQUIRED_DAY_KEYS = ("day_number", "morning", "afternoon", "evening", "food", "transportation")


# ---------------------------------------------------------------------------
# API key / model helpers
# ---------------------------------------------------------------------------
def resolve_api_key(user_supplied_key: Optional[str]) -> Optional[str]:
    """Prefer a key typed into the UI; otherwise fall back to the environment."""
    if user_supplied_key:
        return user_supplied_key.strip()
    env_key = os.getenv("GOOGLE_API_KEY")
    return env_key.strip() if env_key else None


def _safe_num(value, default=0) -> float:
    """Best-effort conversion of a value to a number, stripping currency symbols."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value
    cleaned = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(cleaned) if cleaned else default
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------
def _build_generation_prompt(inputs: Dict) -> str:
    interests_str = ", ".join(inputs.get("interests") or []) or "general sightseeing"
    return f"""You are an expert travel planner.

Create a personalized, realistic, day-by-day travel itinerary using ONLY the
information supplied below. Do not invent precise facts (exact prices,
opening hours, or business names) you cannot reasonably estimate - clearly
label all costs and timings as ESTIMATES.

DESTINATION:
{inputs.get('destination')}

STARTING LOCATION:
{inputs.get('starting_location') or 'Not specified'}

DURATION:
{inputs.get('duration_days')} days

TRAVEL DATES:
{inputs.get('travel_dates') or 'Not specified'}

BUDGET:
{inputs.get('budget')} {inputs.get('currency', '')}

TRAVELERS:
{inputs.get('travelers')}

INTERESTS:
{interests_str}

TRAVEL STYLE:
{inputs.get('travel_style')}

FOOD PREFERENCES:
{inputs.get('food_preferences')}

TRANSPORTATION PREFERENCE:
{inputs.get('transportation')}

ACCOMMODATION PREFERENCE:
{inputs.get('accommodation') or 'Not specified'}

Requirements:
1. Create a day-by-day itinerary, one entry per day, numbered sequentially.
2. Each day must include a morning, afternoon, and evening activity.
3. Include an estimated cost (a number, in the same currency as the budget) for every activity.
4. Include breakfast, lunch, and dinner food recommendations for every day.
5. Include a recommended transportation method, approximate travel time, and estimated cost for each day.
6. Keep the total itinerary within the user's budget when realistically possible.
7. Order each day's activities to avoid unnecessary backtracking; include a "logistics" list of
   stop names in visiting order (e.g. ["Hotel", "Charminar", "Local Restaurant", "Laad Bazaar", "Hotel"]).
8. Prioritize activities that match the user's selected interests.
9. Clearly label costs and times as estimates within the text fields themselves where relevant.
10. Do not invent information you are not reasonably confident about.
11. Keep the itinerary realistic and practical for the destination.
12. Also produce a budget_summary that breaks the ESTIMATED TOTAL trip cost into:
    accommodation, food, transportation, activities, shopping, miscellaneous - plus
    estimated_total, user_budget (the number supplied above), and remaining (user_budget - estimated_total).
13. Include 3-6 short, practical travel_tips (e.g. local customs, weather, safety, connectivity).

Return ONLY valid JSON (no markdown fences, no commentary) in EXACTLY this shape:
{{
  "trip_summary": {{
    "destination": "...", "starting_location": "...", "duration_days": {inputs.get('duration_days')},
    "travel_dates": "...", "travelers": {inputs.get('travelers')}, "budget": {inputs.get('budget')},
    "travel_style": "...", "interests": {json.dumps(inputs.get('interests') or [])},
    "food_preferences": "...", "transportation": "..."
  }},
  "days": [
    {{
      "day_number": 1,
      "morning": {{"activity": "...", "location": "...", "duration": "...", "cost": 0}},
      "afternoon": {{"activity": "...", "location": "...", "duration": "...", "cost": 0}},
      "evening": {{"activity": "...", "location": "...", "duration": "...", "cost": 0}},
      "food": {{"breakfast": "...", "lunch": "...", "dinner": "..."}},
      "transportation": {{"recommended": "...", "travel_time": "...", "cost": 0}},
      "logistics": ["Hotel", "...", "Hotel"],
      "daily_estimated_cost": 0
    }}
  ],
  "budget_summary": {{
    "accommodation": 0, "food": 0, "transportation": 0, "activities": 0,
    "shopping": 0, "miscellaneous": 0, "estimated_total": 0,
    "user_budget": {inputs.get('budget')}, "remaining": 0
  }},
  "travel_tips": ["...", "..."]
}}"""


def _build_modification_prompt(current_itinerary: Dict, user_message: str) -> str:
    return f"""You are an expert travel planner assistant helping a user refine an
EXISTING itinerary through natural-language chat requests.

CURRENT ITINERARY (JSON):
{json.dumps(current_itinerary, ensure_ascii=False)}

USER REQUEST:
"{user_message}"

Instructions:
1. Apply ONLY the change(s) the user asked for.
2. Preserve every other part of the itinerary EXACTLY as it is unless the
   requested change requires adjusting it (e.g. reducing the budget may
   require swapping some paid activities for cheaper ones).
3. Keep the same overall JSON structure as the input.
4. Recalculate "daily_estimated_cost" for any day you changed, and
   recalculate "budget_summary" (accommodation, food, transportation,
   activities, shopping, miscellaneous, estimated_total, remaining) to stay
   consistent with the updated itinerary.
5. Do not invent precise facts you can't reasonably estimate; label costs and
   times as estimates.
6. Also write a short (1-2 sentence), friendly, past-tense confirmation
   message describing exactly what you changed, to show the user in chat.

Return ONLY valid JSON (no markdown fences, no commentary) in EXACTLY this shape:
{{
  "updated_itinerary": {{ ... same shape as the current itinerary ... }},
  "assistant_reply": "..."
}}"""


# ---------------------------------------------------------------------------
# JSON parsing helpers (shared by generation + modification)
# ---------------------------------------------------------------------------
def _extract_json(raw_text: str) -> Dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _validate_itinerary(data: Dict) -> bool:
    if not isinstance(data, dict):
        return False
    if any(key not in data for key in REQUIRED_TOP_KEYS):
        return False
    if not isinstance(data["days"], list) or len(data["days"]) == 0:
        return False
    for day in data["days"]:
        if any(key not in day for key in REQUIRED_DAY_KEYS):
            return False
    return True


def _recalculate_budget_summary(itinerary: Dict) -> Dict:
    """
    Recompute a consistent budget_summary from the days list. Used both by
    the offline fallback and as a safety net after AI edits, so numbers
    never drift out of sync with the actual itinerary content.
    """
    activities_total = 0.0
    transport_total = 0.0
    for day in itinerary.get("days", []):
        for slot in ("morning", "afternoon", "evening"):
            activities_total += _safe_num(day.get(slot, {}).get("cost"))
        transport_total += _safe_num(day.get("transportation", {}).get("cost"))

    existing = itinerary.get("budget_summary", {}) or {}
    food_total = _safe_num(existing.get("food")) or (len(itinerary.get("days", [])) * 800)
    accommodation_total = _safe_num(existing.get("accommodation")) or (
        len(itinerary.get("days", [])) * 1500
    )
    shopping_total = _safe_num(existing.get("shopping"))
    misc_total = _safe_num(existing.get("miscellaneous")) or 500

    estimated_total = (
        accommodation_total + food_total + transport_total + activities_total + shopping_total + misc_total
    )
    user_budget = _safe_num(itinerary.get("trip_summary", {}).get("budget"))

    return {
        "accommodation": round(accommodation_total, 2),
        "food": round(food_total, 2),
        "transportation": round(transport_total, 2),
        "activities": round(activities_total, 2),
        "shopping": round(shopping_total, 2),
        "miscellaneous": round(misc_total, 2),
        "estimated_total": round(estimated_total, 2),
        "user_budget": round(user_budget, 2),
        "remaining": round(user_budget - estimated_total, 2),
    }


# ---------------------------------------------------------------------------
# Offline fallback: itinerary generation
# ---------------------------------------------------------------------------
_INTEREST_ACTIVITY_TEMPLATES = {
    "history": ("Explore a historic landmark", "Old Town / Historic District"),
    "historical places": ("Explore a historic landmark", "Old Town / Historic District"),
    "culture": ("Visit a cultural center or heritage site", "Cultural District"),
    "food": ("Food tasting walk at a local market", "Local Food Market"),
    "shopping": ("Browse a popular local market or bazaar", "Central Market"),
    "photography": ("Visit a scenic viewpoint for photos", "Scenic Viewpoint"),
    "nature": ("Walk through a park or garden", "City Park / Botanical Garden"),
    "adventure": ("Try a local outdoor adventure activity", "Adventure Park"),
    "beaches": ("Relax at a nearby beach", "Beachfront"),
    "nightlife": ("Experience the local nightlife district", "Nightlife District"),
    "museums": ("Visit a well-known local museum", "City Museum"),
    "architecture": ("Admire notable local architecture", "Landmark Building"),
    "family activities": ("Enjoy a family-friendly attraction", "Family Attraction"),
    "religious sites": ("Visit a significant religious site", "Temple / Place of Worship"),
}
_DEFAULT_ACTIVITY = ("General sightseeing around the city center", "City Center")


def _pick_activity(interests: List[str], index: int):
    keys = [i.lower() for i in interests] or ["history"]
    key = keys[index % len(keys)]
    return _INTEREST_ACTIVITY_TEMPLATES.get(key, _DEFAULT_ACTIVITY)


def _style_activity_count(travel_style: str) -> int:
    """How 'packed' each day should feel - used only to flavor cost estimates."""
    return {"Relaxed": 2, "Balanced": 3, "Packed": 4}.get(travel_style, 3)


def _fallback_generate(inputs: Dict) -> Dict:
    """
    Deterministic, template-based itinerary builder used when no Gemini API
    key/package is available. Produces a complete, well-formed itinerary
    object so the rest of the app (display, PDF, calendar, chat) works
    identically regardless of whether AI or the fallback produced the plan.
    """
    destination = inputs.get("destination") or "your destination"
    duration = max(1, int(inputs.get("duration_days") or 1))
    interests = inputs.get("interests") or ["History", "Food"]
    travel_style = inputs.get("travel_style") or "Balanced"
    budget = _safe_num(inputs.get("budget"))
    transportation_pref = inputs.get("transportation") or "Taxi"
    food_pref = inputs.get("food_preferences") or "Any"

    base_activity_cost = 300 if _style_activity_count(travel_style) <= 2 else 500

    days = []
    for d in range(1, duration + 1):
        morning_name, morning_loc = _pick_activity(interests, d * 3)
        afternoon_name, afternoon_loc = _pick_activity(interests, d * 3 + 1)
        evening_name, evening_loc = _pick_activity(interests, d * 3 + 2)

        morning = {"activity": morning_name, "location": morning_loc, "duration": "~2 hours (estimate)", "cost": base_activity_cost}
        afternoon = {"activity": afternoon_name, "location": afternoon_loc, "duration": "~2.5 hours (estimate)", "cost": base_activity_cost + 100}
        evening = {"activity": evening_name, "location": evening_loc, "duration": "~1.5 hours (estimate)", "cost": base_activity_cost - 50}

        food = {
            "breakfast": f"Breakfast at a local café near your accommodation ({food_pref} options, estimate)",
            "lunch": f"Lunch at a well-reviewed local restaurant near {afternoon_loc} (estimate)",
            "dinner": f"Dinner featuring regional specialties near {evening_loc} (estimate)",
        }
        transportation = {
            "recommended": transportation_pref,
            "travel_time": "~20-30 minutes between stops (estimate)",
            "cost": 250,
        }
        logistics = ["Hotel", morning_loc, afternoon_loc, evening_loc, "Hotel"]
        daily_cost = morning["cost"] + afternoon["cost"] + evening["cost"] + transportation["cost"] + 600  # + food estimate

        days.append(
            {
                "day_number": d,
                "morning": morning,
                "afternoon": afternoon,
                "evening": evening,
                "food": food,
                "transportation": transportation,
                "logistics": logistics,
                "daily_estimated_cost": daily_cost,
            }
        )

    itinerary = {
        "trip_summary": {
            "destination": destination,
            "starting_location": inputs.get("starting_location") or "Not specified",
            "duration_days": duration,
            "travel_dates": inputs.get("travel_dates") or "Not specified",
            "travelers": inputs.get("travelers") or 1,
            "budget": budget,
            "travel_style": travel_style,
            "interests": interests,
            "food_preferences": food_pref,
            "transportation": transportation_pref,
        },
        "days": days,
        "budget_summary": {},
        "travel_tips": [
            f"This is an offline demo itinerary for {destination} - connect a Gemini API key for a fully AI-personalized plan.",
            "All costs and durations shown are rough estimates only - verify current prices, hours, and availability locally.",
            "Carry a mix of cash and cards, as acceptance varies by vendor.",
            "Keep a digital and physical copy of key documents while traveling.",
        ],
    }
    itinerary["budget_summary"] = _recalculate_budget_summary(itinerary)
    return itinerary


# ---------------------------------------------------------------------------
# Offline fallback: chat-based modification (simple rule-based edits)
# ---------------------------------------------------------------------------
def _fallback_modify(current_itinerary: Dict, user_message: str) -> Dict:
    """
    A small set of rule-based edits covering the example requests from the
    spec, used when no AI is available. Always preserves the rest of the
    itinerary untouched.
    """
    itinerary = json.loads(json.dumps(current_itinerary))  # deep copy
    msg = user_message.lower()
    reply = "I've updated the itinerary based on your request (offline demo mode - connect a Gemini API key for smarter edits)."

    days = itinerary.get("days", [])

    def day_by_number(n):
        for day in days:
            if day.get("day_number") == n:
                return day
        return None

    day_match = re.search(r"day\s*(\d+)", msg)
    target_day = day_by_number(int(day_match.group(1))) if day_match else None

    if "less packed" in msg or "relax" in msg or "fewer activities" in msg:
        target = target_day or (days[0] if days else None)
        if target:
            target["evening"] = {"activity": "Free time / leisurely stroll", "location": "Near hotel", "duration": "Flexible (estimate)", "cost": 0}
            target["daily_estimated_cost"] = max(0, _safe_num(target.get("daily_estimated_cost")) - 300)
            reply = f"I lightened Day {target['day_number']} by replacing the evening activity with free time."

    elif "more food" in msg or "food spot" in msg or "more restaurants" in msg:
        target = target_day or (days[0] if days else None)
        if target:
            target["food"]["snack"] = "Added: a popular local street-food stop (estimate)"
            reply = "I added an extra local food recommendation to the day's plan."

    elif "cheaper" in msg or "reduce the budget" in msg or "lower the cost" in msg or "budget" in msg:
        for day in days:
            for slot in ("morning", "afternoon", "evening"):
                day[slot]["cost"] = round(_safe_num(day[slot].get("cost")) * 0.7, 2)
            day["transportation"]["cost"] = round(_safe_num(day["transportation"].get("cost")) * 0.8, 2)
            day["daily_estimated_cost"] = round(_safe_num(day.get("daily_estimated_cost")) * 0.75, 2)
        reply = "I swapped in lower-cost alternatives across the itinerary to reduce the overall budget."

    elif "more sightseeing" in msg:
        target = target_day or (days[0] if days else None)
        if target:
            target["afternoon"] = {"activity": "Additional sightseeing stop", "location": "Nearby landmark", "duration": "~1.5 hours (estimate)", "cost": 200}
            reply = f"I added an extra sightseeing stop to Day {target['day_number']}."

    elif "museum" in msg and ("replace" in msg or "outdoor" in msg):
        target = target_day or (days[0] if days else None)
        if target:
            for slot in ("morning", "afternoon", "evening"):
                if "museum" in target[slot].get("activity", "").lower():
                    target[slot] = {"activity": "Outdoor activity (e.g. park walk or garden visit)", "location": "Local Park", "duration": "~1.5 hours (estimate)", "cost": 100}
            reply = "I replaced the museum visit with an outdoor activity."

    elif "beach" in msg:
        target = target_day or (days[0] if days else None)
        if target:
            target["afternoon"] = {"activity": "Relax at a nearby beach", "location": "Beachfront", "duration": "~2 hours (estimate)", "cost": 150}
            reply = f"I added a beach activity to Day {target['day_number']}."

    else:
        reply = (
            "I noted your request, but the offline demo mode only understands a few common phrases "
            "(e.g. 'less packed', 'more food', 'cheaper', 'more sightseeing', 'replace museum', 'add a beach activity'). "
            "Connect a Gemini API key for fully flexible AI edits."
        )

    itinerary["budget_summary"] = _recalculate_budget_summary(itinerary)
    return {"updated_itinerary": itinerary, "assistant_reply": reply}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_itinerary(inputs: Dict, api_key: Optional[str] = None) -> Dict:
    """
    Generate a brand-new itinerary from the trip-planning form inputs.
    Falls back to the offline template generator on any failure.
    """
    resolved_key = resolve_api_key(api_key)

    if not resolved_key:
        return _fallback_generate(inputs)

    try:
        from google import genai

        client = genai.Client(api_key=resolved_key)
        prompt = _build_generation_prompt(inputs)
        response = client.models.generate_content(model=DEFAULT_MODEL, contents=prompt)
        parsed = _extract_json(response.text)

        if not _validate_itinerary(parsed):
            raise ValueError("Gemini response was missing required itinerary fields.")

        # Always recompute the budget summary so it's numerically consistent,
        # even if the model's own arithmetic was slightly off.
        parsed["budget_summary"] = _recalculate_budget_summary(parsed)
        return parsed

    except Exception:
        return _fallback_generate(inputs)


def modify_itinerary(current_itinerary: Dict, user_message: str, api_key: Optional[str] = None) -> Dict:
    """
    Apply a natural-language edit request to an existing itinerary.

    Returns:
        {"updated_itinerary": {...}, "assistant_reply": "..."}
    """
    resolved_key = resolve_api_key(api_key)

    if not resolved_key:
        return _fallback_modify(current_itinerary, user_message)

    try:
        from google import genai

        client = genai.Client(api_key=resolved_key)
        prompt = _build_modification_prompt(current_itinerary, user_message)
        response = client.models.generate_content(model=DEFAULT_MODEL, contents=prompt)
        parsed = _extract_json(response.text)

        if (
            not isinstance(parsed, dict)
            or "updated_itinerary" not in parsed
            or not _validate_itinerary(parsed["updated_itinerary"])
            or "assistant_reply" not in parsed
        ):
            raise ValueError("Gemini response was missing required fields.")

        parsed["updated_itinerary"]["budget_summary"] = _recalculate_budget_summary(parsed["updated_itinerary"])
        return parsed

    except Exception:
        return _fallback_modify(current_itinerary, user_message)
