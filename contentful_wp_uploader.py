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
model = 'gpt-4o'
environment = 'development'
clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
db = clientDB['brimming-test']
collection = db['contentfulAccessDates']
auth = HTTPBasicAuth(USERNAME, PASSWORD)
page_url = f"{URL}wp-json/wp/v2/pages"
meta_url = f"{page_url}/{{page_id}}" 

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
  
refreshArticles = input("\nDo you need to refresh EVERY article or just the ones updated since last access? (y/n): ").strip().upper()
dontSkipCategory = input("Do you want to link and update EVERY category? (y/n): ").strip().upper()
aiSweep = 'N'#input("Do you need to reupdate ChatGPT article links? This takes a while. (y/n): ").strip().upper()

if refreshArticles == 'Y':
    date_threshold_articles = datetime(2023, 1, 1).isoformat()
else: 
    dates = list(collection.find().sort('created_at', -1))
    dates_to_delete = dates[1:] # deletes all dates but the last one
    ids_to_delete = [doc['_id'] for doc in dates_to_delete] # Extract the _ids of documents to delete
    collection.delete_many({'_id': {'$in': ids_to_delete}}) # Delete the identified documents
    recent_posts = collection.find().sort('timestamp', -1).limit(1) # Fetch the most recent posts (assuming you have a 'timestamp' field)
    today = {'name': datetime.now(), 'created_at': datetime.now()}
    collection.insert_one(today) # move to end -^
    for post in recent_posts:
        formattedTime = post['created_at']
        adjusted_time = formattedTime - timedelta(minutes=1) # gives some leeway on last db date request
        formatted_date = adjusted_time.strftime("%Y-%m-%d %H:%M:%S.%f")
    date_threshold_articles = formatted_date
    clientDB.close() ### put in the end
    
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
            {'role': 'system', 'content': "Assistant, providing assistance with text processing and link insertion as requested."},
            {'role': 'user', 'content': prompt}
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
    if aiSweep == 'Y':
        ai_updated_article = generate_article_links(title, content, json_slug_data)  # Add hyperlinks to the article
    else:
        ai_updated_article = renderer.render(content) 
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
        response = requests.get(page_url, params={'per_page': 100, 'page': page_number}, auth=auth, timeout = 10)
        return response.json() if response.status_code == 200 else []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_page, i) for i in range(1, 10)] 
        for future in as_completed(futures):
            pages.extend(future.result())

    return pages

def fetch_metadata_id_concurrently(existing_pages):
    def fetch_metadata(page):
        page_id = page['id']
        meta_response = requests.get(f'{URL}/wp-json/wp/v2/pages/{page_id}', auth=auth, timeout = 10)
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

def fetch_category_metadata_id():
    page = 1
    while True:
        response = requests.get(f"{URL}/wp-json/wp/v2/categories", params={'per_page': 20, 'page': page}, auth=auth)
        categories = response.json()
        
        if not categories:
            break

        for category in categories:
            if 'metadata_id' in category:
                existing_category_metadata.append({'id': category['id'], 'metadata_id': category['metadata_id']})
            else:
                print(f"Category ID: {category['id']} has no Metadata ID.")
        
        page += 1  # Pagination required to obtain more than 10 entries from WP

def create_category(title, description, slug, metadata_id):
    for item in existing_category_metadata:
        if metadata_id == item['metadata_id']:
            category_id = item['id']
            category_data = {
                'name': title,
                'slug': slug,
                'metadata_id': metadata_id,
                'description': description
            }
            existing_category_metadata.append(metadata_id)
            response = requests.post(f"{URL}/wp-json/wp/v2/categories/{category_id}", json=category_data, auth=auth)
            if response.status_code in [200,201]:
                print(f"{title} updated successfully")
                return category_id
            else:
                print(f"Failed to update {title}: {response.status_code}")
                print(response.json())  # Print the response for debugging
            return 
    category_data = {
        'name': title,
        'slug': slug,
        'metadata_id': metadata_id,
        'description': description
    }
    response = requests.post(f"{URL}/wp-json/wp/v2/categories", json=category_data, auth=auth)
    if response.status_code == 201:
        category_id = response.json().get('id')
        print(f'{title} posted successfully')
        return category_id
    else:
        print(f'Failed to create {title}: {response.status_code}')
        print(response.json())
    return 
    
def create_parent_page(activityTitle, activityDescription, entryID, category_ids):
    category_ids = []
    for item in existing_metadata:
        if entryID == item['metadata_id']:
            print(f"{entryID} found")
            page_id = item['id']
            
            if dontSkipCategory != 'Y':
                url = f"{page_url}/{page_id}"
                response = requests.get(url, auth=auth)
                if response.status_code == 200:
                    page_data = response.json()
                    category_ids = page_data.get('categories', [])
                else:
                    print(f"Failed to retrieve page data for page ID {page_id}. Status code: {response.status_code}")
                            
            # Update the page content
            page_data = {
                'title': activityTitle,
                'content': activityDescription,
                'categories': category_ids
            }
            response = requests.post(meta_url.format(page_id=page_id), json=page_data, auth=auth)
            if response.status_code in [200,201]:
                print(f"{activityTitle} updated successfully\n")
                return page_id
            else:
                print(f"Failed to update page: {response.status_code}")
                print(activityTitle)
                print(response.json())  # Print the response for debugging
            return 
    
    # If no matching metadata ID found, create a new page
    page_data = {
        'title': activityTitle,
        'content': activityDescription,
        'categories': category_ids,
        'status': 'publish'
    }

    response = requests.post(page_url, json=page_data, auth=auth)

    if response.status_code == 201:
        print(f"{activityTitle} created successfully\n")
        page_id = response.json()['id']

        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': entryID
            }
        }

        update_meta_response = requests.post(meta_url.format(page_id=page_id), json=meta_data, auth=auth)
        if update_meta_response.status_code in [200,201]:
            print("Metadata updated")
            return page_id
        else:
            print(f"Failed to update metadata: {update_meta_response.status_code}")
    else:
        print(f"Failed to create page: {response.status_code}")
        print(response.json())
    return

def create_child_page(article, parent_id):
    article_title = article['title']
    article_description = article['content']
    entry_ID = article['id']
    
    if not articleDescription:
        print(f"Warning: Article '{article_title}' has empty content.")
        return
    for item in existing_metadata:
        if entry_ID == item['metadata_id']:
            print(f"{entry_ID} found")
            page_id = item['id']
            
            if aiSweep != 'Y':
                url = f"{page_url}/{page_id}"
                response = requests.get(url, auth=auth)
                if response.status_code == 200:
                    page_data = response.json()
                    articleDescription = page_data.get('content', [])
                else:
                    print(f"Failed to retrieve page data for page ID {page_id}. Status code: {response.status_code}")

            # Update the page content
            page_data = {
                'title': article_title,
                'content': article_description,
                'parent': parent_id
            }
            found = True
            response = requests.post(meta_url.format(page_id=page_id), json=page_data, auth=auth)
            if response.status_code == 200:
                print(f"{article_title} updated successfully")
            else:
                print(f"Failed to update page: {response.status_code}")
                print(article_title)
                print(response.json())
            return
  
    # If no matching metadata ID found, create a new page
    page_data = {
        'title': article_title,
        'content': articleDescription,
        'status': 'publish',
        'parent': parent_id
    }

    response = requests.post(page_url, json=page_data, auth=auth)

    # Check if the page creation was successful
    if response.status_code == 201:
        print(f'{article_title} created successfully')
        page_id = response.json()['id']

        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': entry_ID  # Your metadata ID value
            }
        }

        update_meta_response = requests.post(meta_url.format(page_id=page_id), json=meta_data, auth=auth)
        if update_meta_response.status_code == 200:
            return #print('Metadata updated successfully')
        else:
            print(f"Failed to update metadata: {update_meta_response.status_code}")
            print(update_meta_response.json())
    else:
        print(f"Failed to create page: {response.status_code}")
        print(response.json()) 
 
def create_child_page_concurrently(article):
    if article['has_activities_and_barriers']:
        activity = article['activity']
        parent_id = parent_page_ids.get(activity, other_page_id)  # Get the parent page ID

    create_child_page(article, parent_id)   

skip1 = 0
skip2 = 0
skip3 = 0
iteration = 0
limit = 25
all_categories = []
all_activities = []
all_articles = []
activity_data = []
article_data = []
slugs = []
existing_metadata = []
existing_category_metadata = []

print("\nFetching metadata ID's")
existing_pages = fetch_all_pages_concurrently()
fetch_metadata_id_concurrently(existing_pages)
fetch_category_metadata_id()

while True: # Fetch categories
    categories = client.entries({
        'content_type': 'category',
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
        'content_type': 'brim',
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
        'content_type': 'article',
        'limit': limit,
        'skip': skip3,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold_articles
    })
    all_articles.extend(articles)
    skip3 += limit 
    if len(articles) < limit:  # Break the loop if no more articles are fetched
        break 

print("Fetching contentful data")
for entry in all_categories:
    slug = entry.fields().get('slug')  
    title = entry.fields().get('title')
    description = entry.fields().get('description') # change to whatever we choose as the name for description
    category_type = entry.fields().get('category_type')
    category_id = entry.sys.get('id')
    #if category_type == 'Activity' and dontSkipCategory == 'Y':
    #    create_category(title, "", slug, category_id)
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
            'id': article_id,
            'slug': slug,
            'title': title,
            'description': rendered_description
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
            'id': activity_id,
            'slug': slug,
            'title': title,
            'description': rendered_description
        })

fetch_category_metadata_id()
json_slug_data = json.dumps(slugs)
json_article_data = json.dumps(article_data, indent=4)
json_activity_data = json.dumps(activity_data, indent=4)
print("Collected all contentful data")

print(f"Compiling {model} prompts\n")
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

if aiSweep == 'Y':
    for article in processed_articles:
        article['content'] = article['content'].replace("[ARTICLE END]", "")    

activity_types = {item['activity'] for item in processed_articles}    
parent_pages = {}
parent_page_ids = {}
body = ""

for activity in sorted(activity_types):
    for entry in all_activities:
        title = entry.fields().get('title')
        content = entry.fields().get('description_full', [])
        categories = entry.fields().get('categories', [])
        activity_slug = entry.fields().get('slug', [])

        
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
            id = entry.sys.get('id')
            if dontSkipCategory == 'Y':
                for titles, slugs, ids in zip(categories_title_list, categories_slug_list, categories_id_list):
                    category_id = create_category(titles, "", slugs, ids)
                    category_list.append(category_id)
            else:
                category_list = []
            
            if content:
                content = renderer.render(content)
                content += "\nArticles: \n"
                for i in articles_list:
                    content += f"https://discover.brimming.app/{i}\n"
                parent_page_id = create_parent_page(activity, content, id, category_list)
                parent_page_ids[activity] = parent_page_id
            if not content:
                content = "\nArticles: \n"
                for i in articles_list:
                    content += f"https://discover.brimming.app/{i}\n"
                parent_page_id = create_parent_page(activity, content, id, category_list)
                parent_page_ids[activity] = parent_page_id
other_page_id = ""
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(create_child_page_concurrently, article): article for article in processed_articles}
    for future in as_completed(futures):
        article = futures[future]
        try:
            future.result()  # Retrieve the result to trigger any exceptions
        except Exception as exc:
            article_title = article.get('title', 'Unknown Title')
            print(f"Exception occurred while processing article '{article['title']}': {exc}")

print("\nAll articles have been processed successfully.")
