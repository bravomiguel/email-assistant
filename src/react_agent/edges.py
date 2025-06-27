from langchain_core.messages import AIMessage
from typing import Literal

from react_agent.state import State


# routing after model call
def route_model_output(state: State):
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # if there is no tool call, check if we need to generate a title
    if not last_message.tool_calls:
        # Only route to generate_thread_title if we don't have a title yet
        if not state.thread_title:
            return "generate_thread_title"
        # Otherwise, go directly to end
        return "__end__"

    # Check if the tool call is UPDATE_MEMORY
    tool_name = last_message.tool_calls[0].get("name", "")
    if tool_name == "UPDATE_MEMORY":
        # Get the memory_type argument
        memory_type = last_message.tool_calls[0].get("args", {}).get("memory_type", None)
        # Route to the appropriate node based on memory_type
        if memory_type == "user_profile":
            return "user_profile"
        elif memory_type == "writing_style":
            return "writing_style"

    # if tool call is GMAIL_REPLY_TO_THREAD, route to human review node
    if last_message.tool_calls[-1].get("name", "") in [
        "GMAIL_REPLY_TO_THREAD",
        "GMAIL_SEND_EMAIL",
    ]:
        return "human_review"

    # otherwise, route to tools node and execute relevant action
    return "tools"
