
import os

import anthropic
from dotenv import load_dotenv


load_dotenv()

tools = [
    {
        "name": "get_stock_level",
        "description": "Get the current stock quantity for a product at Kamau Stores",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "The name of the product to check",
                }
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "get_price",
        "description": "Get the price per bag for a product at Kamau Stores",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {
                    "type": "string",
                    "description": "The name of the product to check",
                }
            },
            "required": ["product_name"],
        },
    }
]

# Simulate a database lookup (in a production system, this queries SQLite or an API)
inventory = {
    "maize flour": 120,
    "wheat flour": 85,
    "rice": 200,
    "sugar": 0,
    "cooking oil": 45
}


def get_stock_level(product_name):
    product = product_name.lower()
    if product in inventory:
        qty = inventory[product]
        if qty == 0:
            return f"{product_name} is currently out of stock."
        return f"{product_name}: {qty} bags in stock."
    return f"Product '{product_name}' not found in the system."


prices = {"maize flour": 2800, "wheat flour": 3200, "rice": 4500}


def get_price(product_name):
    p = product_name.lower()
    if p in prices:
        return f"{product_name}: KES {prices[p]:,} per bag"
    return f"Price not found for '{product_name}'"


client = anthropic.Anthropic()
messages = [
    {
        "role": "user",
        "content": "How much maize flour do we have, and what is its price?",
    }
]

response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=512,
    tools=tools,
    messages=messages,
)

while response.stop_reason == "tool_use":
    tool_results = []
    messages.append({"role": "assistant", "content": response.content})

    for tool_use in response.content:
        if tool_use.type != "tool_use":
            continue
        if tool_use.name == "get_stock_level":
            result = get_stock_level(tool_use.input["product_name"])
        elif tool_use.name == "get_price":
            result = get_price(tool_use.input["product_name"])
        else:
            raise ValueError(f"Unknown tool: {tool_use.name}")

        print(f"Function called: {tool_use.name}({tool_use.input})")
        print(f"Result: {result}")
        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            }
        )

    messages.append({"role": "user", "content": tool_results})
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        tools=tools,
        messages=messages,
    )

for block in response.content:
    if block.type == "text":
        print(block.text)