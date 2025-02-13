from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage, trim_messages, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph, add_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing_extensions import Annotated, TypedDict
from typing import Sequence
from dotenv import load_dotenv
load_dotenv()

model = init_chat_model("gpt-4o-mini", model_provider="openai")

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    language: str
    
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You talk like royalty. Answer all questions to the best of your ability in {language}.",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

trimmer = trim_messages(
    max_tokens=int(input("Max tokens for history of conversation, try values like 60 or 120: ")),
    strategy="last",
    token_counter=model,
    include_system=True,
    allow_partial=False,
    start_on="human",
)

messages = [
    SystemMessage(content="you're a good assistant"),
    HumanMessage(content="hi! I'm bob"),
    AIMessage(content="hi!"),
    HumanMessage(content="I like vanilla ice cream"),
    AIMessage(content="nice"),
    HumanMessage(content="whats 2 + 2"),
    AIMessage(content="4"),
    HumanMessage(content="thanks"),
    AIMessage(content="no problem!"),
    HumanMessage(content="having fun?"),
    AIMessage(content="yes!"),
]

trimmer.invoke(messages)

workflow = StateGraph(state_schema=State)
def call_model(state: State):
    trimmed_messages = trimmer.invoke(state["messages"])
    prompt = prompt_template.invoke(
        {"messages": trimmed_messages, "language": state["language"]}
    )
    response = model.invoke(prompt)
    return {"messages": response}

workflow.add_edge(START, "model")
workflow.add_node("model", call_model)
memory = MemorySaver()
application = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "0451"}}
alternate_config = {"configurable": {"thread_id": "0452"}}

language = "English"
query = "What's my name?"
input_messages = messages + [HumanMessage(query)]
for chunk, metadata in application.stream(
    {"messages": input_messages, "language": language},
    config,
    stream_mode="messages",
):
    if isinstance(chunk, AIMessage):  
        print(chunk.content, end="", flush = True)

print()
query = "What math problem did I ask?"
input_messages = messages + [HumanMessage(query)] 
for chunk, metadata in application.stream(
    {"messages": input_messages, "language": language},
    config,
    stream_mode="messages",
):
    if isinstance(chunk, AIMessage):  
        print(chunk.content, end="", flush = True)



