from datetime import datetime
import os
from typing import Annotated, Any, Callable, List, Literal, Optional, TypedDict, cast
import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from langgraph.store.base import BaseStore
from langchain_tavily import TavilySearch
from composio_langgraph import Action, ComposioToolSet
from react_agent.dynamic_composio_toolset import DynamicComposioToolSet

from react_agent.configuration import Configuration
from pydantic import BaseModel, Field


async def search_web(query: str) -> Optional[dict[str, Any]]:
    """Search for general web results.

    This function performs a search using the Tavily search engine, which is designed
    to provide comprehensive, accurate, and trusted results. It's particularly useful
    for answering questions about current events.
    """
    configuration = Configuration.from_runnable_config()
    wrapped = TavilySearch(max_results=configuration.max_search_results)
    return cast(dict[str, Any], await wrapped.ainvoke({"query": query}))


# Initialize ToolSet (assuming API key is in env)
# toolset = ComposioToolSet()
toolset = DynamicComposioToolSet()


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
)

gmail_send_email = toolset.get_tools(
    actions=[Action.GMAIL_SEND_EMAIL],
)

gmail_reply_to_thread = toolset.get_tools(
    actions=[Action.GMAIL_REPLY_TO_THREAD],
)

# class UpdateMemorySchema(BaseModel):
#     """Update memory input schema"""

#     memory_type: Literal["user_profile", "writing_style"] = Field(
#         description="The type of memory to update. Either 'user_profile' for user preferences/background or 'writing_style' for writing style information."
#     )


# Update memory tool (just control tool arg, output handled in node return logic)
@tool("UPDATE_MEMORY")
def update_memory(memory_type: Literal["user_profile", "writing_style"]) -> str:
    """Update a specific type of memory in the system.

    Args:
        memory_type: The type of memory to update. One of:
            - "user_profile": Information about the user's preferences, background, etc.
            - "writing_style": Information about the user's writing style.
    """
    # This function is a control tool that just passes the memory_type to be handled by the appropriate node
    # The actual memory update implementation is in the respective nodes
    return f"Updating memory type: {memory_type}"


TOOLS: List[Callable[..., Any]] = [
    search_web,
    *gmail_fetch_emails,
    *gmail_reply_to_thread,
    *gmail_send_email,
    update_memory,
]
