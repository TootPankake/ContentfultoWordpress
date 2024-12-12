from wordpress_operations import create_category

def fetch_contentful_data(limit, skip1, skip2, skip3, date_threshold, date_threshold_articles, date_threshold_categories, client):
    all_categories, all_activities, all_articles = [], [], []
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
        #limit = 5
        articles = client.entries({  
            'content_type': 'article',
            'limit': limit,
            'skip': skip3,
            'order': '-sys.createdAt',
            'sys.updatedAt[gte]': date_threshold_articles,
            'fields.articleType': 'Activity Barrier Navigator'

        })
        all_articles.extend(articles)
        skip3 += limit 
        if len(articles) < limit:# or skip3 >= 5:  # Break the loop if no more articles are fetched
            break 
    return all_categories, all_activities, all_articles

def render_articles(all_articles, renderer, article_data):
    for entry in all_articles:
        article_slug = entry.fields().get('slug')  
        article_title = entry.fields().get('title')
        article_description = entry.fields().get('content')
        article_id = entry.sys.get('id')
        
        if article_description:
            try:
                rendered_description = renderer.render(article_description)
            except Exception as e:
                rendered_description = str(e)
        else:
            rendered_description = None
            
        if article_id and article_slug and article_title and rendered_description:
            article_data.append({
                'id': article_id,
                'slug': article_slug,
                'title': article_title,
                'description': rendered_description
            })
def render_activities(all_activities, renderer, activity_data, activity_slugs):
    for entry in all_activities:
        activity_slug = entry.fields().get('slug')  
        activity_title = entry.fields().get('title')
        activity_description = entry.fields().get('description_full')
        activity_id = entry.sys.get('id')
        activity_slugs.append(activity_slug)
        if activity_description:
            try:
                rendered_description = renderer.render(activity_description)
            except Exception as e:
                rendered_description = str(e)
        else:
            rendered_description = None
            
        if activity_id and activity_slug and activity_title and rendered_description:
            activity_data.append({
                'id': activity_id,
                'slug': activity_slug,
                'title': activity_title,
                'description': rendered_description,
            })
def render_categories(all_categories, all_category_ids, existing_category_metadata):
    for entry in all_categories:
        category_slug = entry.fields().get('slug')  
        category_title = entry.fields().get('title')
        category_description = entry.fields().get('description') # change to whatever we choose as the name for description
        category_description = ""
        category_type = entry.fields().get('category_type')
        category_id = entry.sys.get('id')
        if category_type == 'Activity':
            id = create_category(category_title, category_description, category_slug, category_id, existing_category_metadata)
            all_category_ids.append({'id': id, 'meta_data_id': category_id}) 