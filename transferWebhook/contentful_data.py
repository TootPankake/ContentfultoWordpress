from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


def fetch_contentful_data(contentful_fetching_limit, skip_categories, skip_activities, client):
    date_threshold_activities = datetime(2024, 1, 1).isoformat()
    date_threshold_categories = datetime(2023, 1, 1).isoformat()

    all_categories, all_activities = [], []

    def fetch_with_backoff(fetch_function, skip, max_retries=5):
        retries = 0
        while retries < max_retries:
            try:
                # Call the fetching function
                return fetch_function(skip)
            except Exception as e:
                retries += 1
                wait_time = min(2 ** retries, 60)  # Exponential backoff with a max wait time of 60 seconds
                print(f"Error fetching data: {e}. Retrying in {wait_time} seconds... (Retry {retries}/{max_retries})")
                time.sleep(wait_time)
        raise Exception("Max retries exceeded")

    def fetch_categories(skip):
        return client.entries({
            'content_type': 'category',
            'limit': contentful_fetching_limit,
            'skip': skip,
            'order': '-sys.createdAt',
            'sys.updatedAt[gte]': date_threshold_categories
        })

    def fetch_activities(skip):
        return client.entries({
            'content_type': 'brim',
            'limit': contentful_fetching_limit,
            'skip': skip,
            'order': '-sys.createdAt',
            'sys.updatedAt[gte]': date_threshold_activities
        })

    with ThreadPoolExecutor(max_workers=4) as executor:
        category_futures = []
        activity_futures = []

        # Launch tasks for categories
        while True:
            future = executor.submit(fetch_with_backoff, fetch_categories, skip_categories)
            category_futures.append(future)
            skip_categories += contentful_fetching_limit
            if len(future.result()) < contentful_fetching_limit:
                break

        # Launch tasks for activities
        while True:
            future = executor.submit(fetch_with_backoff, fetch_activities, skip_activities)
            activity_futures.append(future)
            skip_activities += contentful_fetching_limit
            if len(future.result()) < contentful_fetching_limit:
                break

        # Collect results for categories
        for future in as_completed(category_futures):
            all_categories.extend(future.result())

        # Collect results for activities
        for future in as_completed(activity_futures):
            all_activities.extend(future.result())

    return all_categories, all_activities

def render_activities(all_activities, activity_slugs):
    for entry in all_activities:
        activity_slug = entry.fields().get('slug')
        activity_slugs.append(activity_slug)

    