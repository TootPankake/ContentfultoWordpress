from langchain.chat_models import init_chat_model
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
import sys
from dotenv import load_dotenv
load_dotenv()

memory = MemorySaver()

search = TavilySearchResults(max_results=2)
search_results = search.invoke("what is the weather in SD")
tools = [search]


model = init_chat_model("gpt-4", model_provider="openai")
model_with_tools = model.bind_tools(tools)
agent_executor = create_react_agent(model, tools, checkpointer=memory)


config = {"configurable": {"thread_id": "abc123"}} # different conversation threads


for chunk in agent_executor.stream(
    {"messages": [HumanMessage(content="whats the weather in San Diego?")]}, config
):
    print(chunk)
    print("----")

config = {"configurable": {"thread_id": "123abc"}} # different conversation threads

for chunk in agent_executor.stream(
    {"messages": [HumanMessage(content="what city did I just ask about?")]}, config
):
    print(chunk)
    print("----")
sys.exit()