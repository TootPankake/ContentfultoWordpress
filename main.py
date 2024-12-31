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
from contentful_data import fetch_contentful_data, render_activities, render_categories
from wordpress_operations import (fetch_all_pages_and_posts, fetch_page_and_post_metadata_id, fetch_all_tags_and_categories,
                                  create_page_and_tag, create_tag, create_child_page_concurrently)

# MongoDB initialization for accessing date storage
clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
database = clientDB['brimming-test']
time_collection = database['contentfulAccessDates']
date_threshold_activities = datetime(2024, 1, 1).isoformat()
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
refresh_all_articles = input("\nDo you need to refresh EVERY article or just the ones updated since last access? (y/n): ").strip().upper()
ai_links_sweep = input("Do you need to reupdate ChatGPT article links? This takes a while. (y/n): ").strip().upper()

# date_threshold_articles is either hardset or fetched from MongoDB collection
if refresh_all_articles == 'Y':
    date_threshold_articles = datetime(2023, 1, 1).isoformat()
else: 
    recent_posts = time_collection.find().sort('timestamp', -1).limit(1)
    for post in recent_posts:
        formattedTime = post['created_at']
        adjusted_time = formattedTime
        formatted_date = adjusted_time.strftime("%Y-%m-%d %H:%M:%S.%f")
    date_threshold_articles = formatted_date
    
existing_wordpress_pages = []
existing_wordpress_posts = []
existing_page_metadata, existing_post_metadata, existing_tag_metadata, existing_category_metadata = [], [], [], []
print("\nFetching metadata entry ID's from WordPress")
fetch_all_tags_and_categories(existing_tag_metadata, existing_category_metadata) 
fetch_all_pages_and_posts(existing_wordpress_pages, existing_wordpress_posts) 
fetch_page_and_post_metadata_id(existing_wordpress_pages, existing_wordpress_posts, existing_page_metadata, existing_post_metadata)

print("Total posts with metadata: ", len(existing_post_metadata))
print("Total pages with metadata: ", len(existing_page_metadata))
barrier_article_tag_id = create_tag("Barrier Article", "barrier-articles", "0451", existing_tag_metadata)

all_categories, all_activities, all_articles = [], [], []
contentful_fetching_limit = 25
skip_categories = skip_activities = 0
skip_articles = 0 # might want to change this for testing
print("\nFetching contentful data")
all_categories, all_activities, all_articles = fetch_contentful_data(contentful_fetching_limit, skip_categories, skip_activities, skip_articles, 
                                                                     client, date_threshold_activities, date_threshold_articles, date_threshold_categories)

activity_slugs = []
print("Rendering contentful data")
render_activities(all_activities, activity_slugs)

print("Collected all contentful data")
json_slug_data = json.dumps(activity_slugs)

print(f"Compiling {MODEL} prompts\n")
processed_articles = []
with ThreadPoolExecutor(max_workers=10) as executor: # parallelization of prompt execution
    futures = {executor.submit(process_article, entry, ai_links_sweep, json_slug_data, existing_post_metadata): entry for entry in all_articles}
    for future in as_completed(futures):
        article = futures[future]
        try:
            data = future.result()
            processed_articles.append(data)

        except Exception as exc:
            print(f"Exception occurred while processing article: {exc}")

# double check articles for left over prompt structure guides to delete
if ai_links_sweep == 'Y':
    for article in processed_articles:
        article['content'] = article['content'].replace("[ARTICLE END]", "")    
        
all_category_ids = []
print("\nCategories: ")
render_categories(all_categories, all_category_ids, existing_category_metadata)

# activities derived from their links to list of articles
activity_types = {item['activity'] for item in processed_articles}    
page_ids = {}
tag_ids = {}

print("\nActivities: ")
for activity in sorted(activity_types):
    for entry in all_activities:
        title = entry.fields().get('title')
        description_full = entry.fields().get('description_full', [])
        linked_categories = entry.fields().get('categories', [])
        activity_slug = entry.fields().get('slug', [])
        activity_contentful_entry_id = entry.sys.get('id')
        hero_image = entry.fields().get('hero_image')
        hero_image_url = None

        if hero_image: # check if hero_image is a valid Asset object
            image_url = f"https:{hero_image.fields().get('file').get('url')}"

        if title == activity:
            articles = entry.fields().get('articles', [])
            categories_title_list = [category.fields().get('title') for category in linked_categories]
            categories_slug_list = [category.fields().get('slug') for category in linked_categories]
            categories_id_list = [category.sys.get('id') for category in linked_categories]
        
            category_title = categories_title_list[0] if categories_title_list else ''
            category_slug = categories_slug_list[0] if categories_slug_list else ''
            category_id =  categories_id_list[0] if categories_id_list else ''
            category_list = []
                        
            category_id_dict = {item['contentful_entry_id']: item['id_number'] for item in all_category_ids} # dictionary to look through category id list
            category_list = [category_id_dict[j] for j in categories_id_list if j in category_id_dict]

            if description_full:
                description_full = RENDERER.render(description_full)

            # call the parallelized function
            parent_page_id, tag_id = create_page_and_tag(
                activity, description_full, activity_slug, image_url, activity_contentful_entry_id, category_list, existing_page_metadata, existing_tag_metadata
            )
            
            page_ids[activity] = parent_page_id
            tag_ids[activity] = tag_id

print(len(processed_articles))
print("\nArticles: ")
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(create_child_page_concurrently, article, existing_post_metadata, barrier_article_tag_id, tag_ids, ai_links_sweep): article for article in processed_articles}
    for future in as_completed(futures):
        article = futures[future]
        try:
            future.result()  # retrieve the result to trigger any exceptions
        except Exception as exc:
            article_title = article.get('title', 'Unknown Title')
            print(f"Exception occurred while processing article '{article['title']}': {exc}")

print("\nAll articles have been processed successfully.")

# insert new most recent access date once program is successfully compiled
today = {'name': datetime.now(), 'created_at': datetime.now()}
time_collection.insert_one(today)
dates = list(time_collection.find().sort('created_at', -1))
dates_to_delete = dates[1:] # deletes all dates but the last one
ids_to_delete = [doc['_id'] for doc in dates_to_delete] # extract the _ids of documents to delete
time_collection.delete_many({'_id': {'$in': ids_to_delete}}) # delete the identified documents
clientDB.close() 

