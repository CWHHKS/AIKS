from urllib.parse import urlparse

def normalize_domain(url: str) -> str:
    """
    Extracts and normalizes the root domain from a given URL.
    Example:
        - https://www.example.ai/products -> example.ai
        - http://example.com?query=1 -> example.com
        - example.org -> example.org
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # Ensure scheme is present for proper urlparse behavior
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        
        # Remove 'www.' prefix if it exists
        if netloc.startswith('www.'):
            netloc = netloc[4:]
            
        # Strip port number if present (e.g., example.com:8080 -> example.com)
        netloc = netloc.split(':')[0]
        
        return netloc
    except Exception:
        # Fallback to simple split if urlparse fails
        cleaned = url.replace('https://', '').replace('http://', '').split('/')[0]
        if cleaned.startswith('www.'):
            cleaned = cleaned[4:]
        return cleaned.split(':')[0].lower()
