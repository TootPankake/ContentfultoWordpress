import requests
import sys
from contentful_management import Client
import contentful
import openai
from config import SPACE_ID, ACCESS_TOKEN, MANAGEMENT_TOKEN, OPENAI_API_TOKEN, ENVIRONMENT
import pandas as pd
import re

replace_titles = 'Y'#input("Do you want to publish all changes? (y/n): ").strip().upper()

# Set up your API keys
contentful_space_id = SPACE_ID
contentful_access_token = ACCESS_TOKEN
contentful_management_token = MANAGEMENT_TOKEN
openai_api_key = OPENAI_API_TOKEN

try:
    client = contentful.Client(SPACE_ID, ACCESS_TOKEN,  
                               environment=ENVIRONMENT,
                               max_include_resolution_depth=1)
    management_client = Client(MANAGEMENT_TOKEN)

    print("Successfully connected to Contentful client.")
except contentful.errors.NotFoundError as e:
    print(f"Error: {e}")

openai.api_key = OPENAI_API_TOKEN

temperature = 0.9
model = 'gpt-4o-mini'
entries = []
skip = 0
limit = 25

while True:  # Fetch articles 
        articles = client.entries({  
            'content_type': 'article',
            'limit': limit,
            'skip': skip,
            'order': '-sys.updatedAt',
            'fields.articleType': 'Activity Barrier Navigator'

        })
        entries.extend(articles)
        skip += limit 
        if len(articles) < limit:
            break 

# Function to generate a slug from a title
def generate_slug(title):
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special characters
    slug = re.sub(r'\s+', '-', slug)      # Replace spaces with hyphens
    slug = re.sub(r'-+', '-', slug)       # Remove multiple hyphens
    return slug.strip('-')

def shorten_title(title, barrier): 
    title = title.replace(":", "")     
    prompt = f"""Shorten the following title: \"{title}\" using its corresponding barrier as its theme: \"{barrier}\".
Updated title must be 50 to 60 characters optimized for SEO, colons are not necessary, only output the updated title, nothing else.
Some example goal titles: No Time? Start Roller Derby with This Beginner's Guide, Conquering the Fear of Unused Roller Skates for Beginners,
Easily Understand Badminton Terms with This Beginner's Guide, Decoding Tae Bo Terms for Beginners Who Feel Lost, Boost Your Confidence and Start Kitesurfing Today, 
Play Pickleball with Confidence Even If You're Self-Conscious, Find Space to Start Stand Up Paddle Boarding Today, Start Zumba Today Even If You Feel Inflexible
""" 
    response = openai.ChatCompletion.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "Assistant, providing assistance with shortening titles for SEO as requested."},
            {"role": "user", "content": prompt}
        ]
    )
    content = response['choices'][0]['message']['content']
    return content

data = []

for entry in entries:
    title = entry.fields().get('title')
    activities = entry.fields().get('activities', [])
    article_type = entry.fields().get('article_type')  # Assuming this field stores 'Activity Barrier Navigator'
    activities_list = [activity.fields().get('title') for activity in activities]
    activity = activities_list[0] if activities_list else ''
    barriers = entry.fields().get('barriers', [])
    barriers_list = [barrier.fields().get('title') for barrier in barriers]
    barrier = barriers_list[0] if barriers_list else ''
    
    if article_type == "Activity Barrier Navigator":
        if title:
            entry_id = entry.sys['id']

                
            entry_details_url = f"https://api.contentful.com/spaces/{contentful_space_id}/environments/{ENVIRONMENT}/entries/{entry_id}"
            entry_details_headers = {
                'Authorization': f'Bearer {contentful_management_token}',
            }

            
            if replace_titles == 'Y':
                entry_details_response = requests.get(entry_details_url, headers=entry_details_headers)
                entry_details = entry_details_response.json()

                version = entry_details['sys']['version']
                
            
                # Send the full entry data with only the title modified
                update_url = f"https://api.contentful.com/spaces/{contentful_space_id}/environments/{ENVIRONMENT}/entries/{entry_id}"
                update_headers = {
                    'Authorization': f'Bearer {contentful_management_token}',
                    'Content-Type': 'application/vnd.contentful.management.v1+json',
                    'X-Contentful-Version': str(version)
                }
                if "lockTitle" not in entry_details['fields']:
                    shortened_title = shorten_title(title, barrier)
                    print(f"""{title} --> \n{shortened_title}""")
                    data.append({"Activity": activity, "Title": title, "Shortened Title": shortened_title})
                    entry_details['fields']['title']['en-US'] = shortened_title
                    entry_details['fields']['lockTitle'] = {}
                    entry_details['fields']['lockTitle']['en-US'] = False  # Initialize to False
                    update_response = requests.put(update_url, headers=update_headers, json=entry_details)
                elif(entry_details['fields']['lockTitle']['en-US'] == True):
                    ### These are for testing
                    new_slug = generate_slug(title)
                    entry_details['fields']['slug'] = {'en-US': new_slug}
                    print(f"Generated slug: {new_slug}")
                    update_response = requests.put(update_url, headers=update_headers, json=entry_details)
                    # print("SKIP")
                    # continue
                else:
                    entry_details['fields']['lockTitle']['en-US'] = True  # Set 'Lock Title' to Locked (True)
                    new_slug = generate_slug(title)
                    entry_details['fields']['slug'] = {'en-US': new_slug}
                    print(f"Generated slug: {new_slug}")
                    shortened_title = shorten_title(title, barrier)
                    print(f"""{title} --> \n{shortened_title}""")
                    data.append({"Activity": activity, "Title": title, "Shortened Title": shortened_title})
                    entry_details['fields']['title']['en-US'] = shortened_title
                    update_response = requests.put(update_url, headers=update_headers, json=entry_details)                   
                

                if update_response.status_code == 200:
                    #print(f"Successfully updated title for entry ID {entry_id}")
                    
                    # Auto-publish the updated entry
                    publish_url = f"https://api.contentful.com/spaces/{contentful_space_id}/environments/{ENVIRONMENT}/entries/{entry_id}/published"
                    publish_headers = {
                        'Authorization': f'Bearer {contentful_management_token}',
                        'X-Contentful-Version': str(version + 1)  # Increment version for publish request
                    }
                    
                    publish_response = requests.put(publish_url, headers=publish_headers)
                    if publish_response.status_code == 200:
                        print(f"PUBLISHED")
                    else:
                        print(f"Failed to publish entry ID {entry_id}: {publish_response.status_code}, {publish_response.text}")
                else:
                    print(f"Failed to update title for entry ID {entry_id}: {update_response.status_code}, {update_response.text}")
        else:
            print("Title not found for the entry.")
df = pd.DataFrame(data)

# # Save to an Excel file
# file_path = "TitleTesting.xlsx"
# #df.to_excel(file_path, index=False, engine='xlsxwriter')
# print(f"Data written to {file_path}")