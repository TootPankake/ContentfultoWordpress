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
from wordpress_operations import (fetch_all_pages_posts, fetch_metadata_id ,fetch_all_tags_categories,
                                  create_parent_page, create_tag, create_child_page_concurrently)

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
refreshArticles = input("\nDo you need to refresh EVERY article or just the ones updated since last access? (y/n): ").strip().upper()
gptSweep = input("Do you need to reupdate ChatGPT article links? This takes a while. (y/n): ").strip().upper()

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
existing_posts = []
activity_slugs = []
locked_titles = []
activity_data, article_data = [], []
existing_metadata, existing_post_metadata, existing_tag_metadata, existing_category_metadata = [], [], [], []
all_categories, all_activities, all_articles = [], [], []
skip1 = skip2 = 0
skip3 = 0

print("\nFetching metadata entry ID's")
fetch_all_pages_posts(existing_pages, existing_posts)
fetch_metadata_id(existing_pages, existing_posts, existing_metadata, existing_post_metadata)
fetch_all_tags_categories(existing_tag_metadata, existing_category_metadata)

print(len(existing_post_metadata))
print(len(existing_metadata))
print(len(existing_posts))
barrier_tag = create_tag("Barrier Article", "barrier-articles", "0451", existing_tag_metadata)
print("Fetching contentful data")
all_categories, all_activities, all_articles = fetch_contentful_data(limit, skip1, skip2, skip3, date_threshold, date_threshold_articles, date_threshold_categories, client)
print(len(all_articles))
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
    futures = {executor.submit(process_article, entry, gptSweep, json_slug_data, existing_post_metadata): entry for entry in all_articles}

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

print("\nCategories: ")
render_categories(all_categories, all_category_ids, existing_category_metadata)

activity_types = {item['activity'] for item in processed_articles}    
parent_pages = {}
parent_page_ids = {}
tag_ids = {}
body = ""

def create_parent_page_and_tag(activity, content, activity_slug, image_url, activity_id, category_list, existing_metadata, existing_tag_metadata):
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_parent_page = executor.submit(
            create_parent_page, activity, content, activity_slug, image_url, activity_id, category_list, existing_metadata
        )
        future_tag = executor.submit(
            create_tag, activity, activity_slug, activity_id, existing_tag_metadata
        )
        # Wait for both tasks to complete
        parent_page_id = future_parent_page.result()
        tag_id = future_tag.result()
    return parent_page_id, tag_id

print("\nActivities: ")
for activity in sorted(activity_types):
    for entry in all_activities:
        title = entry.fields().get('title')
        content = entry.fields().get('description_full', [])
        categories = entry.fields().get('categories', [])
        activity_slug = entry.fields().get('slug', [])
        activity_id = entry.sys.get('id')
        hero_image = entry.fields().get('hero_image')
        hero_image_url = None

        if hero_image: # Check if hero_image is a valid Asset object
            image_url = f"https:{hero_image.fields().get('file').get('url')}"

        if title == activity:
            articles = entry.fields().get('articles', [])
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

            # Call the parallelized function
            parent_page_id, tag_id = create_parent_page_and_tag(
                activity, content, activity_slug, image_url, activity_id, category_list, existing_metadata, existing_tag_metadata
            )
            
            parent_page_ids[activity] = parent_page_id
            tag_ids[activity] = tag_id

print(len(processed_articles))
print("\nArticles: ")
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(create_child_page_concurrently, article, existing_post_metadata, barrier_tag, tag_ids, gptSweep): article for article in processed_articles}
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

