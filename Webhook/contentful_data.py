from wordpress_operations import create_category
from datetime import datetime

def fetch_contentful_data(contentful_fetching_limit, skip_categories, skip_activities, client):
    date_threshold_activities = datetime(2024, 1, 1).isoformat()
    date_threshold_categories = datetime(2023, 1, 1).isoformat()
    all_categories, all_activities = [], []
    while True: # Fetch categories
        current_batch_of_categories = client.entries({
            'content_type': 'category',
            'limit': contentful_fetching_limit,
            'skip': skip_categories,
            'order': '-sys.createdAt',
            'sys.updatedAt[gte]': date_threshold_categories
        })
        all_categories.extend(current_batch_of_categories)
        skip_categories += contentful_fetching_limit 
        if len(current_batch_of_categories) < contentful_fetching_limit: 
            break
    while True:  # Fetch activities 
        current_batch_of_activities = client.entries({
            'content_type': 'brim',
            'limit': contentful_fetching_limit,
            'skip': skip_activities,
            'order': '-sys.createdAt',
            'sys.updatedAt[gte]': date_threshold_activities 
        })
        all_activities.extend(current_batch_of_activities)
        skip_activities += contentful_fetching_limit 
        if len(current_batch_of_activities) < contentful_fetching_limit: 
            break
    return all_categories, all_activities

def render_activities(all_activities, activity_slugs):
    for entry in all_activities:
        activity_slug = entry.fields().get('slug')  
        activity_slugs.append(activity_slug)
        
def render_categories(all_categories, existing_wordpress_categories):
    for entry in all_categories:
        category_title = entry.fields().get('title')
        category_description = entry.fields().get('description') # change to whatever we choose as the name for description
        category_description = "" # for now it's empty
        category_slug = entry.fields().get('slug')  
        category_contentful_entry_id = entry.sys.get('id')
        
        category_type = entry.fields().get('category_type')
        #if category_type == 'Activity':
            #id_number = create_category(category_title, category_description, category_slug, category_contentful_entry_id, existing_wordpress_categories)
            #all_category_ids.append({'id_number': id_number, 'contentful_entry_id': category_contentful_entry_id}) 