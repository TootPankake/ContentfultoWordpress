import requests
from config import URL, AUTH
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_all_pages(existing_pages):

    def fetch_page_concurrently(page_number):
        response = requests.get(f"{URL}wp-json/wp/v2/pages", params={'per_page': 100, 'page': page_number}, auth=AUTH, timeout = 10)
        return response.json() if response.status_code == 200 else []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_page_concurrently, i) for i in range(1, 10)] 
        for future in as_completed(futures):
            existing_pages.extend(future.result())

def fetch_page_metadata_id(existing_pages, existing_metadata):
    def fetch_metadata_concurrently(page):
        page_id = page['id']
        meta_response = requests.get(f'{URL}/wp-json/wp/v2/pages/{page_id}', auth=AUTH, timeout = 10)
        if meta_response.status_code == 200:
            meta_data = meta_response.json().get('meta', {})
            metadata_id = meta_data.get('_metadata_id', None)
            if metadata_id:
                return {'id': page_id, 'metadata_id': metadata_id}
        return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_metadata_concurrently, page) for page in existing_pages]
        for future in as_completed(futures):
            result = future.result()
            if result:
                existing_metadata.append(result)

def fetch_category_metadata_id(existing_category_metadata):
    page = 1
    while True:
        response = requests.get(f"{URL}/wp-json/wp/v2/categories", params={'per_page': 20, 'page': page}, auth=AUTH)
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
    
def create_parent_page(title, description, slug, metadata_id, category_ids, existing_metadata):
    for item in existing_metadata:
        if metadata_id == item['metadata_id']:
            #print(f"{metadata_id} found")
            page_id = item['id']

            # Update the page content
            page_data = {
                'title': title,
                'content': description,
                'slug': slug,
                'categories': category_ids
            }
            response = requests.post(f"{URL}wp-json/wp/v2/pages/{page_id}".format(page_id=page_id), json=page_data, auth=AUTH)
            if response.status_code in [200,201]:
                print(f"updated --> {title}")
                return page_id
            else:
                print(f"Failed to update page: {response.status_code}")
                print(title)
                print(response.json())  # Print the response for debugging
            return 
    
    # If no matching metadata ID found, create a new page
    page_data = {
        'title': title,
        'content': description,
        'categories': category_ids,
        'slug': slug,
        'status': 'publish'
    }

    response = requests.post(f"{URL}wp-json/wp/v2/pages", json=page_data, auth=AUTH)

    if response.status_code == 201:
        print(f"created --> {title}")
        page_id = response.json()['id']

        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': metadata_id
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

def create_child_page(article, parent_id, existing_metadata, gptSweep):
    article_title = article['title']
    article_description = article['content']
    metadata_id = article['id']
    
    if not article_description:
        print(f"Warning: Article '{article_title}' has empty content.")
        return

    for item in existing_metadata:
        if metadata_id == item['metadata_id']:
            #print(f"{metadata_id} found")
            page_id = item['id']
            
            if gptSweep != 'Y':
                url = f"{URL}wp-json/wp/v2/pages/{page_id}"
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
                'parent': parent_id
            }
            found = True
            response = requests.post(f"{URL}wp-json/wp/v2/pages/{page_id}".format(page_id=page_id), json=page_data, auth=AUTH)
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
        'status': 'publish',
        'parent': parent_id
    }

    response = requests.post(f"{URL}wp-json/wp/v2/pages", json=page_data, auth=AUTH)

    # Check if the page creation was successful
    if response.status_code == 201:
        print(f'created --> {article_title}')
        page_id = response.json()['id']

        # Update the metadata
        meta_data = {
            'meta': {
                '_metadata_id': metadata_id  # Your metadata ID value
            }
        }

        update_meta_response = requests.post(f"{URL}wp-json/wp/v2/pages/{page_id}".format(page_id=page_id), json=meta_data, auth=AUTH)
        if update_meta_response.status_code == 200:
            return #print('Metadata updated successfully')
        else:
            print(f"Failed to update metadata: {update_meta_response.status_code}")
            print(update_meta_response.json())
    else:
        print(f"Failed to create page: {response.status_code}")
        print(response.json()) 

def create_child_page_concurrently(article, existing_metadata, parent_page_ids, gptSweep):
    if article['has_activities_and_barriers']:
        activity = article['activity']
        parent_id = parent_page_ids.get(activity)  # Get the parent page ID
    create_child_page(article, parent_id, existing_metadata, gptSweep)   
