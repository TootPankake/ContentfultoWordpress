from typing import Annotated, List, Dict
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

def chatbot(state: State):
    # Combine memory and current messages
    conversation_history = state["memory"] + state["messages"]
    response = llm.invoke(conversation_history)
    state["memory"].append({"role": "assistant", "content": response.content})
    
    # Return updated messages and memory
    return {
        "messages": [response],
        "memory": state["memory"]
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
    
    final_response = human_in_the_loop(output["messages"][0].content) # Get human confirmation or edit the response
    print("\nFinal Assistant Response:", final_response) # Print the final response after confirmation/edit

    state["memory"].append(state["messages"][0])  # Save user message to memory
    state["memory"].append({"role": "assistant", "content": final_response})

# Define a test state with input messages
initial_state = {
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! What's your name?"}
    ],
    "memory": []
}

# Simulate multiple turns in a conversation
state = initial_state

# First response
memory_printing(state)

# Second Response
state["messages"] = [{"role": "user", "content": "What is the capital of Germany?"}]
memory_printing(state)


# Third Response
state["messages"] = [{"role": "user", "content": "What country did you just talk about?"}]
memory_printing(state)

# Fourth Response
state["messages"] = [{"role": "user", "content": "What is the biggest river in the country you just mentioned?"}]
memory_printing(state)
