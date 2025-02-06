from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient
from config import URI, OPENAI_API_TOKEN
import certifi
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import os


clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
database = clientDB['brimming-test']
recommendations = database['recommendedbrims']

os.environ["OPENAI_API_KEY"] = OPENAI_API_TOKEN
chat_model = ChatOpenAI(temperature=0)

#LangChain prompt
prompt_template = PromptTemplate(
    input_variables=["prompt_data", "activities"],
    template="""
    Based on the following user data:
    - Prompt: {prompt_data}
    - Activities: {activities}
    
    Provide additional recommendations or insights for the user.
    """
)

recent_posts = recommendations.find().sort('timestamp', -1).limit(2)
for post in recent_posts:
    prompt_data = post['prompt']
    activities = post['responses'].get('activities', "No activities available")
    user = post['user']
    
    # Format the prompt and generate response
    formatted_prompt = prompt_template.format(prompt_data=prompt_data, activities=activities)
    langchain_response = chat_model.invoke(formatted_prompt)
    
    # Print the results
    print("MONGODB RECOMMEND BRIMS FOR USER: ", user)
    print(prompt_data)
    print("Recommended Activites: ", activities)
    print("\nLANGCHAIN RESPONSE")
    print(langchain_response.content)


clientDB.close()