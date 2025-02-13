from langchain.chat_models import init_chat_model
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
load_dotenv()

search = TavilySearchResults(max_results=2)
tool_output = search.invoke("what is the weather in San Diego")
wiki_api_wrapper = WikipediaAPIWrapper()  # Initialize the Wikipedia API
wiki = WikipediaQueryRun(api_wrapper=wiki_api_wrapper)  # Pass API wrapper

tools = [search, wiki]


model = init_chat_model("gpt-4", model_provider="openai")
model_with_tools = model.bind_tools(tools)

    
response = model_with_tools.invoke([HumanMessage(content="what is the weather in San Diego")])
print(f"ContentString: {response.content}")
print(f"ToolCalls: {response.tool_calls}")
print(f"\nSearch Results: {tool_output[1]['content']}")

response = model_with_tools.invoke([HumanMessage(content="hi")])
print(f"\n\nContentString: {response.content}")
print(f"ToolCalls: {response.tool_calls}")

response = model_with_tools.invoke([HumanMessage(content="Tell me about the history of usb ports.")])
print(f"\n\nContentString: {response.content}")
print(f"ToolCalls: {response.tool_calls}")

# Execute Wikipedia tool call
for tool_call in response.tool_calls:
    tool_name = tool_call["name"]
    tool_input = tool_call["args"]["query"]

    if tool_name == "wikipedia":
        tool_output = wiki.invoke(tool_input)
        print(f"\n📖 Wikipedia Search Results: {tool_output[:500]}...")