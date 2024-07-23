import json
import requests
import contentful
from openai import OpenAI
from datetime import datetime
from requests.auth import HTTPBasicAuth
from rich_text_renderer import RichTextRenderer
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import SPACE_ID, ACCESS_TOKEN, OPENAI_API_TOKEN, USERNAME, PASSWORD

renderer = RichTextRenderer()  # To render RTF input from contentful
clientAI = OpenAI(api_key=OPENAI_API_TOKEN)
ENVIRONMENT = 'development'  # Not master
auth = HTTPBasicAuth(USERNAME, PASSWORD)
activity_url = "https://staging.brimming.app/brims/" # change to corresponding WP permalink
site_url = "https://maesterlinks.wpcomstaging.com/"  # change to final website link
api_url = f"{site_url}wp-json/wp/v2/pages"

try:
    client = contentful.Client(SPACE_ID, ACCESS_TOKEN,  # Initialize Contentful API Client
                               environment=ENVIRONMENT,
                               max_include_resolution_depth=2)
    print("Successfully connected to Contentful client.")
except contentful.errors.NotFoundError as e:
    print(f"Error: {e}")

def generate_article_links(title, article, data):
    html_output = renderer.render(article)
    prompt = f"""
    [ARTICLE START]
    {html_output} 
    [ARTICLE END]
    If any words/phrases match one of the below slugs, then replace its first appearance, no duplicates, with a hyperlink with the format \"{activity_url}<slug>\" Also have the hyperlink visible when the user hovers over it in HTML.

    Slugs: {data}.
    
    Optimize for html output, only output the updated article, nothing else."""

    response = clientAI.chat.completions.create(
        model="gpt-4o",
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

all_entries = []
all_articles = []
slugs = []
titles = []
urls = []
skip = 0
limit = 100  # Max limit per request
date_threshold = datetime(2024, 1, 1).isoformat()

while True:  # Fetch entries with pagination parameters
    entries = client.entries({
        'content_type': "brim",  # Activities View ID
        'limit': limit,
        'skip': skip,
        'order': '-sys.createdAt',
        'sys.updatedAt[gte]': date_threshold  # limiting Brim activities to after start of 2024
    })
    all_entries.extend(entries)  # Append fetched entries to the list
    skip += limit 
    if len(entries) < limit:  # Break the loop if no more entries are fetched
        break
skip = 0
while True:  # Fetch articles with pagination parameters
    articles = client.entries({  
        'content_type': "article",
        'limit': limit,
        'skip': skip,
        'order': '-sys.createdAt',
    })
    all_articles.extend(articles)  # Append fetched articles to the list
    skip += limit 
    if len(articles) < limit:  # Break the loop if no more articles are fetched
        break
    
for entry in all_entries:
    slug = entry.fields().get('slug')  # isolating slug
    slugs.append(slug)
json_slug_data = json.dumps(slugs)
print("Collected all contentful data")

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

    ai_updated_article = generate_article_links(title, content, json_slug_data)  # Add hyperlinks to the article
    
    return {
        'title': title,
        'activity': activity,
        'barrier': barrier,
        'content': ai_updated_article,
        'has_activities_and_barriers': bool(activities_list and barriers_list)
    }

print("Compiling gpt4o prompts")
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

def remove_article_end(content): # clean json content
    return content.replace("[ARTICLE END]", "")
for article in processed_articles:
    article["content"] = remove_article_end(article["content"])


activity_types = {item['activity'] for item in processed_articles}
parent_pages = {}

def fetch_all_pages():
    pages = []
    page = 1
    while True:
        response = requests.get(api_url, params={'per_page': 100, 'page': page}, auth=auth)
        if response.status_code != 200:
            print(f"Failed to fetch pages. Status code: {response.status_code}")
            break
        batch = response.json()
        if not batch:
            break
        pages.extend(batch)
        page += 1
    return pages

def fetch_all_parent_pages():
    pages = []
    page = 1
    while True:
        response = requests.get(api_url, params={'per_page': 100, 'page': page, 'parent': 0}, auth=auth)
        if response.status_code != 200:
            print(f"Failed to fetch pages. Status code: {response.status_code}")
            break
        batch = response.json()
        if not batch:
            break
        pages.extend(batch)
        page += 1
    return pages

def fetch_or_create_parent_page(tag, existing_parent_pages):
    # Check if the parent page (activity) exists in the existing pages list
    for page in existing_parent_pages:
        if page['title']['rendered'].lower() == tag.lower():
            print(f"Existing page found for tag '{tag}': {page['id']}")  # Debug print to confirm existing page usage
            return page['id']
    
    # Create parent page if it doesn't exist
    parent_data = {
        'title': tag,
        'status': 'publish'
    }
    response = requests.post(api_url, json=parent_data, auth=auth)
    if response.status_code in [200, 201]:
        new_page_id = response.json()['id']
        print(f"Created new parent page for tag '{tag}' with ID: {new_page_id}")  # Debug print for new page creation
        existing_parent_pages.append(response.json())  # Add the newly created page to the list
        return new_page_id
    else:
        print(f"Failed to create parent page '{tag}'. Status code: {response.status_code}")
        print(response.json())
        return None

def add_article_as_child_page(article, parent_id):
    child_data = {
        'title': article['title'],
        'content': article['content'],
        'status': 'publish',
        'parent': parent_id
    }
    response = requests.post(f"{api_url}", json=child_data, auth=auth)
    if response.status_code in [200, 201]:
        print(f"Article '{article['title']}' added successfully under parent ID: {parent_id}")
    else:
        print(f"Failed to add article '{article['title']}'. Status code: {response.status_code}")
        print(response.json())

# Fetch all existing parent pages
existing_parent_pages = fetch_all_parent_pages()
print("List of all parent pages:")
for page in existing_parent_pages:
    print(f"ID: {page['id']}, Title: {page['title']['rendered']}")

# Check and create pages
for activity in sorted(activity_types):
    page_id = fetch_or_create_parent_page(activity, existing_parent_pages)
    if page_id:
        parent_pages[activity] = page_id
    else:
        print(f"Page '{activity}' could not be created.")

# Create "Other" parent page
other_page_id = fetch_or_create_parent_page("Other", existing_parent_pages)
if other_page_id:
    print(f"'Other' page is available with ID: {other_page_id}")
else:
    print(f"Failed to create 'Other' page.")
     
     
# Add articles as child pages
for article in processed_articles:
    if article["has_activities_and_barriers"]:
        activity = article["activity"]
        parent_id = parent_pages.get(activity, other_page_id)     
        add_article_as_child_page(article, parent_id)
    else:
        add_article_as_child_page(article, other_page_id) # for articles with no category


print("All articles have been processed successfully.")


def delete_page(page_id):
    response = requests.delete(f"{api_url}/{page_id}", auth=auth)
    if response.status_code == 200:
        print(f"Successfully deleted page ID: {page_id}")
    else:
        print(f"Failed to delete page ID: {page_id}. Status code: {response.status_code}")
pages = fetch_all_pages()
title_dict = {}
duplicates = []

# Organize pages by title and keep the most recent one
for page in pages:
    title = page['title']['rendered']
    created_at = page['date']
    if title in title_dict:
        # Compare dates to keep the most recent one
        if created_at > title_dict[title]['date']:
            duplicates.append(title_dict[title]['id'])
            title_dict[title] = {'id': page['id'], 'date': created_at}
        else:
            duplicates.append(page['id'])
    else:
        title_dict[title] = {'id': page['id'], 'date': created_at}
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(delete_page, page_id): page_id for page_id in duplicates}
    for future in as_completed(futures):
        try:
            future.result()
        except Exception as exc:
            print(f"Exception occurred while deleting page: {exc}")

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

# Modify the suffixes of all pages using the above three functions
parallel_modify_suffixes(pages)
print("All page slugs have been processed.")
