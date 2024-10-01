import sys
import json
import certifi
import contentful
from datetime import datetime
from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import SPACE_ID, ACCESS_TOKEN, URL, URI, RENDERER, MODEL, ENVIRONMENT, AUTH
from article_processing import process_article
from contentful_data import fetch_contentful_data, render_articles, render_activities, render_categories
from wordpress_operations import (fetch_all_pages, fetch_page_metadata_id, fetch_category_metadata_id,
                                  create_parent_page, create_child_page_concurrently)

#def lambda_handler(event,context):
# MongoDB initialization for access date storage
clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
db = clientDB['brimming-test']
collection = db['contentfulAccessDates']
date_threshold = datetime(2024, 1, 1).isoformat()
date_threshold_categories = datetime(2023, 1, 1).isoformat()

# Initialize Contentful API Client
try:
    client = contentful.Client(SPACE_ID, ACCESS_TOKEN,  
                            environment=ENVIRONMENT,
                            max_include_resolution_depth=1)
    print("Successfully connected to Contentful client.")
except contentful.errors.NotFoundError as e:
    print(f"Error: {e}")

# Prompt user on execution parameters
refreshArticles = 'Y'#input("\nDo you need to refresh EVERY article or just the ones updated since last access? (y/n): ").strip().upper()
gptSweep = 'N'#input("Do you need to reupdate ChatGPT article links? This takes a while. (y/n): ").strip().upper()
# Lambda Replacements
#refreshArticles = event.get('refreshArticles').strip().upper()
#gptSweep = event.get('gptSweep').strip().upper()

if refreshArticles == 'Y':
    date_threshold_articles = datetime(2023, 1, 1).isoformat()
else: 
    recent_posts = collection.find().sort('timestamp', -1).limit(1) # Fetch the most recent posts (assuming you have a 'timestamp' field)
    for post in recent_posts:
        formattedTime = post['created_at']
        adjusted_time = formattedTime #- timedelta(minutes=1) gives some leeway on last db date request
        formatted_date = adjusted_time.strftime("%Y-%m-%d %H:%M:%S.%f")
    date_threshold_articles = formatted_date
    
limit = 25
all_category_ids = []
existing_pages = []
activity_slugs = []
activity_data, article_data = [], []
existing_metadata, existing_category_metadata = [], []
all_categories, all_activities, all_articles = [], [], []
skip1 = skip2 = skip3 = 0

print("\nFetching metadata ID's")
fetch_all_pages(existing_pages)
fetch_page_metadata_id(existing_pages, existing_metadata)
fetch_category_metadata_id(existing_category_metadata)

print("Fetching contentful data")
all_categories, all_activities, all_articles = fetch_contentful_data(limit, skip1, skip2, skip3, date_threshold, date_threshold_articles, date_threshold_categories, client)

print("Rendering contentful data")
render_articles(all_articles, RENDERER, article_data)
render_activities(all_activities, RENDERER, activity_data, activity_slugs)

print("Collected all contentful data")
json_slug_data = json.dumps(activity_slugs)
json_article_data = json.dumps(article_data, indent=4)
json_activity_data = json.dumps(activity_data, indent=4)

print(f"Compiling {MODEL} prompts\n")
processed_articles = []
with ThreadPoolExecutor(max_workers=10) as executor: # parallelization of prompt execution
    futures = {executor.submit(process_article, entry, gptSweep, json_slug_data): entry for entry in all_articles}

    for future in as_completed(futures):
        article = futures[future]
        try:
            data = future.result()
            processed_articles.append(data)

        except Exception as exc:
            print(f"Exception occurred while processing article: {exc}")

# Double check articles for left over prompt structure guides to delete
if gptSweep == 'Y':
    for article in processed_articles:
        article['content'] = article['content'].replace("[ARTICLE END]", "")    

print("Categories: ")
render_categories(all_categories, all_category_ids, existing_category_metadata)

activity_types = {item['activity'] for item in processed_articles}    
parent_pages = {}
parent_page_ids = {}
body = ""

print("\nActivities: ")
for activity in sorted(activity_types):
    for entry in all_activities:
        title = entry.fields().get('title')
        content = entry.fields().get('description_full', [])
        categories = entry.fields().get('categories', [])
        activity_slug = entry.fields().get('slug', [])
        activity_id = entry.sys.get('id')

        if title == activity:
            articles = entry.fields().get('articles', [])
            articles_list = [article.fields().get('slug') for article in articles]
            categories_title_list = [category.fields().get('title') for category in categories]
            categories_slug_list = [category.fields().get('slug') for category in categories]
            categories_id_list = [category.sys.get('id') for category in categories]
        
            category_title = categories_title_list[0] if categories_title_list else ''
            category_slug = categories_slug_list[0] if categories_slug_list else ''
            category_id =  categories_id_list[0] if categories_id_list else ''
            category_list = []
                        
            category_id_dict = {item['meta_data_id']: item['id'] for item in all_category_ids} # dictionary to look through category id list
            category_list = [category_id_dict[j] for j in categories_id_list if j in category_id_dict]

            
            if content:
                content = RENDERER.render(content)
                content += "\nArticles: \n"
                for i in articles_list:
                    content += f"{URL}{activity_slug}/{i}/\n"
                parent_page_id = create_parent_page(activity, content, activity_slug, activity_id, category_list, existing_metadata)
                parent_page_ids[activity] = parent_page_id
            if not content:
                content = "\nArticles: \n"
                for i in articles_list:
                    content += f"{URL}{activity_slug}/{i}/\n"
                parent_page_id = create_parent_page(activity, content, activity_slug, activity_id, category_list, existing_metadata)
                parent_page_ids[activity] = parent_page_id

print("\nArticles: ")
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(create_child_page_concurrently, article, existing_metadata, parent_page_ids, gptSweep): article for article in processed_articles}
    for future in as_completed(futures):
        article = futures[future]
        try:
            future.result()  # Retrieve the result to trigger any exceptions
        except Exception as exc:
            article_title = article.get('title', 'Unknown Title')
            #print(f"Exception occurred while processing article '{article['title']}': {exc}")

print("\nAll articles have been processed successfully.")

# Insert new most recent access date once program is successfully compiled
today = {'name': datetime.now(), 'created_at': datetime.now()}
collection.insert_one(today)
dates = list(collection.find().sort('created_at', -1))
dates_to_delete = dates[1:] # deletes all dates but the last one
ids_to_delete = [doc['_id'] for doc in dates_to_delete] # Extract the _ids of documents to delete
collection.delete_many({'_id': {'$in': ids_to_delete}}) # Delete the identified documents
clientDB.close() 

