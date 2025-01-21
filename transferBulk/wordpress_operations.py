import requests
import time
from config import URL, AUTH
from concurrent.futures import ThreadPoolExecutor, as_completed
# Page (activity) operations
def fetch_page(page):
    try:
        response = requests.get(
            f"{URL}wp-json/wp/v2/pages",
            params={'per_page': 100, 'page': page},
            auth=AUTH,
            timeout=30
        )
        response.raise_for_status()
        return response.json(), response.headers
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page {page}: {e}")
        return None, None

def get_total_pages():
    response = requests.get(
        f"{URL}wp-json/wp/v2/pages",
        params={'per_page': 100, 'page': 1},
        auth=AUTH,
        timeout=30
    )
    if response.status_code == 200:
        return int(response.headers.get('X-WP-TotalPages', 1))
    else:
        response.raise_for_status()
        return 1

def fetch_all_pages_concurrently():
    total_pages = get_total_pages()
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_page = {executor.submit(fetch_page, page): page for page in range(1, total_pages + 1)}
        
        for future in as_completed(future_to_page):
            data, _ = future.result()
            if data:
                results.extend(data)
    
    return results

# Post (article) operations
def fetch_post(page):
    retry_delay = 5
    max_delay = 60
    while True:
        try:
            response = requests.get(
                f"{URL}wp-json/wp/v2/posts",
                params={'per_page': 100, 'page': page},
                auth=AUTH,
                timeout=30
            )
            if response.status_code == 429:
                print(f"Rate limited on page {page}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)  # Exponential backoff
                continue
            response.raise_for_status()
            return response.json(), response.headers
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page {page}: {e}")
            return None, None

def get_total_posts():
    response = requests.get(
        f"{URL}wp-json/wp/v2/posts",
        params={'per_page': 1, 'page': 1},
        auth=AUTH,
        timeout=30
    )
    if response.status_code == 200:
        return int(response.headers.get('X-WP-Total', 1))
    else:
        response.raise_for_status()
        return 1

def fetch_all_posts_concurrently():
    total_posts = get_total_posts()
    total_pages = (total_posts // 100) + 1  # Calculate total number of pages
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_page = {executor.submit(fetch_post, page): page for page in range(1, total_pages + 1)}
        
        for future in as_completed(future_to_page):
            data, _ = future.result()
            if data:
                results.extend(data)
    
    return results


def fetch_all_tags():
    existing_tag_metadata = []
    page = 1
    while True:
        response = requests.get(f"{URL}/wp-json/wp/v2/tags", params={'per_page': 20, 'page': page}, auth=AUTH, timeout = 30)
        tags = response.json()
        
        if not tags:
            break

        for tag in tags:
            description = tag.get('description', '')  # Fetch the description field
            existing_tag_metadata.append({'id': tag['id'], 'description': description})
            if not description:
                print(f"Tag ID: {tag['id']} has no description.")
        page += 1 
    return existing_tag_metadata
        
def fetch_all_categories(all_categories):
    existing_wordpress_categories = []
    page = 1
    while True:
        response = requests.get(f"{URL}/wp-json/wp/v2/categories", params={'per_page': 20, 'page': page}, auth=AUTH, timeout = 30)
        categories = response.json()
        
        if not categories:
            break
        
        for category in categories:
            if 'metadata_id' in category:
                for entry in all_categories:
                    category_contentful_entry_id = entry.sys.get('id')
                    if category_contentful_entry_id == category['metadata_id']:
                        category_title = entry.fields().get('title')
                        category_slug = entry.fields().get('slug')  
                        #category_type = entry.fields().get('category_type')
                        existing_wordpress_categories.append({'category_id': category['id'], 'metadata_id': category['metadata_id'], 
                                                              "category_title": category_title, 'category_slug': category_slug})
            else:
                print(f"Category ID: {category['id']} has no Metadata ID.")
        page += 1
    return existing_wordpress_categories


def create_category(title, description, slug, metadata_id, existing_category_metadata):
    for item in existing_category_metadata:
        if metadata_id == item['metadata_id']:
            category_id = item['category_id']
            category_data = {
                'name': title,
                'slug': slug,
                'metadata_id': metadata_id,
                'description': description
            }
            existing_category_metadata.append(metadata_id)
            response = requests.post(f"{URL}/wp-json/wp/v2/categories/{category_id}", json=category_data, auth=AUTH)
            if response.status_code in [200,201]:
                print(f"updated --> {title}")
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
    response = requests.post(f"{URL}/wp-json/wp/v2/categories", json=category_data, auth=AUTH)
    if response.status_code == 201:
        category_id = response.json().get('id')
        print(f'created --> {title}')
        return category_id
    else:
        print(f'Failed to create {title}: {response.status_code}')
        print(response.json())
    return  

def create_tag(title, slug, entry_id, existing_wordpress_tags):
    for item in existing_wordpress_tags:
        if entry_id == item['description']:
            tag_id = item['id']
            tag_data = {
                'name': title,
                'slug': slug,
                'description': entry_id,
            }
            response = requests.put(f"{URL}/wp-json/wp/v2/tags/{tag_id}", json=tag_data, auth=AUTH)
            if response.status_code in [200, 201]:
                print(f"tag updated --> {title}")
                return tag_id
            else:
                print(f"Failed to update {title}: {response.status_code}")
                print(response.json())
            return

    # If the tag does not exist, create a new one
    tag_data = {
        'name': title,
        'slug': slug,
        'description': entry_id,
    }
    response = requests.post(f"{URL}/wp-json/wp/v2/tags", json=tag_data, auth=AUTH)
    if response.status_code == 201:
        tag_id = response.json().get('id')
        print(f"tag created --> {title}")
        return tag_id
    else:
        print(f"Failed to create {title}: {response.status_code}")
        print(response.json())
    return

def create_page(title, slug, content, entry_id, image_url, category_list, existing_wordpress_pages):
    for item in existing_wordpress_pages:
        if entry_id == item['entry_id']:
            page_id = item['page_id']
            
            # Update the page content
            page_data = {
                'title': title,
                'content': content,
                'slug': slug,
                'categories': category_list,
            }
            response = requests.post(f"{URL}wp-json/wp/v2/pages/{page_id}".format(page_id=page_id), json=page_data, auth=AUTH)
            if response.status_code in [200,201]:
                print(f"page updated --> {title}")
                set_fifu_image(page_id, image_url)
                return page_id
            else:
                print(f"Failed to update page: {response.status_code}")
                print(title)
                print(response.json())  # Print the response for debugging
            return 
    
    # If no matching metadata ID found, create a new page
    page_data = {
        'title': title,
        'content': content,
        'categories': category_list,
        'slug': slug,
        'status': 'publish',
    }

    response = requests.post(f"{URL}wp-json/wp/v2/pages", json=page_data, auth=AUTH)

    if response.status_code == 201:
        print(f"page created --> {title}")
        page_id = response.json()['id']
        set_fifu_image(page_id, image_url)
        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': entry_id,
            }
        }

        update_meta_response = requests.post(f"{URL}wp-json/wp/v2/pages/{page_id}".format(page_id=page_id), json=meta_data, auth=AUTH)
        if update_meta_response.status_code in [200,201]:
            #print("Metadata updated")
            return page_id
        else:
            print(f"Failed to update metadata: {update_meta_response.status_code}")
    else:
        print(f"Failed to create page: {response.status_code}")
        print(response.json())
    return

def set_fifu_image(post_id, image_url):
    # Set the featured image URL via the WordPress REST API
    endpoint = f"{URL}/wp-json/fifu/v1/set-image"
    payload = {
        'post_id': post_id,
        'image_url': image_url
    }

    try:
        response = requests.post(endpoint, json=payload, auth=AUTH)
        if response.status_code in [200, 201]:
            #print(f"Featured image URL set successfully for post ID {post_id}.")
            return response.json()  # Return the API response
        else:
            print(f"Failed to set featured image for post ID {post_id}. Status Code: {response.status_code}")
            print(f"Error: {response.json()}")
            return None
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    
    
def create_post(title, slug, entry_id, content, existing_wordpress_posts, activity_tag_id, barrier_article_tag_id):
    for item in existing_wordpress_posts:
        if entry_id == item['entry_id']:
            page_id = item['page_id']
            # Update the page content
            page_data = {
                'title': title,
                'content': content,
                'slug': slug,
                'tags': [activity_tag_id, barrier_article_tag_id],
            }
            response = requests.post(f"{URL}wp-json/wp/v2/posts/{page_id}".format(page_id=page_id), json=page_data, auth=AUTH)
            if response.status_code == 200:
                print(f"post updated --> {title}")
            else:
                print(f"Failed to update page: {response.status_code}")
                print(title)
                print(response.json())
            return
        
    # If no matching metadata ID found, create a new page
    page_data = {
        'title': title,
        'content': content,
        'slug': slug,
        'status': 'publish',
        'tags': [activity_tag_id, barrier_article_tag_id],
    }

    response = requests.post(f"{URL}wp-json/wp/v2/posts", json=page_data, auth=AUTH)

    # Check if the page creation was successful
    if response.status_code == 201:
        print(f'post created --> {title}')
        page_id = response.json()['id']
        meta_data = {
            'meta': {
                '_metadata_id': entry_id,
            }
        }

        update_meta_response = requests.post(f"{URL}wp-json/wp/v2/posts/{page_id}".format(page_id=page_id), json=meta_data, auth=AUTH)
        if update_meta_response.status_code == 200:
            return #print('Metadata updated successfully')
        else:
            print(f"Failed to update metadata: {update_meta_response.status_code}")
            print(update_meta_response.json())
    else:
        print(f"Failed to create page: {response.status_code}")
        print(response.json())  

def create_posts_concurrently(article, existing_wordpress_posts, barrier_tag, tag_ids):
    if article['barrier'] and article['activity']:
        activity = article['activity']
        tag_id = tag_ids.get(activity)
        
        title = article['title']
        slug = article['slug']
        entry_id = article['entry_id']
        content = article['content']
        create_post(title, slug, entry_id, content, existing_wordpress_posts, tag_id, barrier_tag) 