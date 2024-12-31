import requests
import time
from config import URL, AUTH
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_all_pages_and_posts(existing_wordpress_pages, existing_wordpress_posts):
    # Helper function to fetch pages
    def fetch_page_concurrently(page_number):
        response = requests.get(
            f"{URL}wp-json/wp/v2/pages",
            params={'per_page': 100, 'page': page_number},
            auth=AUTH,
            timeout=30
        )
        return response.json() if response.status_code == 200 else []

    # Helper function to fetch posts
    def fetch_post_concurrently(page_number):
        response = requests.get(
            f"{URL}wp-json/wp/v2/posts",
            params={'per_page': 100, 'page': page_number},
            auth=AUTH,
            timeout=30
        )
        if response.status_code == 200:
            return response.json(), int(response.headers.get('X-WP-TotalPages', 1))
        return [], 1

    # Fetch the first page of posts to determine total pages
    first_response = requests.get(
        f"{URL}wp-json/wp/v2/posts",
        params={'per_page': 100, 'page': 1},
        auth=AUTH,
        timeout=30
    )

    if first_response.status_code != 200:
        print("Failed to fetch posts.")
        return

    # Parse initial response and total pages
    first_page_posts = first_response.json()
    total_pages = int(first_response.headers.get('X-WP-TotalPages', 1))
    existing_wordpress_posts.extend(first_page_posts)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(fetch_post_concurrently, i)
            for i in range(2, total_pages + 1)
        ]
        for future in as_completed(futures):
            posts, _ = future.result()
            existing_wordpress_posts.extend(posts)

    # Repeat similar process for pages
    first_response_pages = requests.get(
        f"{URL}wp-json/wp/v2/pages",
        params={'per_page': 100, 'page': 1},
        auth=AUTH,
        timeout=30
    )

    if first_response_pages.status_code != 200:
        print("Failed to fetch pages.")
        return

    first_page_pages = first_response_pages.json()
    total_pages_pages = int(first_response_pages.headers.get('X-WP-TotalPages', 1))
    existing_wordpress_pages.extend(first_page_pages)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(fetch_page_concurrently, i)
            for i in range(2, total_pages_pages + 1)
        ]
        for future in as_completed(futures):
            pages = future.result()
            existing_wordpress_pages.extend(pages)

def fetch_page_and_post_metadata_id(existing_wordpress_pages, existing_wordpress_posts, existing_page_metadata, existing_post_metadata):
    def fetch_with_retries(url, retries=3, delay=2):
        for attempt in range(retries):
            try:
                response = requests.get(url, auth=AUTH, timeout=30)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to fetch {url} - Status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Error fetching {url}: {e}")
            time.sleep(delay)  # Retry after a delay
        return None  # Return None if all retries fail

    def fetch_page_concurrently(page):
        page_id = page['id']
        url = f'{URL}/wp-json/wp/v2/pages/{page_id}'
        meta_response = fetch_with_retries(url)
        if meta_response:
            meta_data = meta_response.get('meta', {})
            metadata_id = meta_data.get('_metadata_id', None)
            metadata_title = meta_data.get('title', None)
            metadata_content = meta_data.get('content', None)
            metadata_locked = meta_data.get('_lock_title', None)
            if metadata_id:
                return {'content': metadata_content, 'title': metadata_title, 'id': page_id, 'metadata_id': metadata_id, 'locked': metadata_locked}
        return None

    def fetch_post_concurrently(post):
        post_id = post['id']
        url = f'{URL}/wp-json/wp/v2/posts/{post_id}'
        meta_response = fetch_with_retries(url)
        if meta_response:
            meta_data = meta_response.get('meta', {})
            metadata_id = meta_data.get('_metadata_id', None)
            metadata_title = meta_data.get('title', None)
            metadata_content = meta_data.get('content', None)
            metadata_locked = meta_data.get('_lock_title', None)
            if metadata_id:
                return {'content': metadata_content, 'title': metadata_title, 'id': post_id, 'metadata_id': metadata_id, 'locked': metadata_locked}
        return None


    for batch in range(0, len(existing_wordpress_pages), 50):  # Process 50 pages at a time
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(fetch_page_concurrently, page)
                for page in existing_wordpress_pages[batch:batch + 50]
            ]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    existing_page_metadata.append(result)
    time.sleep(5)  # Pause between batches
    for batch in range(0, len(existing_wordpress_posts), 50):  # Process 50 pages at a time
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(fetch_post_concurrently, page)
                for page in existing_wordpress_posts[batch:batch + 50]
            ]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    existing_post_metadata.append(result)
        time.sleep(5)  # Pause between batches

def fetch_all_tags_and_categories(existing_tag_metadata, existing_category_metadata):
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
        
        page += 1  # Increment the page number for pagination
    page = 1
    while True:
        response = requests.get(f"{URL}/wp-json/wp/v2/categories", params={'per_page': 20, 'page': page}, auth=AUTH, timeout = 30)
        categories = response.json()
        
        if not categories:
            break

        for category in categories:
            if 'metadata_id' in category:
                existing_category_metadata.append({'id': category['id'], 'metadata_id': category['metadata_id']})
            else:
                print(f"Category ID: {category['id']} has no Metadata ID.")
        
        page += 1  # Pagination required to obtain more than 10 entries from WP
        
def create_category(title, description, slug, metadata_id, existing_category_metadata):
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

def create_page_and_tag(title, description_full, activity_slug, image_url, activity_id, category_list, existing_page_metadata, existing_tag_metadata):
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_parent_page = executor.submit(
            create_page, title, description_full, activity_slug, image_url, activity_id, category_list, existing_page_metadata
        )
        future_tag = executor.submit(
            create_tag, title, activity_slug, activity_id, existing_tag_metadata
        )
        # Wait for both tasks to complete
        parent_page_id = future_parent_page.result()
        tag_id = future_tag.result()
    return parent_page_id, tag_id

def create_tag(title, slug, metadata_id, existing_tag_metadata):
    for item in existing_tag_metadata:
        if metadata_id == item['description']:
            tag_id = item['id']
            tag_data = {
                'name': title,
                'slug': slug,
                'description': metadata_id,
            }
            response = requests.put(f"{URL}/wp-json/wp/v2/tags/{tag_id}", json=tag_data, auth=AUTH)
            if response.status_code in [200, 201]:
                print(f"Updated --> {title}")
                return tag_id
            else:
                print(f"Failed to update {title}: {response.status_code}")
                print(response.json())
            return

    # If the tag does not exist, create a new one
    tag_data = {
        'name': title,
        'slug': slug,
        'description': metadata_id,
    }
    response = requests.post(f"{URL}/wp-json/wp/v2/tags", json=tag_data, auth=AUTH)
    if response.status_code == 201:
        tag_id = response.json().get('id')
        print(f"Created --> {title}")
        return tag_id
    else:
        print(f"Failed to create {title}: {response.status_code}")
        print(response.json())
    return

def create_page(title, description, slug, image_url, metadata_id, category_ids, existing_page_metadata):
    for item in existing_page_metadata:
        if metadata_id == item['metadata_id']:
            page_id = item['id']
            
            if (item['content'] != description or item['categories'] != category_ids):
                # Update the page content
                page_data = {
                    'title': title,
                    'content': description,
                    'slug': slug,
                    'categories': category_ids,
                }
                response = requests.post(f"{URL}wp-json/wp/v2/pages/{page_id}".format(page_id=page_id), json=page_data, auth=AUTH)
                if response.status_code in [200,201]:
                    print(f"updated --> {title}")
                    set_fifu_image(page_id, image_url)
                    return page_id
                else:
                    print(f"Failed to update page: {response.status_code}")
                    print(title)
                    print(response.json())  # Print the response for debugging
                return 
            return page_id
    
    # If no matching metadata ID found, create a new page
    page_data = {
        'title': title,
        'content': description,
        'categories': category_ids,
        'slug': slug,
        'status': 'publish',
    }

    response = requests.post(f"{URL}wp-json/wp/v2/pages", json=page_data, auth=AUTH)

    if response.status_code == 201:
        print(f"created --> {title}")
        page_id = response.json()['id']
        set_fifu_image(page_id, image_url)
        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': metadata_id,
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

def create_child_page(article, existing_post_metadata, barrier_tag, tag_id, gptSweep):
    article_title = article['title']
    article_description = article['content']
    article_slug = article['slug']
    metadata_id = article['id']
    
    if not article_description:
        print(f"Warning: Article '{article_title}' has empty content.")
        return

    for item in existing_post_metadata:
        if metadata_id == item['metadata_id']:
            if item['locked'] == "1":
                response = requests.get(f"{URL}/wp-json/wp/v2/posts/{item['id']}")
                article_title = response.json()
                article_title = article_title['title']['rendered']
            page_id = item['id']
        
            if gptSweep != 'Y':
                url = f"{URL}wp-json/wp/v2/posts/{page_id}"
                response = requests.get(url, auth=AUTH)
                if response.status_code == 200:
                    page_data = response.json()
                    article_description = page_data.get('content', [])
                else:
                    print(f"Failed to retrieve page data for page ID {page_id}. Status code: {response.status_code}")

            # Update the page content
            page_data = {
                'title': article_title,
                'content': article_description,
                'slug': article_slug,
                'tags': [tag_id, barrier_tag],
            }
            response = requests.post(f"{URL}wp-json/wp/v2/posts/{page_id}".format(page_id=page_id), json=page_data, auth=AUTH)
            if response.status_code == 200:
                print(f"updated --> {article_title}")
            else:
                print(f"Failed to update page: {response.status_code}")
                print(article_title)
                print(response.json())
            return
        
    # If no matching metadata ID found, create a new page
    page_data = {
        'title': article_title,
        'content': article_description,
        'slug': article_slug,
        'status': 'publish',
        'tags': [tag_id, barrier_tag],
    }

    response = requests.post(f"{URL}wp-json/wp/v2/posts", json=page_data, auth=AUTH)

    # Check if the page creation was successful
    if response.status_code == 201:
        print(f'created --> {article_title}')
        page_id = response.json()['id']
        meta_data = {
            'meta': {
                '_metadata_id': metadata_id,
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

def create_child_page_concurrently(article, existing_page_metadata, barrier_tag, tag_ids, gptSweep):
    if article['has_activities_and_barriers']:
        activity = article['activity']
        #parent_id = parent_page_ids.get(activity)  # Get the parent page ID
        tag_id = tag_ids.get(activity)
    create_child_page(article, existing_page_metadata, barrier_tag, tag_id, gptSweep)   

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