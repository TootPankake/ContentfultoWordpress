from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
load_dotenv()

model = init_chat_model("gpt-4o-mini", model_provider="openai")
response = model.invoke(
    [
        HumanMessage(content="Hi! I'm Emre"),                         # These two messages
        AIMessage(content="Hello Emre! How can I assist you today?"), # are the chat history
        HumanMessage(content="What's my name?"),
    ]
)
print(response.content)
