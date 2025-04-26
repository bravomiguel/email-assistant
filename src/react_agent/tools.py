"""This module provides example tools for web scraping and search functionality.

It includes a basic Tavily search function (as an example)

These tools are intended as free examples to get started. For production use,
consider implementing more robust and specialized tools tailored to your needs.
"""

import os
from typing import Any, Callable, List, Optional, cast

from langchain_tavily import TavilySearch  # type: ignore[import-not-found]

from composio_langgraph import Action, ComposioToolSet

from react_agent.configuration import Configuration


async def search(query: str) -> Optional[dict[str, Any]]:
    """Search for general web results.

    This function performs a search using the Tavily search engine, which is designed
    to provide comprehensive, accurate, and trusted results. It's particularly useful
    for answering questions about current events.
    """
    configuration = Configuration.from_context()
    wrapped = TavilySearch(max_results=configuration.max_search_results)
    return cast(dict[str, Any], await wrapped.ainvoke({"query": query}))


# Initialize ToolSet (assuming API key is in env)
toolset = ComposioToolSet(api_key=os.environ["COMPOSIO_API_KEY"])


# filter result returned by gmail fetch emails tool
def filter_email_results(result: dict) -> dict:
    """Filters email list to only include sender and subject."""
    # Pass through errors or unsuccessful executions unchanged
    if not result.get("successful") or "data" not in result:
        return result

    original_messages = result["data"].get("messages", [])
    if not isinstance(original_messages, list):
        return result  # Return if data format is unexpected

    # keys to keep
    keys_to_keep = [
        "threadId",
        "messageId",
        "messageTimestamp",
        "labelIds",
        "subject",
        "sender",
        "to",
        "preview",
        "messageText",
    ]

    filtered_messages = [
        {key: email.get(key) for key in keys_to_keep} for email in original_messages
    ]

    # trim text of long messages
    trimmed_messages = [
        {
            key: "TOO LONG" if key == "messageText" and len(val) > 1000 else val
            for key, val in email.items()
        }
        for email in filtered_messages
    ]

    # Construct the new result dictionary
    processed_result = {
        "successful": True,
        # Use a clear key for the filtered data
        "data": {"messages": trimmed_messages},
        "error": None,
    }
    return processed_result


# Fetch only the tool for starring a GitHub repo
gmail_fetch_emails = toolset.get_tools(
    actions=[Action.GMAIL_FETCH_EMAILS],
    processors={
        "post": {Action.GMAIL_FETCH_EMAILS: filter_email_results},
    },
    entity_id="miguel-bravo",
)

TOOLS: List[Callable[..., Any]] = [search, *gmail_fetch_emails]
