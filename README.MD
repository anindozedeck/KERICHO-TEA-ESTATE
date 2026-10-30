# Kericho Tea Estate Field Assistant

A command-line assistant for practical questions about a tea estate in Kericho,
Kenya. It uses Anthropic's Claude Haiku model for responses and fetches live
conditions and a six-hour forecast from Open-Meteo for weather and harvesting
questions.

## Requirements

- Python 3.9 or later
- An Anthropic API key
- Internet access when asking the assistant a question

The weather service is Open-Meteo's forecast API and does not require an API
key. The Python dependencies are `anthropic` and `python-dotenv`.

## Setup

From this directory, install the dependencies:

```powershell
python -m pip install anthropic python-dotenv
```

Set your Anthropic API key in the terminal before starting the assistant:

```powershell
$env:ANTHROPIC_API_KEY = "your-api-key"
```

Alternatively, create a `.env` file in this directory and add:

```dotenv
ANTHROPIC_API_KEY=your-api-key
```

The application loads values from `.env` at startup. Do not commit API keys or
other secrets.

## Run

Start the assistant:

```powershell
python Day14_exercise.py
```

Enter a question when prompted. Type `quit` or `exit` to leave without sending
a question. The program handles one question each time it is run.

Weather, environmental-condition, and harvesting questions are routed to the
weather tool. It retrieves current conditions and forecast data for the next
six hours, then uses that information to formulate a practical answer. Other
questions are sent to the model without a weather lookup.

## Check question routing

Run the built-in offline checks without an API key or network access:

```powershell
python Day14_exercise.py --test-routing
```

The checks cover a harvesting question and two unrelated questions, and print
`PASS` for each successful routing check.

## Harvesting guidance

The assistant's instructions define good harvesting conditions as:

- No rain forecast in the next six hours
- Temperature from 15°C through 25°C, inclusive
- Relative humidity below 70%

Active rain and temperatures above 28°C are considered bad conditions. Mixed
conditions or temperatures between the stated ranges should receive a cautious
recommendation rather than a claim that conditions are ideal.
