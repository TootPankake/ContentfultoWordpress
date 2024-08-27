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

### category list page -> category detail page -> activity detail page (add article links)
# makefile or input to do clean sweep or only recent articles, maybe add api tokens as parameters to aws function
# exponential backoff
# link to articles instead of barriers -^

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
  
refreshArticles = 'Y'#input("Do you need to refresh EVERY article? (y/n): ").strip().upper()

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
    ai_updated_article = content#generate_article_links(title, content, json_slug_data)  # Add hyperlinks to the article
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
        response = requests.get(api_url, params={'per_page': 100, 'page': page_number}, auth=auth, timeout = 10)
        return response.json() if response.status_code == 200 else []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_page, i) for i in range(1, 10)] 
        for future in as_completed(futures):
            pages.extend(future.result())

    return pages

def fetch_all_categories_concurrently():
    categories = []
    page = 1
    limit = 100

    def fetch_category_page(page_number):
        response = requests.get(f"{URL}/wp-json/wp/v2/categories", params={'per_page': limit, 'page': page_number}, auth=auth, timeout=10)
        return response.json() if response.status_code == 200 else []

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Assuming there are not more than 10 pages of categories; adjust as needed
        futures = [executor.submit(fetch_category_page, i) for i in range(1, 11)]
        for future in as_completed(futures):
            categories.extend(future.result())

    return categories

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

def fetch_category_metadata_concurrently(existing_categories):
    def fetch_metadata(category):
        category_id = category['id']
        meta_url = f'{URL}/wp-json/wp/v2/categories/{category_id}'
        meta_response = requests.get(meta_url, auth=auth, timeout=10)
        if meta_response.status_code == 200:
            meta_data = meta_response.json().get('meta', {})
            metadata_id = meta_data.get('_metadata_id', None)
            if metadata_id:
                return {'id': category_id, 'metadata_id': metadata_id}
        return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_metadata, category) for category in existing_categories]
        for future in as_completed(futures):
            result = future.result()
            if result:
                existing_metadata_categories.append(result)    

def create_category(title, slug, description, entryID):
    # Check if the category already exists by title
    category_id = None
    for cat in existing_categories:
        if cat['name'] == title:
            category_id = cat['id']
            print(f"Category '{title}' already exists with ID {category_id}. Using existing category.")
            break

    if category_id:
        # If category exists, update its description (if needed)
        category_data = {
            'description': description
        }

        response = requests.post(f"{URL}/wp-json/wp/v2/categories/{category_id}", json=category_data, auth=auth)
        if response.status_code == 200:
            print(f'Category "{title}" updated successfully')
        else:
            print(f'Failed to update category: {response.status_code}')
            print(response.json())  # Print the response for debugging
        return category_id
    else:
        # If no matching category found, create a new category
        category_data = {
            'name': title,
            'slug': slug,
            'description': description,
            'meta': {
                '_metadata_id': entryID  # Add the metadata ID to the new category
            }
        }

        response = requests.post(f"{URL}/wp-json/wp/v2/categories", json=category_data, auth=auth)

        # Check if the category creation was successful
        if response.status_code == 201:
            print(f'Category "{title}" created successfully')
            category_id = response.json()['id']
            return category_id
        else:
            print(f'Failed to create category: {response.status_code}')
            print(response.json())  # Print the response for debugging
        return

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
    articleDescription = article['content']
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
            found = True
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
 
def create_child_page_concurrently(article):
    if article["has_activities_and_barriers"]:
        activity = article["activity"]
        parent_id = parent_page_ids.get(activity, other_page_id)  # Get the parent page ID

    create_child_page(article, parent_id)   

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
existing_metadata_categories = []


print("Fetching metadata ID's")
existing_pages = fetch_all_pages_concurrently()
fetch_metadata_id_concurrently(existing_pages)
existing_categories = fetch_all_categories_concurrently()  # Assume this function fetches categories concurrently.
fetch_category_metadata_concurrently(existing_categories)
print(existing_metadata_categories)

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
        create_category(title, slug, description, category_id)
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
                    entry_description = linked_entry.fields().get('description_full','No description')
                    entry_id = linked_entry.sys.get('id', 'Unknown ID')
                    if isinstance(entry_description, dict):
                        try:
                            entry_description = renderer.render(entry_description)
                        except Exception as e:
                            print(f"Failed to render description for '{title}': {e}")
                            entry_description = 'Rendering failed.'
                    #print(f"- {title}: {entry_id}")
            
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

json_slug_data = json.dumps(slugs)
json_article_data = json.dumps(article_data, indent=4)
json_activity_data = json.dumps(activity_data, indent=4)
print("Collected all Contentful data")
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
    for entry in all_activities:
        title = entry.fields().get('title')
        content = entry.fields().get('description_full')
        entry_id = entry.sys.get('id')
        categories = entry.fields().get('categories', [])
        
        # Retrieve both title and ID for each category
        categories_list = [
            {'title': category.fields().get('title'), 'id': category.sys.get('id')}
            for category in categories
        ]
        
        if categories_list:
            category = categories_list[0]
            category_title = category['title']
            category_entry_id = category['id']
            
            # Now you can use both the title and the ID as needed
            print(f"Category Title: {category_title}, Category Entry ID: {category_entry_id}")

            # Retrieve the category ID by title
            category_id = None
            if category_title:
                for cat in existing_categories:
                    if cat['name'] == category_title:
                        category_id = cat['id']
                        break

            if category_id:
                # Update or create the page with the assigned category
                page_id = create_parent_page(title, content, entry_id)
                
                if page_id:
                    # Assign the category to the page
                    page_data = {
                        'categories': [category_id]
                    }

                    response = requests.post(f"{URL}/wp-json/wp/v2/pages/{page_id}", json=page_data, auth=auth)
                    if response.status_code == 200:
                        print(f'Page "{title}" successfully assigned to category "{category_title}"')
                    else:
                        print(f'Failed to assign category "{category_title}" to page "{title}": {response.status_code}')
                        print(response.json())  # Print the response for debugging
            else:
                print(f'Category "{category_title}" not found for page "{title}"')
other_page_id = ""

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(create_child_page_concurrently, article): article for article in processed_articles}

    for future in as_completed(futures):
        article = futures[future]
        try:
            future.result()  # Retrieve the result to trigger any exceptions
        except Exception as exc:
            print(f"Exception occurred while processing article '{article['title']}': {exc}")
        
print("\nAll articles have been processed successfully.")
