from wordpress_operations import create_category

def fetch_contentful_data(contentful_fetching_limit, skip_categories, skip_activities, skip_articles, 
                          client, date_threshold_activities, date_threshold_articles, date_threshold_categories):
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

def render_activities(all_activities, activity_slugs):
    for entry in all_activities:
        activity_slug = entry.fields().get('slug')  
        activity_slugs.append(activity_slug)
        
