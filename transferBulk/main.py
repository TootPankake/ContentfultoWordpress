import sys
import json
import certifi
from datetime import datetime
from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import URI, RENDERER, MODEL
from article_processing import generate_article_links
from contentful_data import fetch_contentful_data, render_activities, render_articles, render_categories
from wordpress_operations import (fetch_all_pages_concurrently, fetch_all_posts_concurrently, 
                                  fetch_all_tags, fetch_all_categories, 
                                  create_tag, create_category, create_post, create_page)

# Prompt user on execution parameters
refresh_all_articles = input("Do you need to refresh EVERY article or just the ones updated since last access? (y/n): ").strip().upper()
ai_links_sweep = input("Do you need to reupdate ChatGPT article links? This takes a while. (y/n): ").strip().upper()

# date_threshold_articles is either hardset or fetched from MongoDB collection
if refresh_all_articles == 'Y':
    date_threshold_articles = datetime(2023, 1, 1).isoformat()
else: 
    clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
    database = clientDB['brimming-test']
    time_collection = database['contentfulAccessDates']
    recent_posts = time_collection.find().sort('timestamp', -1).limit(1)
    for post in recent_posts:
        formattedTime = post['created_at']
        adjusted_time = formattedTime
        formatted_date = adjusted_time.strftime("%Y-%m-%d %H:%M:%S.%f")
    date_threshold_articles = formatted_date
    
all_categories, all_activities, all_articles = [], [], []
contentful_fetching_limit = 25
skip_categories = skip_activities = 0
skip_articles = 0 # might want to change this for testing
all_categories, all_activities, all_articles = fetch_contentful_data(contentful_fetching_limit, skip_categories, skip_activities, skip_articles, date_threshold_articles)


processed_activities, activity_slugs = render_activities(all_activities)
processed_articles = render_articles(all_articles)
json_slug_data = json.dumps(activity_slugs)

existing_wordpress_pages, existing_wordpress_posts = [], []
all_pages = fetch_all_pages_concurrently()
all_posts = fetch_all_posts_concurrently() 

print("Fetching wordpress pages")
for item in all_pages:
    if '_metadata_id' in item['meta']:
        title = item['title']['rendered']
        slug = item['slug']
        post_id = item['id']
        entry_id = item['meta']['_metadata_id']
        description = item['content']['rendered']
        if entry_id == '':
            continue
        existing_wordpress_pages.append({'title': title, 'slug': slug, 'entry_id': entry_id,
                                         'page_id': post_id})
print("Fetching wordpress posts")
for item in all_posts:
    if '_metadata_id' in item['meta']:
        title = item['title']['rendered']
        slug = item['slug']
        post_id = item['id']
        entry_id = item['meta']['_metadata_id']
        content = item['content']['rendered']
        if entry_id == '':
            continue
        existing_wordpress_posts.append({'title': title, 'slug': slug, 'entry_id': entry_id,
                                         'page_id': post_id, 'content': content})

print(f"\nCompiling {MODEL} prompts\n")
def update_content(item):
    if ai_links_sweep == 'Y':
        item['content'] = generate_article_links(item['title'], item['content'], json_slug_data)
    else: # find current WordPress content and recycle it
        for curr_item in existing_wordpress_posts:
            if item['entry_id'] == curr_item['entry_id']:
                item['content'] = curr_item['content']
    return item

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(update_content, item) for item in processed_articles]
    processed_articles = [future.result() for future in as_completed(futures)]

print("Fetching wordpress categories")
existing_wordpress_categories = []
fetch_all_categories(all_categories, existing_wordpress_categories)
#print(existing_wordpress_categories)
#print(all_categories)
# activities derived from their links to list of articles

activity_types = {item['activity'] for item in processed_articles}    
page_ids = {}
tag_ids = {}

all_category_ids = []
print("Categories: ")
render_categories(all_categories, all_category_ids, existing_wordpress_categories)

# print("\nActivities: ")
# for activity in sorted(activity_types):
#     category_list = []
#     for item in existing_wordpress_categories:
#         category_list.append(item['category_id'])

#     for item in processed_activities:
#         if item['title'] == activity:
            
#             # call the parallelized function
#             parent_page_id, tag_id = create_page_and_tag(
#                 activity, item['content'], item['slug'], item['hero_image'], item['entry_id'], category_list, existing_page_metadata, existing_tag_metadata
#             )
            
#             page_ids[activity] = parent_page_id
#             tag_ids[activity] = tag_id

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

            print(category_list)
            # Call the parallelized function
            parent_page_id = create_page(
                activity, activity_slug, content, activity_id, image_url, category_list, existing_wordpress_pages
            )
            break
            
sys.exit()
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

