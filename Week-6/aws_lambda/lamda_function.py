import json
import urllib.request
import urllib.error
import gzip
from bs4 import BeautifulSoup
import re

def clean_url(url):
    """Ensure URL has a protocol"""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url

def scrape_website(url, max_size=5*1024*1024): 
    """
    Scrape a website and return plain text content using BeautifulSoup
    
    Args:
        url: The URL to scrape
        max_size: Maximum response size in bytes (default 5MB)
    
    Returns:
        dict: Contains 'success', 'text', and optional 'error'
    """
    try:
        url = clean_url(url)
        
        # Create request with headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; WebScraperBot/1.0)',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        req = urllib.request.Request(url, headers=headers)
        
        # Fetch the page with redirects and timeout
        with urllib.request.urlopen(req, timeout=30) as response:
            # Check content length
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > max_size:
                return {
                    'success': False,
                    'error': f'Page too large: {content_length} bytes (limit: {max_size} bytes)'
                }
            
            # Read response
            content = response.read()
            
            # Check actual size
            if len(content) > max_size:
                return {
                    'success': False,
                    'error': f'Page too large: {len(content)} bytes (limit: {max_size} bytes)'
                }
            
            # Check if response is gzipped
            if response.headers.get('Content-Encoding') == 'gzip':
                content = gzip.decompress(content)
            
            # Decode to text
            html = content.decode('utf-8', errors='ignore')
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script, style, and other non-content tags
            for tag in soup(['script', 'style', 'head', 'meta', 'link', 'noscript', 'iframe']):
                tag.decompose()
            
            # Extract text
            text = soup.get_text(separator=' ', strip=True)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Remove excessive newlines
            text = re.sub(r'\n\s*\n', '\n\n', text)
            
            # Limit output size
            max_output = 50000  # ~50k characters
            if len(text) > max_output:
                text = text[:max_output] + '... [truncated]'
            
            return {
                'success': True,
                'text': text,
                'url': response.geturl(),  # Final URL after redirects
                'title': soup.title.string if soup.title else None
            }
            
    except urllib.error.HTTPError as e:
        return {
            'success': False,
            'error': f'HTTP Error {e.code}: {e.reason}'
        }
    except urllib.error.URLError as e:
        return {
            'success': False,
            'error': f'URL Error: {str(e.reason)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error: {str(e)}'
        }

def lambda_handler(event, context):
    """
    AWS Lambda handler for Bedrock Agent with OpenAPI schema
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        
        api_path = event.get('apiPath', '')
        http_method = event.get('httpMethod', 'POST')
        action_group = event.get('actionGroup', 'WebScraperActionGroup')
        
        
        url = None
        
        
        request_body = event.get('requestBody', {})
        if request_body:
            content = request_body.get('content', {})
            app_json = content.get('application/json', {})
            properties = app_json.get('properties', [])
            for prop in properties:
                if prop.get('name') == 'url':
                    url = prop.get('value')
                    break
        
        
        if not url:
            parameters = event.get('parameters', [])
            for param in parameters:
                if param.get('name') == 'url':
                    url = param.get('value')
                    break
        
        if not url:
            response_body = {
                'success': False,
                'error': 'URL parameter is required'
            }
            http_status = 400
        else:
            response_body = scrape_website(url)
            http_status = 200 if response_body.get('success') else 500
        
        
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': action_group,
                'apiPath': api_path,
                'httpMethod': http_method,
                'httpStatusCode': http_status,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(response_body)
                    }
                }
            }
        }
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'WebScraperActionGroup'),
                'apiPath': event.get('apiPath', '/WebScraperActionGroup/web_scrape'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({
                            'success': False,
                            'error': f'Lambda error: {str(e)}'
                        })
                    }
                }
            }
        }