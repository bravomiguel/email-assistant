from typing import Dict, List, cast
from datetime import datetime
import uuid
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    merge_message_runs,
)
from langgraph.types import Command, interrupt
from langgraph.store.base import BaseStore
from langchain_openai import ChatOpenAI
from react_agent.schemas import Profile
from trustcall import create_extractor

from react_agent.prompts import (
    WRITING_STYLE_INSTRUCTIONS,
    TRUSTCALL_INSTRUCTION,
)
from react_agent.utils import load_chat_model
from react_agent.state import State
from react_agent.configuration import Configuration
from react_agent.tools import TOOLS

gpt_4o_mini = ChatOpenAI(model="gpt-4o-mini")

tools = ToolNode(TOOLS)


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

    # Get the user ID from the config
    user_id = configuration.user_id

    # Retrieve profile memory from the store
    memories = await store.asearch(("user_profile", user_id))
    if memories:
        user_profile = memories[0].value
    else:
        user_profile = None

    # Retrieve custom instructions
    memories = await store.asearch(("instructions", user_id))
    if memories:
        instructions = memories[0].value
    else:
        instructions = ""

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = configuration.system_prompt.format(
        system_time=datetime.now().isoformat(),
        user_profile=user_profile,
        writing_style=instructions,
    )

    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(configuration.model).bind_tools(TOOLS)

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

    if tool_call.get("name", "") not in ["GMAIL_REPLY_TO_THREAD", "GMAIL_SEND_EMAIL"]:
        return Command(goto="tools")

    review = interrupt(
        {
            "question": "Ready to send?",
            "recipient_email": tool_call.get("args", {}).get("recipient_email", ""),
            "message_body": tool_call.get("args", {}).get("message_body", ""),
            "body": tool_call.get("args", {}).get("body", ""),
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


def user_profile(state: State, config: RunnableConfig, store: BaseStore):
    """Reflect on the chat history and update user profile."""

    # get user id
    user_id = Configuration.from_runnable_config(config).user_id

    # get user profile from store and format for trustcall
    profile_store = store.search(("user_profile", user_id))
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
            messages=[SystemMessage(content=system_prompt)] + state.messages[:-1]
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
                "tool_call_id": state.messages[-1].tool_calls[0]["id"],
            }
        ]
    }


def writing_style(state: State, config: RunnableConfig, store: BaseStore):
    """Reflect on the chat history and update writing style instructions."""

    # get user id
    user_id = Configuration.from_runnable_config(config).user_id

    # get existing instructions from store
    existing_instructions = store.get(
        ("instructions", user_id), "writing_style_instructions"
    )

    # Format the memory in the system prompt
    system_msg = WRITING_STYLE_INSTRUCTIONS.format(
        existing_instructions=(
            existing_instructions.value if existing_instructions else None
        )
    )
    new_memory = gpt_4o_mini.invoke(
        [SystemMessage(content=system_msg)]
        + state.messages[:-1]
        + [
            HumanMessage(
                content="Please update the instructions based on the conversation"
            )
        ]
    )

    # Overwrite the existing memory in the store
    store.put(
        ("instructions", user_id),
        "writing_style_instructions",
        new_memory.content,
    )
    tool_calls = state.messages[-1].tool_calls
    # Return tool message with update verification
    return {
        "messages": [
            {
                "role": "tool",
                "content": "updated writing style instructions",
                "tool_call_id": tool_calls[0]["id"],
            }
        ]
    }


async def generate_thread_title(state: State, config: RunnableConfig, store: BaseStore):
    """Generate a 4-word summary title for the conversation thread.

    This function is called when the AI responds to a human without tool calls.
    It analyzes the conversation history and creates a concise title that will
    be displayed in the frontend UI.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.
        store (BaseStore): The store to use for memories.

    Returns:
        dict: Updated state with the thread_title field set.
    """
    # Prepare system prompt for title generation
    system_prompt = "Generate a concise 4-word title that summarizes the conversation thread. The title should capture the main topic or purpose of the conversation."

    # Get the conversation history
    messages = state.messages

    # Invoke model to generate the title
    response = await gpt_4o_mini.ainvoke(
        [{"role": "system", "content": system_prompt}, *messages]
    )

    # Extract the title (trim to ensure it's exactly 4 words)
    title = " ".join(response.content.strip().split()[:4])

    # Return the state with the thread_title field updated
    return {"thread_title": title}
