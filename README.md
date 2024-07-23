# contentful_wp_uploader.py Script

## Description
This script synchronizes content from Contentful to a WordPress site. It fetches entries from Contentful, processes them, and uploads them as pages to a specified WordPress site. 
The script also includes functionality for hyperlinking specific words or phrases within the content based on predefined slugs.

## Setup
pip the following packages
- contentful==2.1.1
- openai==1.35.5
- requests==2.32.3
- rich-text-renderer==0.2.8

### Requirements
- Python 3.x
- Contentful API credentials
- OpenAI API credentials
- WordPress site with REST API enabled
- `config.py` file for configuration settings
