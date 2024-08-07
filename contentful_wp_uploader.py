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
model = "gpt-4o"
environment = 'development' # Not master
clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
db = clientDB["brimming-test"]
collection = db["contentfulAccessDates"]
auth = HTTPBasicAuth(USERNAME, PASSWORD)
api_url = f"{URL}wp-json/wp/v2/pages"
meta_url = f"{api_url}/{{page_id}}"


addActivities = 'Y' #input("Do you need to refresh the activity descriptions? (y/n): ").strip().upper()
refreshArticles = 'Y' #input("Do you need to refresh EVERY article? (y/n): ").strip().upper()

try:
    client = contentful.Client(SPACE_ID, ACCESS_TOKEN,  # Initialize Contentful API Client
                               environment=environment,
                               max_include_resolution_depth=1)
    renderer = RichTextRenderer()  # To render RTF input from contentful
    date_threshold = datetime(2024, 1, 1).isoformat()
    print("Successfully connected to Contentful client.")
except contentful.errors.NotFoundError as e:
    print(f"Error: {e}")
    
def generate_article_links(title, article, slug_list):
    html_output = renderer.render(article)
    prompt = f"""
    [ARTICLE START]
    {html_output} 
    [ARTICLE END]
    If any words/phrases match one of the below slugs, then replace its first appearance, no duplicates,
    with a hyperlink with the format \"{URL}<slug>\" Also have the hyperlink visible when the user hovers over it in HTML.

    Slugs: {slug_list}.
    
    Optimize for html output, only output the updated article, nothing else."""

    response = clientAI.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": "Assistant, providing assistance with text processing and link insertion as requested."},
            {"role": "user", "content": prompt}
        ]
    )
    content = response.choices[0].message.content
    content = content.replace('[ARTICLE START]\n', '').replace('\n[ARTICLE END]', '')
    content = content.replace('```html\n', '').replace('\n```', '')
    print(f"Article link completed: {title}")
    return content

def process_article(entry):
    slug = entry.fields().get('slug')  
    title = entry.fields().get('title')
    content = entry.fields().get('content')
    id = entry.sys.get('id')
    
    # activites and barriers are both nested, so they must be looped through
    activities = entry.fields().get('activities', [])
    barriers = entry.fields().get('barriers', [])
    activities_list = [activity.fields().get('title') for activity in activities]
    barriers_list = [barrier.fields().get('title') for barrier in barriers]
    
    activity = activities_list[0] if activities_list else ''
    barrier = barriers_list[0] if barriers_list else ''
    ai_updated_article = content
    #ai_updated_article = generate_article_links(title, content, json_slug_data)  # Add hyperlinks to the article
    
    return {
        'title': title,
        'id': id,
        'slug': slug,
        'activity': activity,
        'barrier': barrier,
        'content': ai_updated_article,
        'has_activities_and_barriers': bool(activities_list and barriers_list)
    }

def fetch_all_pages_concurrently():
    pages = []
    page = 1

    def fetch_page(page_number):
        response = requests.get(api_url, params={'per_page': 100, 'page': page_number}, auth=auth)
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
        meta_response = requests.get(meta_url, auth=auth)
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
                
def create_parent_page(activityTitle, activityDescription, entryID):
    for item in existing_metadata:
        if entryID == item['metadata_id']:
            print(f"{entryID} found")
            page_id = item['id']
            # Update the page content
            page_data = {
                'title': activityTitle,
                'content': activityDescription
            }

            response = requests.post(meta_url.format(page_id=page_id), json=page_data, auth=auth)
            if response.status_code == 200:
                print(f'{activityTitle} updated successfully')
                return page_id
            else:
                print(f'Failed to update page: {response.status_code}')
                print(activityTitle)
                print(response.json())  # Print the response for debugging
            return 

    # If no matching metadata ID found, create a new page
    page_data = {
        'title': activityTitle,
        'content': activityDescription,
        'status': 'publish'
    }

    response = requests.post(api_url, json=page_data, auth=auth)

    # Check if the page creation was successful
    if response.status_code == 201:
        print(f'{activityTitle} created successfully')
        page_id = response.json()['id']

        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': entryID  # Your metadata ID value
            }
        }

        update_meta_response = requests.post(meta_url.format(page_id=page_id), json=meta_data, auth=auth)
        if update_meta_response.status_code == 200:
            print('Metadata updated')
            return page_id
        else:
            print(f'Failed to update metadata: {update_meta_response.status_code}')
            #print(update_meta_response.json())  # Print the response for debugging
    else:
        print(f'Failed to create page: {response.status_code}')
        #print(response.json())  # Print the response for debugging
    return

def create_child_page(article, parent_id):
    articleTitle = article['title']
    articleDescription = renderer.render(article['content'])
    entryID = article['id']
    
    if not articleDescription:
        print(f"Warning: Article '{articleTitle}' has empty content.")
        return
    for item in existing_metadata:
        if entryID == item['metadata_id']:
            print(f"{entryID} found")
            page_id = item['id']
            # Update the page content
            page_data = {
                'title': articleTitle,
                'content': articleDescription,
                'parent': parent_id
            }

            response = requests.post(meta_url.format(page_id=page_id), json=page_data, auth=auth)
            if response.status_code == 200:
                print(f'{articleTitle} updated successfully')
            else:
                print(f'Failed to update page: {response.status_code}')
                print(articleTitle)
                print(response.json())  # Print the response for debugging
            return

    # If no matching metadata ID found, create a new page
    page_data = {
        'title': articleTitle,
        'content': articleDescription,
        'status': 'publish',
        'parent': parent_id
    }

    response = requests.post(api_url, json=page_data, auth=auth)

    # Check if the page creation was successful
    if response.status_code == 201:
        print(f'{articleTitle} created successfully')
        page_id = response.json()['id']

        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': entryID  # Your metadata ID value
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
iteration = 0
limit = 100
all_activities = []
all_articles = []
activity_data = []
article_data = []
slugs = []
existing_metadata = []
existing_pages = fetch_all_pages_concurrently()
fetch_metadata_id_concurrently(existing_pages)

if refreshArticles == 'Y':
    date_threshold = datetime(2024, 1, 1).isoformat()
    date_threshold_articles = datetime(2023, 1, 1).isoformat()
else: 
    dates = list(collection.find().sort('created_at', -1))
    dates_to_delete = dates[1:] # deletes all dates but the last one
    ids_to_delete = [doc['_id'] for doc in dates_to_delete] # Extract the _ids of documents to delete
    collection.delete_many({'_id': {'$in': ids_to_delete}}) # Delete the identified documents
    recent_posts = collection.find().sort("timestamp", -1).limit(1) # Fetch the most recent posts (assuming you have a 'timestamp' field)
    today = {"name": datetime.now(), "created_at": datetime.now()}
    collection.insert_one(today)
    for post in recent_posts:
        formattedTime = post['created_at']
        adjusted_time = formattedTime - timedelta(minutes=1) # gives some leeway on last db date request
        formatted_date = adjusted_time.strftime('%Y-%m-%d %H:%M:%S.%f')
    #date_threshold = formatted_date
    date_threshold_articles = formatted_date
    clientDB.close()

while True:  # Fetch activities with pagination parameters
    activities = client.entries({
        'content_type': "brim",
        'limit': limit,
        'skip': skip1,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold  # limiting Brim activities to after start of 2024
    })
    all_activities.extend(activities)
    skip1 += limit 
    if len(activities) < limit:  # Break the loop if no more entries are fetched
        break
while True:  # Fetch articles with pagination parameters
    articles = client.entries({  
        'content_type': "article",
        'limit': limit,
        'skip': skip2,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold_articles
    })
    all_articles.extend(articles)
    skip2 += limit 
    if len(articles) < limit:  # Break the loop if no more articles are fetched
        break 
for entry in all_articles:
    slug = entry.fields().get('slug')  
    title = entry.fields().get('title')
    description = entry.fields().get('content')
    article_id = entry.sys.get('id')
    slugs.append(slug)
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

json_slug_data = json.dumps(slugs)
json_article_data = json.dumps(article_data, indent=4)
json_activity_data = json.dumps(activity_data, indent=4)
print("Collected all contentful data")

print(f"Compiling {model} prompts")
processed_articles = []
with ThreadPoolExecutor(max_workers=10) as executor: # parallelization of prompt execution
    futures = {executor.submit(process_article, entry): entry for entry in all_articles}

    for future in as_completed(futures):
        article = futures[future]
        try:
            data = future.result()
            processed_articles.append(data)

        except Exception as exc:
            print(f"Exception occurred while processing article: {exc}")

#for article in processed_articles:
#    article["content"] = article["content"].replace("[ARTICLE END]", "")        

activity_types = {item['activity'] for item in processed_articles}
parent_pages = {}
parent_page_ids = {}
body = ""
for activity in sorted(activity_types):
    for entry2 in all_activities:
        title = entry2.fields().get('title')
        content = entry2.fields().get('description_full')
        id = entry2.sys.get('id')
        if content and addActivities == 'Y':
            if title == activity:
                body = renderer.render(content)
                break
            else:
                body = ""
    parent_page_id = create_parent_page(activity, body, id)
    if parent_page_id:
        parent_page_ids[activity] = parent_page_id
        
other_page_id = create_parent_page("Other","","0451")


# Add articles as child pages
for article in processed_articles:
    if article["has_activities_and_barriers"]:
        activity = article["activity"]
        parent_id = parent_page_ids.get(activity, other_page_id)  # Get the parent page ID
        create_child_page(article, parent_id)
    else:
        create_child_page(article, other_page_id)
        
print("All articles have been processed successfully.")
