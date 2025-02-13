from langchain.chat_models import init_chat_model
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
import asyncio
from dotenv import load_dotenv
load_dotenv()

wiki_api_wrapper = WikipediaAPIWrapper()  # Initialize the Wikipedia API
wiki = WikipediaQueryRun(api_wrapper=wiki_api_wrapper)  # Pass API wrapper
search = TavilySearchResults(max_results=2)
tools = [search, wiki]


model = init_chat_model("gpt-4o-mini", model_provider="openai")
model_with_tools = model.bind_tools(tools)
agent_executor = create_react_agent(model, tools)

# response = agent_executor.invoke(
#     {"messages": [HumanMessage(content="whats the weather in SD?")]}
# )

# for chunk in agent_executor.stream(
#     {"messages": [HumanMessage(content="whats the weather in SD?")]}
# ):
#     print(chunk)
#     print("----")
    
async def stream_events(query):
    async for event in agent_executor.astream_events(
        {"messages": [HumanMessage(content=query)]}, version="v1"
    ):
        kind = event["event"]
        if kind == "on_chain_start":
            if (
                event["name"] == "Agent"
            ):  
                print(
                    f"Starting agent: {event['name']} with input: {event['data'].get('input')}"
                )
        elif kind == "on_chain_end":
            if (
                event["name"] == "Agent"
            ): 
                print()
                print("--")
                print(
                    f"Done agent: {event['name']} with output: {event['data'].get('output')['output']}"
                )
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                # Empty content in the context of OpenAI means
                # that the model is asking for a tool to be invoked.
                # So we only print non-empty content
                print(content, end="")
        elif kind == "on_tool_start":
            print("--")
            print(
                f"Starting tool: {event['name']} with inputs: {event['data'].get('input')}"
            )
        elif kind == "on_tool_end":
            print(f"Done tool: {event['name']}")
            print(f"Tool output was: {event['data'].get('output')}")
            print("--")

# law of gravity is found on wikipeda, latest research found with tavily
query = "Who formulated the law of universal gravitation, and what are the latest research findings on gravity?"
asyncio.run(stream_events(query))