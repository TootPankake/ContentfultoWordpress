from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
load_dotenv()

model = init_chat_model("gpt-4o-mini", model_provider="openai")

text_to_translate = input("Type what you want translated: ")
language = input("What language?: ")

system_template = "Translate the following from English into {language}"

prompt_template = ChatPromptTemplate.from_messages(
    [("system", system_template), ("user", "{text}")]
)
prompt = prompt_template.invoke({"language": language, "text": text_to_translate})


response = model.invoke(prompt)
print(response.content)

# See how tokens are split up
for token in model.stream(prompt):
    print(token.content, end="|")
