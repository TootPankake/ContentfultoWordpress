import requests
import contentful
from openai import OpenAI
from config import SPACE_ID, ACCESS_TOKEN, MANAGEMENT_TOKEN, OPENAI_API_TOKEN

replace_titles = input("Do you want to publish all changes? (y/n): ").strip().upper()
moreQueries = input("Do you want the option to doublecheck the results? (y/n): ").strip().upper()


# Set up your API keys
contentful_space_id = SPACE_ID
contentful_access_token = ACCESS_TOKEN
contentful_management_token = MANAGEMENT_TOKEN
openai_api_key = OPENAI_API_TOKEN

try:
    client = contentful.Client(SPACE_ID, ACCESS_TOKEN,  
                               environment='development',
                               max_include_resolution_depth=1)
    print("Successfully connected to Contentful client.")
except contentful.errors.NotFoundError as e:
    print(f"Error: {e}")

clientAI = OpenAI(api_key=OPENAI_API_TOKEN)
retry = 'N'
# Fetch the most recent article from Contentful
temperature = 0.9
model = 'gpt-4o-mini'
entries = []
articles = client.entries({
    'content_type': "article",
    'order': '-sys.createdAt',  # Order by creation date descending
    'skip': 0, # skip the an arbitrary amount of entries first
    'limit': 100,  # Fetch only the most recent entry
})
entries.extend(articles)

def shorten_title(title, barrier): 
    title = title.replace(":", "")     
    prompt = f"""Shorten the following title: \"{title}\" using its corresponding barrier as its theme: \"{barrier}\".
Updated title must be 50 to 60 characters optimized for SEO, colons are not necessary, only output the updated title, nothing else.
Some example goal titles: No Time? Start Roller Derby with This Beginner's Guide, Conquering the Fear of Unused Roller Skates for Beginners,
Easily Understand Badminton Terms with This Beginner's Guide, Decoding Tae Bo Terms for Beginners Who Feel Lost, Boost Your Confidence and Start Kitesurfing Today, 
Play Pickleball with Confidence Even If You're Self-Conscious, Find Space to Start Stand Up Paddle Boarding Today, Start Zumba Today Even If You Feel Inflexible
""" 
    if title == "<title>" and barrier == "<barrier>":
        with open("PromptTitleTesting.md", 'a') as file:
            file.write("\nPrompt(temperature - " + str(temperature) + ", model - " + model + "):\n" + prompt + "\nResults:")
        print("\nPrompt (temperature - " + str(temperature) + ", model - " + model + "):\n" + prompt + "\nResults:")
        return
    response = clientAI.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "Assistant, providing assistance with shortening titles for SEO as requested."},
            {"role": "user", "content": prompt}
        ]
    )
    shortened_title = response.choices[0].message.content
    return shortened_title

shorten_title("<title>","<barrier>") # show what the prompt is for comparison
for entry in entries:
    title = entry.fields().get('title')
    barriers = entry.fields().get('barriers', [])
    barriers_list = [barrier.fields().get('title') for barrier in barriers]
    barrier = barriers_list[0] if barriers_list else ''
    
    if title:
        shortened_title = shorten_title(title, barrier)
        entry_id = entry.sys['id']
        print(f"""{title} --> \n{shortened_title}""")
        if moreQueries == 'Y':
            retry = input("Adjust (y) or Continue (n): ").strip().upper()
        print("")
        if retry == 'Y':
            list = []
            for i in range(10):
                shortened_title = shorten_title(title, barrier)
                print(str(i+1) + ". " + shortened_title)
                list.append(shortened_title)
            choice = input("Select your favorite of the 10 or enter (C) for custom entry: ").strip().upper()
            if choice == "C": 
                shortened_title = input("Type out custom title: ")
            else: 
                shortened_title = list[int(choice)-1]
            print(f"""\n{title} -->\n{shortened_title}\n\n""")
            with open("PromptTitleTesting.md", 'a') as file:
                file.write(f"""{title} -->\n{shortened_title}\n\n""")
        else: 
            with open("PromptTitleTesting.md", 'a') as file:
                file.write(f"""{title} -->\n{shortened_title}\n\n""")
            
        entry_details_url = f"https://api.contentful.com/spaces/{contentful_space_id}/environments/development/entries/{entry_id}"
        entry_details_headers = {
            'Authorization': f'Bearer {contentful_management_token}',
        }

        entry_details_response = requests.get(entry_details_url, headers=entry_details_headers)
        entry_details = entry_details_response.json()

        version = entry_details['sys']['version']

        # Update only the title field, keeping other fields unchanged
        entry_details['fields']['title']['en-US'] = shortened_title

        # Send the full entry data with only the title modified
        update_url = f"https://api.contentful.com/spaces/{contentful_space_id}/environments/development/entries/{entry_id}"
        update_headers = {
            'Authorization': f'Bearer {contentful_management_token}',
            'Content-Type': 'application/vnd.contentful.management.v1+json',
            'X-Contentful-Version': str(version)
        }
        if replace_titles == 'Y':
            update_response = requests.put(update_url, headers=update_headers, json=entry_details)
            if update_response.status_code == 200:
                print(f"Successfully updated title for entry ID {entry_id}")
                
                # Auto-publish the updated entry
                publish_url = f"https://api.contentful.com/spaces/{contentful_space_id}/environments/development/entries/{entry_id}/published"
                publish_headers = {
                    'Authorization': f'Bearer {contentful_management_token}',
                    'X-Contentful-Version': str(version + 1)  # Increment version for publish request
                }
                
                publish_response = requests.put(publish_url, headers=publish_headers)
                if publish_response.status_code == 200:
                    print(f"Successfully published entry ID {entry_id}")
                else:
                    print(f"Failed to publish entry ID {entry_id}: {publish_response.status_code}, {publish_response.text}")
            else:
                print(f"Failed to update title for entry ID {entry_id}: {update_response.status_code}, {update_response.text}")
    else:
        print("Title not found for the entry.")