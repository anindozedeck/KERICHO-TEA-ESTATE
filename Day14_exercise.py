import argparse
import json
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import os

import anthropic
from dotenv import load_dotenv


load_dotenv()

MODEL = "claude-haiku-4-5"
KERICHO_LATITUDE = -0.3676
KERICHO_LONGITUDE = 35.2831
NAIROBI_TIMEZONE = ZoneInfo("Africa/Nairobi")

SYSTEM_PROMPT = """You are a practical field assistant for a tea estate in Kericho, Kenya.
For any question involving weather, environmental conditions, or harvesting, call
get_kericho_weather before answering. Do not call the weather tool for unrelated
questions. Use the returned weather data to give a concise, practical recommendation
in plain language; do not invent weather observations.

Tea harvesting guidance:
- Good conditions require no rain forecast in the next 6 hours, a temperature
  from 15C through 25C inclusive, and low relative humidity (below 70%).
- Active rain is a bad condition.
- Temperatures above 28C are a bad condition.
- If conditions are mixed or between the stated temperature ranges, explain the
  concern and give a cautious, practical recommendation rather than claiming the
  conditions are ideal.
"""

WEATHER_TOOL = {
    "name": "get_kericho_weather",
    "description": (
        "Get current conditions and the next six hours of weather for the tea "
        "estate in Kericho, Kenya. Call this for weather, condition, or harvesting questions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

WEATHER_QUESTION_PATTERN = re.compile(
    r"\b(?:weather|condition\w*|harvest\w*|rain\w*|temperature\w*|"
    r"humid\w*|forecast\w*|wind\w*|sunny|cloudy|drying)\b",
    re.IGNORECASE,
)


def question_needs_weather(question):
    """Return whether a question is about weather conditions or harvesting."""
    return bool(WEATHER_QUESTION_PATTERN.search(question))


def get_kericho_weather():
    """Fetch current weather and hourly forecast data for Kericho."""
    params = urlencode(
        {
            "latitude": KERICHO_LATITUDE,
            "longitude": KERICHO_LONGITUDE,
            "current": (
                "temperature_2m,relative_humidity_2m,precipitation,rain,showers"
            ),
            "hourly": (
                "temperature_2m,relative_humidity_2m,"
                "precipitation_probability,precipitation"
            ),
            "forecast_days": 2,
            "timezone": "Africa/Nairobi",
        }
    )
    request = Request(
        f"https://api.open-meteo.com/v1/forecast?{params}",
        headers={"User-Agent": "KerichoTeaHarvestAssistant/1.0"},
    )
    with urlopen(request, timeout=15) as response:
        weather = json.load(response)

    current = weather["current"]
    hourly = weather["hourly"]
    now = datetime.now(NAIROBI_TIMEZONE)
    forecast_end = now + timedelta(hours=6)
    next_hours = []

    for index, forecast_time in enumerate(hourly["time"]):
        forecast_at = datetime.fromisoformat(forecast_time).replace(
            tzinfo=NAIROBI_TIMEZONE
        )
        if now < forecast_at <= forecast_end:
            next_hours.append(
                {
                    "time": forecast_at.strftime("%H:%M"),
                    "temperature_c": hourly["temperature_2m"][index],
                    "relative_humidity_percent": hourly[
                        "relative_humidity_2m"
                    ][index],
                    "precipitation_probability_percent": hourly[
                        "precipitation_probability"
                    ][index],
                    "precipitation_mm": hourly["precipitation"][index],
                }
            )

    return json.dumps(
        {
            "location": "Kericho, Kenya",
            "observed_at": current["time"],
            "current": {
                "temperature_c": current["temperature_2m"],
                "relative_humidity_percent": current["relative_humidity_2m"],
                "precipitation_mm": current["precipitation"],
                "rain_mm": current["rain"],
                "showers_mm": current["showers"],
            },
            "next_six_hours": next_hours,
        }
    )


def ask_agent(client, question):
    """Ask the model a question and execute its weather tool call when needed."""
    weather_needed = question_needs_weather(question)
    available_tools = [WEATHER_TOOL] if weather_needed else []
    request_options = {
        "model": MODEL,
        "max_tokens": 512,
        "system": SYSTEM_PROMPT,
        "tools": available_tools,
        "messages": [{"role": "user", "content": question}],
    }

    if weather_needed:
        request_options["tool_choice"] = {
            "type": "tool",
            "name": "get_kericho_weather",
        }

    response = client.messages.create(**request_options)
    messages = request_options["messages"]

    while response.stop_reason == "tool_use":
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for tool_use in response.content:
            if tool_use.type != "tool_use":
                continue
            if tool_use.name != "get_kericho_weather":
                raise ValueError(f"Unknown tool requested: {tool_use.name}")

            result = get_kericho_weather()
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                }
            )

        if not tool_results:
            raise RuntimeError("The model requested a tool but supplied no tool call.")

        messages.append({"role": "user", "content": tool_results})
        request_options.pop("tool_choice", None)
        response = client.messages.create(**request_options)

    return "\n".join(
        block.text for block in response.content if block.type == "text"
    )


def run_routing_tests():
    """Check that weather questions route to the tool and unrelated ones do not."""
    cases = (
        ("Is today good for harvesting?", True),
        ("What should I pack for lunch?", False),
        ("How should I sharpen pruning shears?", False),
    )

    for question, expected in cases:
        actual = question_needs_weather(question)
        if actual != expected:
            raise AssertionError(
                f"Routing failed for {question!r}: expected {expected}, got {actual}"
            )
        print(f"PASS: {question} -> {'weather tool' if actual else 'no weather tool'}")


def main():
    parser = argparse.ArgumentParser(
        description="Ask the Kericho tea estate field assistant."
    )
    parser.add_argument(
        "--test-routing",
        action="store_true",
        help="Run offline checks for one weather question and two unrelated questions.",
    )
    args = parser.parse_args()

    if args.test_routing:
        run_routing_tests()
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Set it in this terminal before running "
            "the assistant."
        )

    client = anthropic.Anthropic()
    question = input("Ask a question about the Kericho tea estate (or type 'quit'): ")
    if question.strip().lower() in {"quit", "exit"}:
        return
    if not question.strip():
        raise SystemExit("Please enter a question.")

    print(ask_agent(client, question))


if __name__ == "__main__":
    main()