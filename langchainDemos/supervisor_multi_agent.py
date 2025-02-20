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


# === Supervisor Node ===
members = ["researcher", "coder"]

system_prompt = (
    "You are a supervisor managing a conversation between these workers: "
    f"{members}. Based on the user request, select the next worker to proceed. "
    "Each worker performs their task and reports results. When finished, respond with FINISH."
)

class Router(TypedDict):
    next: Literal["researcher", "coder", "FINISH"] # Worker to route to next. If no workers are needed, route to FINISH.


llm = ChatOpenAI(model="gpt-4o-mini")

class State(MessagesState):
    next: str

def supervisor_node(state: State) -> Command[Literal["researcher", "coder", "__end__"]]:
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    
    response = llm.with_structured_output(Router, method="function_calling").invoke(messages)
    goto = response["next"]
    
    if goto == "FINISH":
        goto = END

    return Command(goto=goto, update={"next": goto})


# === Researcher Node ===
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


# === Construct Graph ===
builder = StateGraph(State)

# Define workflow edges
builder.add_edge(START, "supervisor")
builder.add_node("supervisor", supervisor_node)
builder.add_node("researcher", research_node)
builder.add_node("coder", code_node)

# Compile graph
graph = builder.compile()

for s in graph.stream(
    #{"messages": [("user", "What's the square root of 42?")]}
    {"messages": [("user", "Find the latest GDP of New York and California, then calculate the average")]}
    , subgraphs=True,
):
    print(s)
    print("----")