# contentful_wp_uploader.py Script

## Description
This script synchronizes content from Contentful to a WordPress site. It fetches entries from Contentful, processes them, and uploads them as pages to a specified WordPress site. The script also includes functionality for hyperlinking specific words or phrases within the content based on predefined slugs. The lambda function has 4 event variables:
 - "refreshArtices": determines whether every single contentful article is processed, or just the ones from the last cycle
 - "gptSweep": whether AI hyperlinks are applied to article descriptions, can be costly at high quantities
 - "maxArticles": limiting number of articles processed for lambda API invocation errors
 - "segment": signifies where how many contentful articles are skipped to get to a certain portion 
        -example: articles 0-200, segment = 0; articles 201-400, segment = 200; articles 401-600, segment = 400, and so on

## Setup
pip the following packages
- contentful==2.2.0
- openai==0.28
- requests==2.32.3
- rich-text-renderer==0.2.8
- pymongo==4.8.0
- certifi==2024.7.4


### Requirements
- Python 3.12
- Contentful API credentials
- OpenAI API credentials
- WordPress site with REST API enabled
- `config.py` file for configuration settings
