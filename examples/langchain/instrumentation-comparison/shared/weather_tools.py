"""
Shared weather tools for instrumentation comparison.
All three implementations use these same tools.
"""

from langchain_core.tools import tool


@tool
def get_current_weather(location: str) -> dict:
    """Get current weather conditions for a location.
    
    Args:
        location: City name or location
        
    Returns:
        Current weather data including temperature and conditions
    """
    # Simulated response - in production would call weather API
    return {
        "location": location,
        "temperature": "57°F",
        "condition": "partly cloudy",
        "humidity": "65%",
        "wind_speed": "10 mph"
    }


@tool
def get_forecast(location: str, days: int = 3) -> dict:
    """Get weather forecast for the next several days.
    
    Args:
        location: City name or location
        days: Number of days to forecast (1-7)
        
    Returns:
        Multi-day forecast data
    """
    forecasts = []
    conditions = ["sunny", "cloudy", "rainy", "partly cloudy"]
    for i in range(days):
        forecasts.append({
            "day": i + 1,
            "high": f"{65 + i * 3}°F",
            "low": f"{45 + i * 2}°F",
            "condition": conditions[i % len(conditions)]
        })
    return {"location": location, "forecast": forecasts}


@tool
def get_historical_weather(location: str, date: str) -> dict:
    """Get historical weather data for a past date.
    
    Args:
        location: City name or location
        date: Date in YYYY-MM-DD format
        
    Returns:
        Historical weather data for the specified date
    """
    return {
        "location": location,
        "date": date,
        "high": "62°F",
        "low": "48°F",
        "condition": "partly cloudy",
        "precipitation": "0.1 in"
    }


WEATHER_TOOLS = [get_current_weather, get_forecast, get_historical_weather]

SYSTEM_PROMPT = """You are a helpful weather assistant. You have access to three tools:
- get_current_weather: For current conditions
- get_forecast: For multi-day forecasts  
- get_historical_weather: For past weather data

Always use the appropriate tool based on what the user is asking about."""

TEST_QUERIES = [
    "What's the current weather in Seattle?",
    "What's the forecast for Tokyo for the next 3 days?",
    "What was the weather like in London yesterday?",
]
