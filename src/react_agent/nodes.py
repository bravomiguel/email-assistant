import asyncio
from typing import Dict, List, cast
from datetime import datetime
import uuid
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
from langgraph.types import Command, interrupt
from langgraph.store.base import BaseStore
from langchain_openai import ChatOpenAI
from react_agent.schemas import Profile
from trustcall import create_extractor

from react_agent.prompts import (
    CREATE_EMAIL_PRIORITIZATION_INSTRUCTIONS,
    CREATE_WRITING_STYLE_INSTRUCTIONS,
    TRUSTCALL_INSTRUCTION,
)
from react_agent.utils import load_chat_model
from react_agent.state import State
from react_agent.configuration import Configuration
from react_agent.tools import TOOLS, gmail_reply_to_thread

gpt_4o_mini = ChatOpenAI(model="gpt-4o-mini")

tools = ToolNode(TOOLS)

gmail_reply_node = ToolNode(gmail_reply_to_thread)


async def call_model(
    state: State, config: RunnableConfig, store: BaseStore
) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.
        store (BaseStore): The store to use for memories.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)

    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(configuration.model).bind_tools(TOOLS)

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = configuration.system_prompt.format(
        system_time=datetime.now().isoformat()
    )

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}


async def human_review(state: State) -> Command:
    """Handle human review of the email reply."""
    last_message = state.messages[-1]

    if not last_message.tool_calls:
        raise ValueError("No tool calls found")

    tool_call = last_message.tool_calls[-1]

    if tool_call.get("name", "") != "GMAIL_REPLY_TO_THREAD":
        return Command(goto="tools")

    review = interrupt(
        {
            "question": "Ready to send?",
            "recipient_email": tool_call.get("args", {}).get("recipient_email", ""),
            "message_body": tool_call.get("args", {}).get("message_body", ""),
        }
    )

    action = review.get("action")
    edits = review.get("edits")
    feedback = review.get("feedback")

    if action == "send":
        return Command(goto="tools")

    if action == "edit_send":
        updated_tool_call = {
            "role": "ai",
            "content": last_message.content,
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "name": tool_call["name"],
                    "args": {**tool_call.get("args", {}), **edits},
                }
            ],
            "id": last_message.id,
        }

        return Command(goto="tools", update={"messages": [updated_tool_call]})

    if action == "reject":
        tool_message = {
            "role": "tool",
            "content": f"Reply rejected by the user. User feedback: {feedback}",
            "name": tool_call["name"],
            "tool_call_id": tool_call["id"],
        }

        return Command(goto="call_model", update={"messages": [tool_message]})


async def user_profile(state: State, config: RunnableConfig, store: BaseStore):
    """Reflect on the chat history and update user profile."""

    # get user id
    user_id = Configuration.from_runnable_config(config).user_id

    # get user profile from store and format for trustcall
    profile_store = await store.asearch(("user_profile", user_id))
    profile = (
        [(item.key, "Profile", item.value) for item in profile_store]
        if profile_store
        else None
    )

    # run trustcall on messages and profile (prep system prompt)
    profile_extractor = create_extractor(
        gpt_4o_mini, tools=[Profile], tool_choice="Profile"
    )
    system_prompt = TRUSTCALL_INSTRUCTION.format(time=datetime.now().isoformat())
    messages = list(
        merge_message_runs(
            messages=[SystemMessage(content=system_prompt)] + state["messages"][:-1]
        )
    )

    result = profile_extractor.invoke({"messages": messages, "existing": profile})

    # update profile in store with trustcall response
    for response, response_metadata in zip(
        result["responses"], result["response_metadata"]
    ):
        store.put(
            ("user_profile", user_id),
            response_metadata.get("json_doc_id", str(uuid.uuid4())),
            response.model_dump(mode="json"),
        )

    # return tool message confirming profile updated successfully
    return {
        "messages": [
            {
                "role": "tool",
                "content": "User profile updated",
                "tool_call_id": state["messages"][-1].tool_calls[0]["id"],
            }
        ]
    }


async def writing_style(state: State, config: RunnableConfig, store: BaseStore):
    """Reflect on the chat history and update writing style instructions."""

    # get user id
    user_id = Configuration.from_runnable_config(config).user_id

    # get existing instructions from store
    existing_instructions = await store.asearch(
        ("instructions", user_id), "writing_style_instructions"
    )

    # prep system prompt
    system_prompt = CREATE_WRITING_STYLE_INSTRUCTIONS.format(
        existing_instructions=(
            existing_instructions.value if existing_instructions else ""
        )
    )

    # invoke model to generate writing style instructions, based on chat history
    response = gpt_4o_mini.ainvoke(
        [{"role": "system", "content": system_prompt}, *state.messages]
    )

    # update writing style instructions in store
    await store.aput(
        ("instructions", user_id),
        "writing_style_instructions",
        {"instructions": response.content},
    )

    # return tool message confirming instructions updated
    return {
        "messages": [
            {
                "role": "tool",
                "content": "Writing style instructions updated",
                "tool_call_id": state["messages"][-1].tool_calls[0]["id"],
            }
        ]
    }


async def email_priorities(state: State, config: RunnableConfig, store: BaseStore):
    """Reflect on the chat history and update email prioritization instructions."""

    # get user id
    user_id = Configuration.from_runnable_config(config).user_id

    # get existing instructions from store
    existing_instructions = await store.asearch(
        ("instructions", user_id), "email_prioritization_instructions"
    )

    # prep system prompt
    system_prompt = CREATE_EMAIL_PRIORITIZATION_INSTRUCTIONS.format(
        existing_instructions=(
            existing_instructions.value if existing_instructions else ""
        )
    )

    # invoke model to generate email prioritization instructions, based on chat history
    response = gpt_4o_mini.ainvoke(
        [{"role": "system", "content": system_prompt}, *state.messages]
    )

    # update email prioritization instructions in store
    await store.aput(
        ("instructions", user_id),
        "email_prioritization_instructions",
        {"instructions": response.content},
    )

    # return tool message confirming instructions updated
    return {
        "messages": [
            {
                "role": "tool",
                "content": "Email prioritization instructions updated",
                "tool_call_id": state["messages"][-1].tool_calls[0]["id"],
            }
        ]
    }
