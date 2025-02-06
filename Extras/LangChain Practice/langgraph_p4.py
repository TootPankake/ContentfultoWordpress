from typing import Annotated, List, Dict, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from config import OPENAI_API_TOKEN
import os


os.environ["OPENAI_API_KEY"] = OPENAI_API_TOKEN # Set API key for OpenAI
memory = MemorySaver()

# Initialize OpenAI's chat model with GPT-4-turbo
llm = ChatOpenAI(model="gpt-4-turbo", temperature=0.7, streaming=True)

class State(TypedDict):
    messages: Annotated[List[Dict[str, str]], add_messages]
    memory: List[Dict[str, str]]  # Memory holds all previous messages
    preferences: Optional[Dict[str, str]]          # User preferences (e.g., tone, length)
    conversation_flags: Optional[Dict[str, bool]]  # Flags for controlling chatbot behavior
    
def chatbot(state: State):
    preferences = state.get("preferences", {})
    flags = state.get("conversation_flags", {})
    
    response_length = preferences.get("response_length", "normal")

    # Modify the system message based on preferences
    if response_length == "brief":
        state["messages"].insert(0, {"role": "system", "content": "Be concise and to the point."})
    elif response_length == "detailed":
        state["messages"].insert(0, {"role": "system", "content": "Provide detailed explanations."})

    # Combine memory and current messages
    conversation_history = state["memory"] + state["messages"]
    response = llm.invoke(conversation_history)
    state["memory"].append({"role": "assistant", "content": response.content})
    
    # Update the flag to indicate that the conversation is active
    if flags is not None:
        flags["is_active"] = True
        
    # Return updated messages and memory
    return {
        "messages": [response],
        "memory": state["memory"],
        "conversation_flags": flags

    }

# Add human-in-the-loop confirmation
def human_in_the_loop(response: str) -> str:
    print("\nAssistant's Response:", response)
    user_choice = input("Accept this response? (yes/no/edit): ").strip().lower()

    if user_choice == "yes":
        return response
    elif user_choice == "edit":
        return input("Enter your custom response: ").strip()
    else:
        print("Response rejected. Generating a new response...")
        return "Response rejected. Try asking again."
    
def memory_printing(state):
    output = chatbot(state)
    
    # Print the assistant's response
    print("\nAssistant:", output["messages"][0].content)

    # Display updated state details
    print("Updated Memory:", state["memory"])
    print("Conversation Flags:", state["conversation_flags"])
    
    state["memory"].append(state["messages"][0])  # Save user message to memory

# Define a test state with input messages
initial_state = {
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Can you summarize the book '1984'?"}
    ],
    "memory": [],
    "preferences": {
        "response_length": "brief"  # Other options: "detailed", "normal"
    },
    "conversation_flags": {
        "is_active": False
    }
}

# Simulate multiple turns in a conversation
state = initial_state

# First response
memory_printing(state)

# First turn
memory_printing(state)

# Second turn
state["messages"] = [{"role": "user", "content": "What is the capital of Germany?"}]
memory_printing(state)

# Third turn
state["messages"] = [{"role": "user", "content": "Give me more details about it."}]
state["preferences"]["response_length"] = "detailed"
memory_printing(state)

# Fourth turn - Ending the conversation
state["messages"] = [{"role": "user", "content": "Thank you, that's all for now."}]

# Set the flag to end the conversation
state["conversation_flags"]["end_conversation"] = True

# Modify the chatbot function to handle this flag
def chatbot_with_end_flag(state: State):
    # Check if the end_conversation flag is set
    if state["conversation_flags"].get("end_conversation"):
        print("\nAssistant: It was great talking to you! Have a nice day!")
        return {
            "messages": [{"role": "assistant", "content": "Conversation ended."}],
            "memory": state["memory"],
            "conversation_flags": state["conversation_flags"]
        }

    # Continue with normal processing if the flag is not set
    return chatbot(state)

# Call the updated chatbot function in the fourth turn
memory_printing(state)