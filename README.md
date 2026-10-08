# ✈️ Generative AI Travel Itinerary Planner

A Streamlit web app that turns a destination, budget, trip duration, and a
few preferences into a detailed, day-by-day travel itinerary — complete with
activities, food recommendations, transportation logistics, and a budget
breakdown. Refine the plan through a natural-language chat interface, then
export it as a PDF or a calendar (`.ics`) file.

## Project Overview

You fill in a short trip-planning form (destination, dates, budget,
travelers, interests, travel style, food and transport preferences). The
app uses the Google Gemini API to generate a structured itinerary — morning,
afternoon, and evening activities each day, food recommendations, transport
logistics, and an estimated budget breakdown. You can then chat with the AI
to tweak the plan ("Make day 2 less packed", "Add a beach activity on day
3", "Reduce the budget") without losing the rest of your itinerary, and
finally export the result as a shareable PDF or import it into your
calendar app.

## Features

- **Trip planning form** — destination, starting location, travel dates,
  duration, budget, number of travelers, interests, travel style, food
  preference, accommodation preference, and transportation preference.
- **Popular destination quick-pick** — optional dropdown (backed by
  `data/sample_destinations.csv`) to prefill the destination field.
- **AI itinerary generation** — day-by-day plan with morning/afternoon/
  evening activities, food recommendations, transportation logistics, and a
  suggested visiting order to avoid backtracking.
- **Interest-based personalization** — activities are prioritized to match
  your selected interests (Food, History, Culture, Adventure, Beaches, etc.).
- **Budget management** — a full cost breakdown (accommodation, food,
  transportation, activities, shopping, miscellaneous) with a clear warning
  if the estimated cost exceeds your budget.
- **AI chat refinement** — a chat box below the itinerary lets you modify it
  with plain-English requests; the rest of the plan is preserved unless your
  request requires a change.
- **Session state management** — your itinerary, inputs, and chat history
  persist across interactions within the same session.
- **PDF export** — a professional, shareable PDF built with ReportLab.
- **Calendar export** — a standard `.ics` file with one event per activity,
  importable into Google Calendar, Outlook, Apple Calendar, etc.
- **Offline fallback mode** — no Gemini API key? The app still generates a
  complete demo itinerary and supports a handful of common chat edits, so
  you can try the whole workflow immediately.
- **Friendly error handling** — invalid dates, negative budgets, empty
  destinations, API errors, and export failures all show clear messages
  instead of crashing the app.

## Technology Stack

- **Python 3.9+**
- **Streamlit** — web interface and session state
- **Pandas** — CSV handling (sample destinations data)
- **Google Gemini API** (`google-genai` SDK) — itinerary generation & chat-based edits
- **python-dotenv** — environment variable management
- **ReportLab** — PDF generation
- **Python `datetime`** — date/time scheduling logic
- **Custom `.ics` builder** — calendar export (no extra dependency required)

## Folder Structure

```
generative-ai-travel-itinerary-planner/
│
├── app.py                   # Streamlit UI and session state
├── itinerary_generator.py   # Gemini API integration + generation/modification + offline fallback
├── pdf_export.py            # PDF generation using ReportLab
├── calendar_export.py       # .ics calendar file generation
├── requirements.txt         # Python dependencies
├── .env.example             # Template for environment variables
├── README.md                # This file
│
├── data/
│   └── sample_destinations.csv   # Popular destinations used for quick-pick suggestions
│
└── output/
    └── .gitkeep                   # Keeps the (empty) output folder in git
```

## Installation

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate it

**Windows (PowerShell / Command Prompt):**
```powershell
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## API Key Setup

You have two options:

1. **`.env` file (recommended for local development):**
   - Copy `.env.example` to `.env`.
   - Fill in your key:
     ```
     GOOGLE_API_KEY=your_gemini_api_key
     ```
   - (Optional) set `GEMINI_MODEL` to use a different Gemini model — defaults
     to `gemini-2.5-flash`.

2. **Enter it in the app:**
   - Paste your key into the "Gemini API Key" field in the sidebar (masked,
     never written to disk or hard-coded into the source).

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/).

If no key is available from either source, the app automatically switches
to an **offline demo generator** so the full workflow (itinerary, chat edits,
PDF, calendar) can still be tested without internet access or a key.

## Running the Application

```bash
streamlit run app.py
```

Streamlit will print a local URL (usually `http://localhost:8501`) — open it
in your browser.

## Example Trip

```
Destination:        Hyderabad, India
Starting Location:  Mumbai, India
Duration:           4 days
Budget:             25,000
Travelers:          2
Interests:          Historical places, Food, Shopping, Photography, Culture
Travel Style:       Balanced
Food Preference:    Any
Transportation:     Taxi
```

After clicking **🪄 Generate My Itinerary**, you'll see a day-by-day plan
(Day 1, Day 2, ...) with morning/afternoon/evening activities, food
recommendations, transportation, a route summary, and a daily estimated
cost — followed by a full budget summary and travel tips.

Then try chatting below the itinerary:

```
You:  Make day 2 less packed.
AI:   I lightened Day 2 by replacing the evening activity with free time.

You:  Add more food spots.
AI:   I added an extra local food recommendation to the day's plan.

You:  Reduce the budget to 20,000.
AI:   I swapped in lower-cost alternatives across the itinerary to reduce the overall budget.
```

## Data Format (`data/sample_destinations.csv`)

Used only to power the optional "Popular destination" dropdown in the
sidebar — it is not required for the app to function.

```csv
destination,country,famous_for,suggested_duration_days,typical_daily_budget_inr
Hyderabad,India,"Historical places, Food, Pearls",4,6000
Goa,India,"Beaches, Nightlife, Seafood",4,7000
```

Feel free to add your own rows — the dropdown updates automatically.

## PDF Export

Click **📄 Download PDF** after generating or refining an itinerary. The PDF
includes the trip summary, full day-by-day plan, budget summary (with a
warning if you're over budget), and travel tips. Filenames follow the
pattern `travel_itinerary_<destination>.pdf` (e.g.
`travel_itinerary_hyderabad_india.pdf`).

## Calendar Export

Click **📅 Export Calendar** to download an `.ics` file with one event per
activity (morning, afternoon, evening) for every day of the trip, using your
selected start date. Import it into Google Calendar, Outlook, or Apple
Calendar. Since the AI only estimates activity durations (not exact clock
times), each event uses a fixed default start time per time-of-day slot
(Morning 9:00 AM, Afternoon 1:30 PM, Evening 6:00 PM) with a duration parsed
from the activity's estimate where possible.

## Chat Refinement

The chat box below the itinerary lets you request changes in plain English.
With a Gemini API key configured, the AI can handle open-ended requests and
will only change what you asked for, recalculating costs and the budget
summary as needed. Without a key, a small set of rule-based edits handles
the most common requests from the examples above (less packed, more food,
cheaper, more sightseeing, replace museum, add a beach activity).

## Troubleshooting

| Issue | Likely Cause / Fix |
|---|---|
| "Please enter a destination" | The destination field was left empty. |
| Itinerary looks generic / template-like | No Gemini API key was found — the app is using the offline demo generator. Add a key in `.env` or the sidebar. |
| Gemini errors or unexpected itinerary shape | The app automatically falls back to the offline generator so it never crashes — check your API key and quota if this happens often. |
| "Couldn't generate the PDF" | Usually caused by unusual characters in generated text; try regenerating the itinerary and exporting again. |
| "Couldn't generate the calendar file" | Make sure the itinerary has at least one day with activities; try regenerating first. |
| Chat doesn't seem to understand my request (offline mode) | The offline fallback only recognizes a handful of common phrases. Connect a Gemini API key for fully flexible edits. |
| `ModuleNotFoundError` on startup | Re-run `pip install -r requirements.txt` inside your activated virtual environment. |

## Important Notes

All costs, opening hours, availability, and travel times shown in this app
are **estimates only**, generated by an AI model or a simple offline
template. They are **not** verified against live, current sources. Always
confirm prices, hours, and availability directly with the destination /
venue before you travel.

┌───────────────────────┐
                     │   User Trip Inputs    │
                     │ (Budget, Dates, etc.) │
                     └───────────┬──────────Here is an alternative, streamlined version of your README file designed to be punchy and developer-focused, followed by the logical expressions and an architectural flow diagram of your application.

### Alternative README Content

# 🗺️ AI Travel Itinerary Planner & Assistant

An intelligent, Streamlit-based web application that transforms basic travel parameters into comprehensive, day-by-day itineraries. Powered by the Google Gemini API, this tool generates personalized schedules, manages budgets, and allows users to refine their plans via a natural-language chat interface before exporting them to PDF or a Calendar app.

## 🚀 Key Highlights
* **Dynamic Generation:** Creates detailed morning, afternoon, and evening schedules with food and transport recommendations.
* **Conversational Refinement:** Chat directly with the AI to tweak specific days or activities without regenerating the entire trip.
* **Smart Budgeting:** Automatically calculates estimated costs and flags if the itinerary exceeds the user's budget.
* **Export Ready:** Generate professional PDFs (via ReportLab) or `.ics` calendar files seamlessly.
* **Resilient Architecture:** Built-in offline fallback mode ensures the app functions perfectly for demos even without a Gemini API key.

## 🛠️ Quick Start

**1. Clone & Environment Setup**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
