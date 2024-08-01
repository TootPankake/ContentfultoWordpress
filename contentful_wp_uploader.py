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
from config import SPACE_ID, ACCESS_TOKEN, OPENAI_API_TOKEN, USERNAME, PASSWORD, URI

### TODO
# fetch contentful entry ID as title
# make Y then N work by using not gpt article processing to amass slugs
# add barriers (eventually) to bottom of activity page, for now just link to other articles about darts example
# array of types activity barrier navigator, + more added in the future
# makefile or input to do clean sweep or only recent articles, maybe add api tokens as parameters to aws function
# pivot to page ID's instead of title for updating, update contentful too, maybe a separate system

clientAI = OpenAI(api_key=OPENAI_API_TOKEN)
model = "gpt-4o"
environment = 'development' # Not master
clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
db = clientDB["brimming-test"]
collection = db["contentfulAccessDates"]
auth = HTTPBasicAuth(USERNAME, PASSWORD)
site_url = "https://maesterlinks.wpcomstaging.com/"  # change to final website link
api_url = f"{site_url}wp-json/wp/v2/pages"

#delete_all_pages()

addActivities = input("Do you need to refresh the activity descriptions? (y/n): ").strip().upper()
refreshArticles = input("Do you need to refresh EVERY article? (y/n): ").strip().upper()

try:
    client = contentful.Client(SPACE_ID, ACCESS_TOKEN,  # Initialize Contentful API Client
                               environment=environment,
                               max_include_resolution_depth=1)
    renderer = RichTextRenderer()  # To render RTF input from contentful
    print("Successfully connected to Contentful client.")
except contentful.errors.NotFoundError as e:
    print(f"Error: {e}")
    
def generate_article_links(title, article, data):
    html_output = renderer.render(article)
    prompt = f"""
    [ARTICLE START]
    {html_output} 
    [ARTICLE END]
    If any words/phrases match one of the below slugs, then replace its first appearance, no duplicates,
    with a hyperlink with the format \"{site_url}<slug>\" Also have the hyperlink visible when the user hovers over it in HTML.

    Slugs: {data}.
    
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

def process_article(article):
    content = article.fields().get('content', {})  # isolating content from each article
    title = article.fields().get('title', 'No Title')

    # activites and barriers are both nested, so they must be looped through
    activities = article.fields().get('activities', [])
    barriers = article.fields().get('barriers', [])
    
    activities_list = [activity.fields().get('title') for activity in activities]
    barriers_list = [barrier.fields().get('title') for barrier in barriers]
    
    activity = activities_list[0] if activities_list else ''
    barrier = barriers_list[0] if barriers_list else ''
    ai_updated_article = content
    #ai_updated_article = generate_article_links(title, content, json_slug_data)  # Add hyperlinks to the article
    
    return {
        'title': title,
        'activity': activity,
        'barrier': barrier,
        'content': ai_updated_article,
        'has_activities_and_barriers': bool(activities_list and barriers_list)
    }

def delete_all_pages():
    all_pages = fetch_all_pages()
        
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(delete_page, page['id']) for page in all_pages]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print(f"Exception occurred while deleting page: {exc}")
                
def fetch_all_pages():
    pages = []
    page = 1
    while True:
        response = requests.get(api_url, params={'per_page': 100, 'page': page}, auth=auth)
        if response.status_code != 200:
            #print(f"Failed to fetch pages. Status code: {response.status_code}")
            break
        batch = response.json()
        if not batch:
            break
        pages.extend(batch)
        page += 1
    return pages

def fetch_all_page_titles():
    titles = []
    page_number = 1
    while True:
        response = requests.get(api_url, params={'per_page': 100, 'page': page_number}, auth=auth)
        if response.status_code != 200:
            print(f"Failed to fetch pages. Status code: {response.status_code}")
            break
        batch = response.json()
        if not batch:
            break
        for page in batch:
            title = page['title']['rendered']
            page_id = page['id']
            # Replace HTML entity with a regular tokens
            title = title.replace('&#8221;', '"')
            title = title.replace('&#8220;', '"')
            title = title.replace('&#8217;', "'")  
            title = title.replace('&#8211;', "-")  
            title = title.replace('&#038;', '&')
            title = title.strip()

            titles.append((page_id, title))
        page_number += 1
    return titles

def fetch_all_parent_pages():
    pages = []
    page = 1
    while True:
        response = requests.get(api_url, params={'per_page': 100, 'page': page, 'parent': 0}, auth=auth)
        if response.status_code != 200:
            #print(f"Failed to fetch pages. Status code: {response.status_code}")
            break
        batch = response.json()
        if not batch:
            break
        pages.extend(batch)
        page += 1
    return pages
    
def create_parent_page_body(tag, existing_parent_pages, body):
    # Check if the parent page (activity) exists in the existing pages list
    for page in existing_parent_pages:
        if page['title']['rendered'].lower() == tag.lower():
            page_id = page['id']
            print(f"Existing page found for tag '{tag}': {page_id}")  # Debug print to confirm existing page usage
            
            # Fetch the existing content of the page
            response = requests.get(f'{api_url}/{page_id}', auth=auth)
            if response.status_code == 200:
                # Update the page with the new content
                update_response = requests.post(
                    f'{api_url}/{page_id}',
                    auth=auth,
                    json={'content': body}
                )

                if update_response.status_code == 200:
                    print('Page updated successfully!')
                else:
                    print(f'Failed to update the page: {update_response.status_code}')
            else:
                print(f'Failed to fetch the page content: {response.status_code}')

            return page_id
    create_response = requests.post(api_url, auth=auth,
        json={
            'title': tag,
            'content': body,
            'status': 'publish'  # or 'draft' depending on your needs
        }
    )

    if create_response.status_code == 201:
        new_page_id = create_response.json()['id']
        print(f'New page created successfully with ID: {new_page_id}')
        return new_page_id
    else:
        print(f'Failed to create new page: {create_response.status_code}')
        return None

def create_child_page(article, parent_id):
    article_title = article['title'].strip()
    for page_id, title in existing_pages: # Check if the title matches any existing page title
        if title == article_title: ### CHANGE TO PAGE ID!!!
            update_data = {
                'title': article_title,
                'content': article['content'],
                'status': 'publish',
                'parent': parent_id
            }
            response = requests.post(f"{api_url}/{page_id}", json=update_data, auth=auth)
            if response.status_code == 200:
                print(f"Article '{article_title}' updated successfully with ID: {page_id}")
            else:
                print(f"Failed to update article '{article_title}'. Status code: {response.status_code}")
                print(response.json())
            return
    
    child_data = { # If no matching title is found, create a new page
        'title': article_title,
        'content': article['content'],
        'status': 'publish',
        'parent': parent_id
    }
    response = requests.post(api_url, json=child_data, auth=auth)
    if response.status_code in [200, 201]:
        print(f"Article '{article_title}' added successfully under parent ID: {parent_id}")
    else:
        print(f"Failed to add article '{article_title}'. Status code: {response.status_code}")
        print(response.json())
        
def delete_page(page_id):
    response = requests.delete(f"{api_url}/{page_id}", auth=auth)
    if response.status_code == 200:
        print(f"Successfully deleted page ID: {page_id}")
    else:
        print(f"Failed to delete page ID: {page_id}. Status code: {response.status_code}")
        
def update_slug(page_id, new_slug):
    update_data = {
        'slug': new_slug
    }
    response = requests.post(f"{api_url}/{page_id}", json=update_data, auth=auth)
    if response.status_code in [200, 201]:
        print(f"Slug updated to '{new_slug}' for page ID: {page_id}")
    else:
        print(f"Failed to update slug for page ID: {page_id}. Status code: {response.status_code}")
        print(response.json())

def modify_suffixes(page):
    original_slug = page['slug']
    for i in range(2, 11):
        if original_slug.endswith(f'-{i}'):
            new_slug = original_slug.replace(f'-{i}', '')
            update_slug(page['id'], new_slug)
            break  # Exit the loop once the slug is updated

def parallel_modify_suffixes(pages):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(modify_suffixes, page) for page in pages]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"An error occurred: {e}")
         
all_entries = []
all_articles = []
slugs = []
titles = []
skip1 = 0
skip2 = 0
iteration = 0
limit = 100  # Max limit per request
existing_parent_pages = fetch_all_parent_pages()
existing_pages = fetch_all_page_titles()

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
    date_threshold = formatted_date
    date_threshold_articles = formatted_date
    clientDB.close()

while True:  # Fetch activities with pagination parameters
    entries = client.entries({
        'content_type': "brim",  # Activities View ID
        'limit': limit,
        'skip': skip1,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold  # limiting Brim activities to after start of 2024
    })
    all_entries.extend(entries)
    skip1 += limit 
    if len(entries) < limit:  # Break the loop if no more entries are fetched
        break
while True:  # Fetch articles with pagination parameters
    articles = client.entries({  
        'content_type': "article",
        'limit': limit,
        'skip': skip2,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold_articles
    })
    all_articles.extend(articles)  # Append fetched articles to the list
    skip2 += limit 
    if len(articles) < limit:  # Break the loop if no more articles are fetched
        break 

for entry in all_entries:
    slug = entry.fields().get('slug')  # isolating slug
    slugs.append(slug)
json_slug_data = json.dumps(slugs)
print("Collected all contentful data")

print(f"Compiling {model} prompts")
processed_articles = []
with ThreadPoolExecutor(max_workers=10) as executor: # parallelization of prompt execution
    futures = {executor.submit(process_article, article): article for article in all_articles}

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
body = ''
for activity in sorted(activity_types):
    for entry2 in all_entries:
        title = entry2.fields().get('title')
        content = entry2.fields().get('description_full')
        if content and addActivities == 'Y':
            if title == activity:
                body = renderer.render(content)
                break
        else:
            body = ""
    page_id = create_parent_page_body(activity, existing_parent_pages, body)
    if page_id:
        parent_pages[activity] = page_id
    else:
        print(f"Page '{activity}' could not be created.")

# Create "Other" parent page
other_page_id = create_parent_page_body("Other", existing_parent_pages,"")
if other_page_id:
    print(f"'Other' page is available with ID: {other_page_id}")
else:
    print(f"Failed to create 'Other' page.")
    
# Add articles as child pages
for article in processed_articles:
    if article["has_activities_and_barriers"]:
        activity = article["activity"]
        parent_id = parent_pages.get(activity, other_page_id)
        create_child_page(article, parent_id)
    else:
        create_child_page(article, other_page_id) # for articles with no category

print("All articles have been processed successfully.")
