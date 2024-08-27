import sys
import json
import requests
import certifi
import contentful
from openai import OpenAI
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient
from rich_text_renderer import RichTextRenderer
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import SPACE_ID, ACCESS_TOKEN, OPENAI_API_TOKEN, USERNAME, PASSWORD, URI, URL

clientAI = OpenAI(api_key=OPENAI_API_TOKEN)
model = "gpt-4o-mini"
environment = 'development' # Not master
clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
db = clientDB["brimming-test"]
collection = db["contentfulAccessDates"]
auth = HTTPBasicAuth(USERNAME, PASSWORD)
api_url = f"{URL}wp-json/wp/v2/pages"
meta_url = f"{api_url}/{{page_id}}" 

try:
    client = contentful.Client(SPACE_ID, ACCESS_TOKEN,  # Initialize Contentful API Client
                               environment=environment,
                               max_include_resolution_depth=1)
    renderer = RichTextRenderer()  # To render RTF input from contentful
    date_threshold = datetime(2024, 1, 1).isoformat()
    date_threshold_categories = datetime(2023, 1, 1).isoformat()
    print("Successfully connected to Contentful client.")
except contentful.errors.NotFoundError as e:
    print(f"Error: {e}")

refreshArticles = 'Y' #input("Do you need to refresh EVERY article? (y/n): ").strip().upper()
if refreshArticles == 'Y':
    date_threshold_articles = datetime(2023, 1, 1).isoformat()
else: 
    dates = list(collection.find().sort('created_at', -1))
    dates_to_delete = dates[1:] # deletes all dates but the last one
    ids_to_delete = [doc['_id'] for doc in dates_to_delete] # Extract the _ids of documents to delete
    collection.delete_many({'_id': {'$in': ids_to_delete}}) # Delete the identified documents
    recent_posts = collection.find().sort("timestamp", -1).limit(1) # Fetch the most recent posts (assuming you have a 'timestamp' field)
    today = {"name": datetime.now(), "created_at": datetime.now()}
    collection.insert_one(today) # move to end -^
    for post in recent_posts:
        formattedTime = post['created_at']
        adjusted_time = formattedTime - timedelta(minutes=1) # gives some leeway on last db date request
        formatted_date = adjusted_time.strftime('%Y-%m-%d %H:%M:%S.%f')
    date_threshold_articles = formatted_date
    clientDB.close() ### put in the end
    
def fetch_all_pages_concurrently():
    pages = []
    page = 1

    def fetch_page(page_number):
        response = requests.get(api_url, params={'per_page': 100, 'page': page_number}, auth=auth, timeout = 10)
        return response.json() if response.status_code == 200 else []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_page, i) for i in range(1, 10)] 
        for future in as_completed(futures):
            pages.extend(future.result())

    return pages

def fetch_metadata_id_concurrently(existing_pages):
    def fetch_metadata(page):
        page_id = page['id']
        meta_url = f'{URL}/wp-json/wp/v2/pages/{page_id}'
        meta_response = requests.get(meta_url, auth=auth, timeout = 10)
        if meta_response.status_code == 200:
            meta_data = meta_response.json().get('meta', {})
            metadata_id = meta_data.get('_metadata_id', None)
            if metadata_id:
                return {'id': page_id, 'metadata_id': metadata_id}
        return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_metadata, page) for page in existing_pages]
        for future in as_completed(futures):
            result = future.result()
            if result:
                existing_metadata.append(result)

def create_grandparent_page(categoryTitle, categoryDescription, entryID):
    for item in existing_metadata:
        if entryID == item['metadata_id']:
            #print(f"{entryID} found")
            page_id = item['id']
            # Update the page content
            page_data = {
                'title': categoryTitle,
                'content': categoryDescription
            }

            response = requests.post(meta_url.format(page_id=page_id), json=page_data, auth=auth)
            if response.status_code == 200:
                print(f'{categoryTitle} updated successfully')
                return page_id
            else:
                print(f'Failed to update page: {response.status_code}')
                print(categoryTitle)
                print(response.json())  # Print the response for debugging
            return 

    # If no matching metadata ID found, create a new page
    page_data = {
        'title': categoryTitle,
        'content': categoryDescription,
        'status': 'publish'
    }

    response = requests.post(api_url, json=page_data, auth=auth)

    # Check if the page creation was successful
    if response.status_code == 201:
        print(f'{categoryTitle} created successfully')
        page_id = response.json()['id']

        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': entryID  # Your metadata ID value
            }
        }

        update_meta_response = requests.post(meta_url.format(page_id=page_id), json=meta_data, auth=auth)
        if update_meta_response.status_code == 200:
            #print('Metadata updated')
            return page_id
        else:
            print(f'Failed to update metadata: {update_meta_response.status_code}')
            #print(update_meta_response.json())  # Print the response for debugging
    else:
        print(f'Failed to create page: {response.status_code}')
        #print(response.json())  # Print the response for debugging
    return

def create_child_page(entry_id, title, content, grandparent_id):
    for item in existing_metadata:
        if entry_id == item['metadata_id']:
            print(f"{entry_id} found")
            page_id = item['id']
            # Update the page content
            page_data = {
                'title': title,
                'content': content,
                'parent': grandparent_id
            }

            response = requests.post(meta_url.format(page_id=page_id), json=page_data, auth=auth)
            if response.status_code == 200:
                print(f'{title} updated successfully')
            else:
                print(f'Failed to update page: {response.status_code}')
                print(title)
                print(response.json())  # Print the response for debugging
            return
    print(entry_id)
    # If no matching metadata ID found, create a new page
    page_data = {
        'title': title,
        'content': content,
        'status': 'publish',
        'parent': grandparent_id
    }

    response = requests.post(api_url, json=page_data, auth=auth)

    # Check if the page creation was successful
    if response.status_code == 201:
        print(f'{title} created successfully')
        page_id = response.json()['id']

        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': entry_id  # Your metadata ID value
            }
        }

        update_meta_response = requests.post(meta_url.format(page_id=page_id), json=meta_data, auth=auth)
        if update_meta_response.status_code == 200:
            return #print('Metadata updated successfully')
        else:
            print(f'Failed to update metadata: {update_meta_response.status_code}')
            #print(update_meta_response.json())  # Print the response for debugging
    else:
        print(f'Failed to create page: {response.status_code}')
        #print(response.json())  # Print the response for debugging
        
skip1 = 0
skip2 = 0
skip3 = 0
iteration = 0
limit = 50
all_categories = []
all_activities = []
all_articles = []
activity_data = []
article_data = []
slugs = []
existing_metadata = []

print("Fetching metadata ID's")
existing_pages = fetch_all_pages_concurrently()
fetch_metadata_id_concurrently(existing_pages)

print("Fetching contentful data")
while True: # Fetch categories
    categories = client.entries({
        'content_type': "category",
        'limit': limit,
        'skip': skip1,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold_categories  # limiting Brim activities to after start of 2024
    })
    all_categories.extend(categories)
    skip1 += limit 
    if len(categories) < limit:  # Break the loop if no more entries are fetched
        break
while True:  # Fetch activities 
    activities = client.entries({
        'content_type': "brim",
        'limit': limit,
        'skip': skip2,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold  # limiting Brim activities to after start of 2024
    })
    all_activities.extend(activities)
    skip2 += limit 
    if len(activities) < limit:  # Break the loop if no more entries are fetched
        break
while True:  # Fetch articles 
    articles = client.entries({  
        'content_type': "article",
        'limit': limit,
        'skip': skip3,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold_articles
    })
    all_articles.extend(articles)
    skip3 += limit 
    if len(articles) < limit:  # Break the loop if no more articles are fetched
        break 

print("Parsing contentful entries")
for entry in all_categories:
    slug = entry.fields().get('slug')  
    title = entry.fields().get('title')
    description = entry.fields().get('description') # change to whatever we choose as the name for description
    category_type = entry.fields().get('category_type')
    category_id = entry.sys.get('id')
    if category_type == "Activity":
        grandparent_id = create_grandparent_page(title, description, category_id)
        linked_entries = client.entries({
        'links_to_entry': category_id
        })
        limit = 20
        skip = 0
        total_fetched = 0

        while True:
            linked_entries = client.entries({
                'links_to_entry': category_id,
                'skip': skip,
                'limit': limit
            })

            # Process the fetched entries
            for linked_entry in linked_entries:
                content_type = linked_entry.sys.get('content_type')
                if content_type.id == "brim":  # Check if content type is 'article'
                    title = linked_entry.fields().get('title', 'No title')
                    content = linked_entry.fields().get('description_full')
                    if content:
                        content = renderer.render(content)
                    else:
                        content = ""
                    entry_id = linked_entry.sys.get('id', 'Unknown ID')
                    #print(f"- {title}: {entry_id}")
                    create_child_page(entry_id, title, content, grandparent_id)
            
            total_fetched += len(linked_entries)
            skip += len(linked_entries)
            if len(linked_entries) < limit:
                break
            
            total_fetched += len(linked_entries)
            skip += len(linked_entries)
            if len(linked_entries) < limit:
                break
for entry in all_articles:
    slug = entry.fields().get('slug')  
    title = entry.fields().get('title')
    description = entry.fields().get('content')
    article_id = entry.sys.get('id')
    if description:
        try:
            rendered_description = renderer.render(description)
        except Exception as e:
            rendered_description = str(e)
    else:
        rendered_description = None
        
    if article_id and slug and title and rendered_description:
        article_data.append({
            "id": article_id,
            "slug": slug,
            "title": title,
            "description": rendered_description
        })
for entry in all_activities:
    slug = entry.fields().get('slug')  
    title = entry.fields().get('title')
    description = entry.fields().get('description_full')
    activity_id = entry.sys.get('id')
    slugs.append(slug)
    if description:
        try:
            rendered_description = renderer.render(description)
        except Exception as e:
            rendered_description = str(e)
    else:
        rendered_description = None
        
    if activity_id and slug and title and rendered_description:
        activity_data.append({
            "id": activity_id,
            "slug": slug,
            "title": title,
            "description": rendered_description
        })

print("Collected all contentful data")
