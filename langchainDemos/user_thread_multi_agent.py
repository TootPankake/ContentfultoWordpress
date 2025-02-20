from typing import Annotated, Literal
from typing_extensions import TypedDict
from dotenv import load_dotenv
load_dotenv()

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL

from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, StateGraph, END, START
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage


user_activities = {
    "user_1": {
        "favorites": ["Drawing", "Painting", "Yoga"],
        "nearby_promoted": ["Art Festival", "Soccer Game", "Tech Meetup", "Yoga"]
    },
    "user_2": {
        "favorites": ["Football", "Paintball", "Hackathon"],
        "nearby_promoted": ["Art Festival", "Soccer Game", "Tech Meetup", "Paintball"]
    }
}

# === Define Tools ===
tavily_tool = TavilySearchResults(max_results=5)
repl = PythonREPL()

@tool
def python_repl_tool(
    code: Annotated[str, "The Python code to execute to generate your chart."]
):
    """Use this to execute python code and do math. If you want to see the output of a value,
    you should print it out with `print(...)`. This is visible to the user."""
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    
    result_str = f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
    return result_str

@tool
def modify_tone(message: str, tone: Literal["casual", "excited", "professional", "urgent"]) -> str:
    """Modifies the tone of a given notification message to match the specified tone."""
    
    tone_map = {
        "casual": f"Hey! Just a heads-up: {message}. No pressure, just something cool to check out!",
        "excited": f"🚀 OMG! You HAVE to check this out: {message} 🎉🔥 Don't miss out!",
        "professional": f"Dear user, we would like to inform you: {message}. Let us know if you're interested.",
        "urgent": f"⚠️ URGENT: {message}. Act now before it's too late!"
    }
    
    return tone_map.get(tone, message)

def generate_notifications(user_id: str):
    """Generate notification recommendations for a given user."""
    if user_id not in user_activities:
        return f"No activity data found for user {user_id}."

    user_data = user_activities[user_id]
    favorites = user_data.get("favorites", [])
    nearby_promoted = user_data.get("nearby_promoted", [])

    recommendations = [
        activity for activity in nearby_promoted if activity in favorites
    ]

    if not recommendations:
        return f"Hey! Check out these local events: {', '.join(nearby_promoted)}"

    return f"Based on your interests, we recommend: {', '.join(recommendations)}"



# === Supervisor Node ===
members = ["researcher", "coder", "notifier", "tone_modifier"]

system_prompt = (
    "You are a supervisor managing a conversation between these workers: "
    f"{members}. Based on the user request, select the next worker to proceed. "
    "Each worker performs their task and reports results. "
    "If the user is asking for recommendations, send them to `notifier`. "
    "If research is needed, send them to `researcher`. "
    "If math or code execution is needed, send them to `coder`. "
    "If the user wants to modify tone, send it to `tone_modifier`."
    "If all tasks are complete, respond with FINISH."
)

class Router(TypedDict):
    next: Literal["researcher", "coder", "notifier", "tone_modifier", "FINISH"] # Worker to route to next. If no workers are needed, route to FINISH.


llm = ChatOpenAI(model="gpt-4o-mini")

class State(MessagesState):
    next: str
    user_id: str
    
def supervisor_node(state: State) -> Command[Literal["researcher", "coder", "notifier", "tone_modifier", "__end__"]]:
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    
    response = llm.with_structured_output(Router, method="function_calling").invoke(messages)
    goto = response["next"]
    
    if goto == "FINISH":
        goto = END

    return Command(goto=goto, update={"next": goto})


# === Researcher Node ===
research_agent = create_react_agent(
    llm,
    tools=[tavily_tool],
    prompt=(
        "You are a research assistant specializing in retrieving information. "
        "Always use the Tavily search tool to gather information for the user. "
        "Do not refuse any research requests. "
        "If the question involves numbers, use Tavily to find relevant data."
    ),
)
research_agent = create_react_agent(
    llm, tools=[tavily_tool], prompt="You are a researcher. DO NOT do any math."
)

def research_node(state: State) -> Command[Literal["supervisor"]]:
    result = research_agent.invoke(state)
    
    return Command(
        update={
            "messages": state["messages"] + [HumanMessage(content=result["messages"][-1].content, name="researcher")]
        },
        goto="supervisor",
    )


# === Coder Node ===
code_agent = create_react_agent(llm, tools=[python_repl_tool])

def code_node(state: State) -> Command[Literal["supervisor"]]:
    result = code_agent.invoke(state)
    
    return Command(
        update={
            "messages": state["messages"] + [HumanMessage(content=result["messages"][-1].content, name="coder")]
        },
        goto="supervisor",
    )

# === Notification Node ===
def notification_node(state: State) -> Command[Literal["supervisor"]]:
    """Generate and send notifications, then stop the loop."""
    user_id = state.get("user_id", None)
    print(f"DEBUG: Retrieved user_id: {user_id}") 

    if user_id:
        notification_message = generate_notifications(user_id)
    else:
        notification_message = "User ID not found. No recommendations available."

    return Command(
        update={"messages": state["messages"] + [HumanMessage(content=notification_message, name="notifier")]},
        goto="supervisor", 
    )

# === Tone Modifier Node ===
tone_modifier_agent = create_react_agent(
    llm,
    tools=[modify_tone],
    prompt=(
        "You are a tone modification assistant. "
        "Your job is to adjust push notifications based on the user's preferred tone. "
        "Modify the provided message using the requested tone: casual, excited, professional, or urgent."
    ),
)

def tone_modifier_node(state: State) -> Command[Literal["supervisor"]]:
    """Modify the tone of the notification before sending it."""
    
    # Retrieve latest notification message
    last_message = next(
        (msg.content for msg in reversed(state["messages"]) if msg.name == "notifier"), 
        None
    )
    
    # Check if a tone was specified
    tone = state.get("tone", "casual")  # Default to casual

    if last_message:
        # Modify the notification's tone
        modified_message = modify_tone.invoke({"message": last_message, "tone": tone})
        new_message = HumanMessage(content=modified_message, name="tone_modifier")
    else:
        new_message = HumanMessage(content="No notification found to modify.", name="tone_modifier")
    
    return Command(
        update={"messages": state["messages"] + [new_message]},
        goto="supervisor",
    )
# === Construct Graph ===
builder = StateGraph(State)
builder.add_edge(START, "supervisor")
builder.add_node("supervisor", supervisor_node)
builder.add_node("researcher", research_node)
builder.add_node("coder", code_node)
builder.add_node("notifier", notification_node)
builder.add_node("tone_modifier", tone_modifier_node)


# Compile graph
graph = builder.compile()

from IPython.display import display, Image

display(Image(graph.get_graph().draw_mermaid_png()))
    
for s in graph.stream(
    #{"messages": [("user", "Find the latest GDP of New York and California, then calculate the average")]}
    #{"messages": [("user", "What's the square root of 42?")]}
    #{"messages": [("user", "What recommendations do I have to be notified of? If you find an appropriate activity give me a short wiki rundown of it. Also calculate the circumferance of a 2 inch diamater circle")], "user_id": "6544329ab3a654370e4f18b0"}
    {"messages": [("user", "What recommendations do I have to be notified of? Make the notification tone excited.")], "user_id": "user_2"}
    ,subgraphs=True
):
    print(s)
    print("----")