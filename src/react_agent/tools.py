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
composio_toolset = ComposioToolSet()

# Fetch only the tool for starring a GitHub repo
gmail_fetch_emails = composio_toolset.get_tools(
    actions=[Action.GMAIL_FETCH_EMAILS]
)

TOOLS: List[Callable[..., Any]] = [search, *gmail_fetch_emails]
