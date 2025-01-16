import openai
import time
from config import URL, OPENAI_API_TOKEN, MODEL

openai.api_key = OPENAI_API_TOKEN

def call_openai_with_backoff(prompt, max_retries=5, initial_delay=1):
    retries = 0
    delay = initial_delay

    while retries < max_retries:
        try:
            # Make the API call
            response = openai.ChatCompletion.create(
                model=MODEL,
                temperature=0,
                messages=[
                    {'role': 'system', 'content': "Assistant, providing assistance with text processing and link insertion as requested."},
                    {'role': 'user', 'content': prompt}
                ]
            )
            return response  # Return response if successful

        except openai.RateLimitError as e:
            # Handle 429 errors by backing off
            retries += 1
            if retries == max_retries:
                print("Max retries reached. Exiting.")
                raise e
            else:
                print(f"Rate limit hit. Retrying in {delay} seconds...")
                time.sleep(delay)  # Exponential backoff
                delay *= 2  # Double the delay for the next retry

        except Exception as e:
            # Handle other possible exceptions (network errors, etc.)
            print(f"An error occurred: {e}")
            raise e

def generate_article_links(event_title, rendered_content, json_slug_data):
    prompt = f"""
    Slugs: {json_slug_data}
    
    If any words/phrases in the below article match one of the above slugs, then replace its first appearance, no duplicates,
    with a hyperlink with the format \"{URL}<slug>\" Also have the hyperlink visible when the user hovers over it in HTML.
    
    Optimize for html output, only output the updated article, nothing else.
    
    [ARTICLE START]
    {rendered_content} 
    [ARTICLE END]
    """

    response = call_openai_with_backoff(prompt)

    # Extracting the generated content
    content = response['choices'][0]['message']['content']
    content = content.replace('[ARTICLE START]\n', '').replace('\n[ARTICLE END]', '')
    content = content.replace('```html\n', '').replace('\n```', '')
    
    print(f"added links --> {event_title}")
    return content
