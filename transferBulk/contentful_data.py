import contentful
from datetime import datetime
from config import SPACE_ID, ACCESS_TOKEN, ENVIRONMENT, RENDERER
from wordpress_operations import create_category

def fetch_contentful_data(contentful_fetching_limit, skip_categories, skip_activities, skip_articles, date_threshold_articles):
    try: # Initialize Contentful API Client
        client = contentful.Client(SPACE_ID, ACCESS_TOKEN, environment=ENVIRONMENT, max_include_resolution_depth=1)
        print("\nFetching contentful client entries")
    except contentful.errors.NotFoundError as e:
        print(f"Error: {e}")
        
    date_threshold_activities = datetime(2024, 1, 1).isoformat()
    date_threshold_categories = datetime(2023, 1, 1).isoformat()

    all_categories, all_activities, all_articles = [], [], []
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
    while True:  # Fetch articles 
        current_batch_of_articles = client.entries({  
            'content_type': 'article',
            'limit': contentful_fetching_limit,
            'skip': skip_articles,
            'order': '-sys.createdAt',
            'sys.updatedAt[gte]': date_threshold_articles,
            'fields.articleType': 'Activity Barrier Navigator'
        })
        all_articles.extend(current_batch_of_articles)
        skip_articles += contentful_fetching_limit 
        if len(current_batch_of_articles) < contentful_fetching_limit:
            break 
    return all_categories, all_activities, all_articles

def render_activities(all_activities):
    activity_slugs = []
    for entry in all_activities:
        slug = entry.fields().get('slug')  
        activity_slugs.append(slug)

    return activity_slugs

def render_articles(all_articles):
    processed_articles = []
    for entry in all_articles:
        entry_fields = entry.fields()
        entry_id = entry.sys.get('id')

        slug = entry_fields.get('slug')  
        title = entry_fields.get('title')
        content = entry_fields.get('content')
        content = RENDERER.render(content)
        
        # activites and barriers are both nested, so they must be looped through
        activities = entry_fields.get('activities', [])
        barriers = entry_fields.get('barriers', [])
        activities_list = [activity.fields().get('title') for activity in activities]
        barriers_list = [barrier.fields().get('title') for barrier in barriers]
        activity = activities_list[0] if activities_list else ''
        barrier = barriers_list[0] if barriers_list else ''

        processed_articles.append({'title': title, 'slug': slug, 'entry_id': entry_id, 'activity': activity, 
                                   'barrier': barrier, 'content': content})
    return processed_articles

def render_categories(all_categories, existing_wordpress_categories):
    all_category_ids = []

    for entry in all_categories:
        category_id = entry.sys.get('id')
        entry_fields = entry.fields()

        category_slug = entry_fields.get('slug')  
        category_title = entry_fields.get('title')
        category_type = entry_fields.get('category_type')
        if category_type == 'Activity':
            id = create_category(category_title, category_slug, category_id, existing_wordpress_categories)
            all_category_ids.append({'id': id, 'meta_data_id': category_id}) 
    
    return all_category_ids