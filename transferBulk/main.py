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
                                  create_tag, create_page, create_posts_concurrently)

# Prompt user on execution parameters
refresh_all_articles = input("Do you need to refresh EVERY article or just the ones updated since last access? (y/n): ").strip().upper()
ai_links_sweep = input("Do you need to reupdate ChatGPT article links? This takes a while. (y/n): ").strip().upper()


clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
database = clientDB['brimming-test']
time_collection = database['contentfulAccessDates']

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
    
all_categories, all_activities, all_articles = [], [], []
contentful_fetching_limit = 25
skip_categories = skip_activities = 0
skip_articles = 0 # might want to change this for testing
all_categories, all_activities, all_articles = fetch_contentful_data(contentful_fetching_limit, skip_categories, skip_activities, skip_articles, date_threshold_articles)


activity_slugs = render_activities(all_activities)
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
        
print("Fetching wordpress tags")
existing_wordpress_tags = fetch_all_tags()
matching_entry = next((entry for entry in existing_wordpress_tags if entry['description'] == '0451'), None) # checking to see if barrier article is already on wordpress
if not matching_entry:
    barrier_article_tag_id = create_tag("Barrier Article", "barrier-articles", '0451', existing_wordpress_tags)
else:
    barrier_article_tag_id = matching_entry['id']
    
print(f"\nCompiling {MODEL} prompts")
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


print("\nCategories: ")
existing_wordpress_categories = fetch_all_categories(all_categories)
all_category_ids = render_categories(all_categories, existing_wordpress_categories)


def create_page_and_tag(title, slug, content, entry_id, image_url, category_list, existing_wordpress_pages, existing_wordpress_tags):
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_parent_page = executor.submit(
            create_page, title, slug, content, entry_id, image_url, category_list, existing_wordpress_pages
        )
        future_tag = executor.submit(
            create_tag, title, slug, entry_id, existing_wordpress_tags
        )
        # Wait for both tasks to complete
        parent_page_id = future_parent_page.result()
        tag_id = future_tag.result()
    return parent_page_id, tag_id


# activities derived from their links to list of articles
activity_types = {item['activity'] for item in processed_articles}    
activity_dict = {entry.fields().get('title'): entry for entry in all_activities}

page_ids = {}
tag_ids = {}

print("\nActivities: ")
for activity in sorted(activity_types):
    entry = activity_dict.get(activity)
    if not entry:
        continue
    entry_fields = entry.fields()
    title = entry_fields.get('title')
    slug = entry_fields.get('slug')  
    entry_id = entry.sys.get('id')

    description_full = entry_fields.get('description_full', [])
    if description_full:
        content = RENDERER.render(description_full)
        
    hero_image = entry_fields.get('hero_image')
    if hero_image:
        image_url = f"https:{hero_image.fields().get('file').get('url')}"

    if title == activity:
        linked_categories = entry_fields.get('categories', [])
        categories_id_list = [category.sys.get('id') for category in linked_categories]
        category_list = []
                    
        category_id_dict = {item['meta_data_id']: item['id'] for item in all_category_ids} # dictionary to look through category id list
        category_list = []
        for category in linked_categories:
            category_id = category.sys.get('id')
            if category_id in category_id_dict:
                category_list.append(category_id_dict[category_id])
                
        # Call the parallelized function
        parent_page_id, tag_id = create_page_and_tag(
            title, slug, content, entry_id, image_url, category_list, existing_wordpress_pages, existing_wordpress_tags
        )
        
        page_ids[activity] = parent_page_id
        tag_ids[activity] = tag_id
        
print("\nArticles: ")
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(create_posts_concurrently, article, existing_wordpress_posts, barrier_article_tag_id, tag_ids): article for article in processed_articles}
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

