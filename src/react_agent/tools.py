"""This module provides example tools for web scraping and search functionality.

It includes a basic Tavily search function (as an example)

These tools are intended as free examples to get started. For production use,
consider implementing more robust and specialized tools tailored to your needs.
"""

from datetime import datetime
from typing import Annotated, Any, Callable, List, Optional, cast
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langgraph.store.base import BaseStore
from langchain_tavily import TavilySearch  # type: ignore[import-not-found]
from composio_langgraph import Action, ComposioToolSet

from react_agent.configuration import Configuration


async def search(query: str) -> Optional[dict[str, Any]]:
    """Search for general web results.

    This function performs a search using the Tavily search engine, which is designed
    to provide comprehensive, accurate, and trusted results. It's particularly useful
    for answering questions about current events.
    """
    configuration = Configuration.from_runnable_config()
    wrapped = TavilySearch(max_results=configuration.max_search_results)
    return cast(dict[str, Any], await wrapped.ainvoke({"query": query}))


# Initialize ToolSet (assuming API key is in env)
toolset = ComposioToolSet()


def filter_email_fetch_inputs(inputs: dict) -> dict:
    """filter out any inputs set to None"""
    # filtered_inputs = {key: value for key, value in inputs.items() if value is not None}
    # return filtered_inputs
    inputs["query"] = inputs.get("query", "")
    inputs["label_ids"] = inputs.get("label_ids", [])
    inputs["page_token"] = inputs.get("page_token", "")
    return inputs


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


# Fetch only the tool for fetching emails
gmail_fetch_emails = toolset.get_tools(
    actions=[Action.GMAIL_FETCH_EMAILS],
    processors={
        "pre": {Action.GMAIL_FETCH_EMAILS: filter_email_fetch_inputs},
        "post": {Action.GMAIL_FETCH_EMAILS: filter_email_results},
    },
    entity_id="miguel-bravo",
)

gmail_reply_to_thread = toolset.get_tools(
    actions=[Action.GMAIL_REPLY_TO_THREAD],
    entity_id="miguel-bravo",
)


async def upsert_memory(
    content: str,
    context: str,
    *,
    memory_id: Optional[uuid.UUID] = None,
    # Hide these arguments from the model.
    config: Annotated[RunnableConfig, InjectedToolArg],
    store: Annotated[BaseStore, InjectedToolArg],
):
    """Upsert a memory in the database with what happened in your last interaction with the user.

    If a memory conflicts with an existing one, then just UPDATE the
    existing one by passing in memory_id - don't create two memories
    that are the same. If the user corrects a memory, UPDATE it.

    Args:
        content: The main content of the memory. For example:
            "User expressed interest in learning about French."
        context: Additional context for the memory. For example:
            "This was mentioned while discussing career options in Europe."
        memory_id: ONLY PROVIDE IF UPDATING AN EXISTING MEMORY.
    """
    mem_id = memory_id or uuid.uuid4()
    user_id = Configuration.from_runnable_config(config).user_id

    await store.aput(
        ("memories", user_id),
        key=str(mem_id),
        value={"content": content, "context": context, "created_at": datetime.now().isoformat()},
    )

    return f"Stored memory {mem_id}"

TOOLS: List[Callable[..., Any]] = [search, *gmail_fetch_emails, *gmail_reply_to_thread]