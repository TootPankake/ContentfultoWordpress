# Contentful Keys
SPACE_ID = ''
ACCESS_TOKEN = ''
PREVIEW_API_ACCESS_TOKEN = ''

# Wordpress Certification
USERNAME = ''
PASSWORD = ''

# Open AI key
OPENAI_API_TOKEN = ''
#python3 -m venv env
#source env/bin/activate

### OLD SCRIPTS
#json files
'''file_path = '/Users/emregumus/Downloads/titles.json' # whichever filepath you prefer
with open(file_path, 'w') as f:
    json.dump(titles,f)

file_path = '/Users/emregumus/Downloads/slugs.json' # whichever filepath you prefer
with open(file_path, 'w') as f:
    json.dump(slugs,f)


file_path = '/Users/emregumus/Downloads/urls.json' # whichever filepath you prefer
with open(file_path, 'w') as f:
    json.dump(urls,f)'''
#Fetch content types matching the specified name, lists id's of development environment
'''content_types = client.content_types()
for content_type in content_types:
    print(f"Content Type ID: {content_type.id}")'''
#Function to replace slugs with hyperlinks
'''def add_hyperlinks_to_article(article, slugs, base_url):
    for slug in slugs:
        # Create the hyperlink
        hyperlink = f'<a href="{base_url}{slug}">{slug}</a>'
        # Use a case-insensitive replacement
        article = re.sub(f'\\b{slug}\\b', hyperlink, article, flags=re.IGNORECASE)
    return article'''
#Testing entry and slug counts
'''print("Entry count: " + str(entry_count))
   print("Entries w/ slugs: " + str(len(titles)))'''
#Fetch data from wordpress
'''if response.status_code == 200:
    posts = response.json()['posts']
    for post in posts:
        print(f"Title: {post['title']}")
        print(f"Content: {post['content']}")
        print("\n")
else:
    print(f"Failed to fetch posts. Status code: {response.status_code}")'''
#Auth code retrieval
# https://public-api.wordpress.com/oauth2/authorize?client_id=102439&redirect_uri=https://maesterlinks.wordpress.com&response_type=code&scope=global
'''token_url = 'https://public-api.wordpress.com/oauth2/token'
data = {
    'client_id': 102439,
    'redirect_uri': 'https://maesterlinks.wordpress.com',
    'client_secret': WP_ACCESS_TOKEN,
    'code': 'dFoFFGgAOI',
    'grant_type': 'authorization_code'
}

response = requests.post(token_url, data=data)
if response.status_code == 200:
    access_token = response.json()['access_token']
    print(f"Access Token: {access_token}")
else:
    print(f"Failed to obtain access token: {response.status_code}")
    print(response.json())'''
#Save to downloads
'''filename = f'/Users/emregumus/Downloads/article{iteration}.html' #filenames from article1.md to article 10.md     
with open(filename, 'w') as f:
    f.write(ai_updated_article)
f.close()'''
#Fast delete all posts
'''def fetch_all_posts():
    posts = []
    page = 1
    while True:
        response = requests.get(posts_url, headers=headers, params={'number': 100, 'page': page})
        if response.status_code != 200:
            print(f"Failed to fetch posts. Status code: {response.status_code}")
            break
        data = response.json()
        if not data['posts']:
            break
        posts.extend(data['posts'])
        page += 1
    return posts

def delete_post(post_id):
    delete_url = f'{posts_url}/{post_id}/delete'
    response = requests.post(delete_url, headers=headers)
    if response.status_code == 200:
        print(f"Post {post_id} deleted successfully.")
    else:
        print(f"Failed to delete post {post_id}. Status code: {response.status_code}")
        print(response.json())

def delete_all_posts():
    all_posts = fetch_all_posts()
        
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(delete_post, post['ID']) for post in all_posts]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print(f"Exception occurred while deleting post: {exc}")

# Call the function to delete all posts
delete_all_posts()'''
#Fast delete all pages
'''def fetch_all_pages():
    pages = []
    page = 1
    while True:
        response = requests.get(api_url, auth=auth, params={'per_page': 100, 'page': page})
        if response.status_code != 200:
            print(f"Failed to fetch pages. Status code: {response.status_code}")
            break
        data = response.json()
        if not data:
            break
        pages.extend(data)
        page += 1
    return pages

def delete_page(page_id):
    delete_url = f'{api_url}/{page_id}'
    response = requests.delete(delete_url, auth=auth)
    if response.status_code == 200:
        print(f"Page {page_id} deleted successfully.")
    else:
        print(f"Failed to delete page {page_id}. Status code: {response.status_code}")
        print(response.json())

def delete_all_pages():
    all_pages = fetch_all_pages()
        
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(delete_page, page['id']) for page in all_pages]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print(f"Exception occurred while deleting page: {exc}")

# Call the function to delete all pages
delete_all_pages()'''
#Check all WP posts titles for html bugs
'''def fetch_all_posts():
    posts = []
    page = 1
    while True:
        response = requests.get(posts_url, headers=headers, params={'number': 100, 'page': page})
        if response.status_code != 200:
            print(f"Failed to fetch posts. Status code: {response.status_code}")
            break
        data = response.json()
        if not data['posts']:
            break
        posts.extend(data['posts'])
        page += 1
    return posts
def extract_titles(posts):
    #print([post['title'] for post in posts])
    return [post['title'] for post in posts]
def save_titles_to_json(titles, file_path):
    with open(file_path, 'w') as f:
        json.dump(titles, f)
    print(f"Titles saved to {file_path}")
    
all_posts = fetch_all_posts()
all_titles = extract_titles(all_posts)
file_path = '/Users/emregumus/Downloads/titlesWP.json' # 
save_titles_to_json(all_titles, file_path)'''
#List all slugs
'''print("List of all pages:")
for page in pages:
    print(f"ID: {page['id']}, Title: {page['title']['rendered']}, Slug: {page['slug']}")'''