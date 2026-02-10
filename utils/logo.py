"""Logo extraction utilities."""

import requests
import base64
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Optional, Tuple


def extract_logo_url(website_url: str) -> Optional[str]:
    """
    Extract logo URL from a website.

    Tries multiple strategies:
    1. og:image meta tag
    2. Logo in header/nav with 'logo' in class/id/src
    3. SVG logo
    4. Favicon

    Args:
        website_url: The website URL to extract logo from

    Returns:
        Logo URL if found, None otherwise
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(website_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'lxml')
        base_url = website_url.rstrip('/')

        # Strategy 1: og:image meta tag
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return urljoin(base_url, og_image['content'])

        # Strategy 2: Find img tags with 'logo' in attributes
        logo_patterns = [
            soup.find_all('img', class_=re.compile(r'logo', re.I)),
            soup.find_all('img', id=re.compile(r'logo', re.I)),
            soup.find_all('img', src=re.compile(r'logo', re.I)),
            soup.find_all('img', alt=re.compile(r'logo', re.I)),
        ]

        for imgs in logo_patterns:
            for img in imgs:
                src = img.get('src')
                if src:
                    return urljoin(base_url, src)

        # Strategy 3: Look in header/nav for any image
        header = soup.find(['header', 'nav'])
        if header:
            img = header.find('img')
            if img and img.get('src'):
                return urljoin(base_url, img['src'])

        # Strategy 4: SVG logo
        svg_logo = soup.find('svg', class_=re.compile(r'logo', re.I))
        if svg_logo:
            # Can't easily extract SVG as URL, skip
            pass

        # Strategy 5: Favicon
        favicon_links = [
            soup.find('link', rel='icon'),
            soup.find('link', rel='shortcut icon'),
            soup.find('link', rel='apple-touch-icon'),
        ]

        for link in favicon_links:
            if link and link.get('href'):
                return urljoin(base_url, link['href'])

        # Strategy 6: Default favicon location
        return f"{base_url}/favicon.ico"

    except Exception as e:
        print(f"  Error extracting logo from {website_url}: {e}")
        return None


def download_logo(logo_url: str, output_dir: str, filename: str) -> Optional[str]:
    """
    Download a logo image and save it locally.

    Args:
        logo_url: URL of the logo
        output_dir: Directory to save the logo
        filename: Base filename (without extension)

    Returns:
        Path to saved file, or None if failed
    """
    if not logo_url:
        return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(logo_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        # Determine extension from content-type or URL
        content_type = response.headers.get('content-type', '')
        if 'svg' in content_type or logo_url.endswith('.svg'):
            ext = '.svg'
        elif 'png' in content_type or logo_url.endswith('.png'):
            ext = '.png'
        elif 'webp' in content_type or logo_url.endswith('.webp'):
            ext = '.webp'
        elif 'ico' in content_type or logo_url.endswith('.ico'):
            ext = '.ico'
        else:
            ext = '.png'  # Default

        output_path = Path(output_dir) / f"{filename}{ext}"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'wb') as f:
            f.write(response.content)

        return str(output_path)

    except Exception as e:
        print(f"  Error downloading logo from {logo_url}: {e}")
        return None


def get_logo_as_base64(logo_url: str) -> Optional[Tuple[str, str]]:
    """
    Download logo and return as base64 data URI.

    Args:
        logo_url: URL of the logo

    Returns:
        Tuple of (base64_data_uri, mime_type) or None if failed
    """
    if not logo_url:
        return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(logo_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        content_type = response.headers.get('content-type', 'image/png')
        if 'svg' in logo_url:
            content_type = 'image/svg+xml'
        elif 'webp' in logo_url:
            content_type = 'image/webp'
        elif 'ico' in logo_url:
            content_type = 'image/x-icon'

        b64 = base64.b64encode(response.content).decode('utf-8')
        data_uri = f"data:{content_type};base64,{b64}"

        return (data_uri, content_type)

    except Exception as e:
        print(f"  Error getting logo as base64 from {logo_url}: {e}")
        return None

def get_local_logo_as_base64(file_path: Path) -> Optional[Tuple[str, str]]:
    """
    Load a local image file and return as base64 data URI.
    
    Args:
        file_path: Path to the local image file
        
    Returns:
        Tuple of (base64_data_uri, mime_type) or None if failed
    """
    try:
        if not file_path.exists():
            return None
            
        mime_type = 'image/png'
        if file_path.suffix.lower() == '.svg':
            mime_type = 'image/svg+xml'
        elif file_path.suffix.lower() == '.jpg' or file_path.suffix.lower() == '.jpeg':
            mime_type = 'image/jpeg'
        elif file_path.suffix.lower() == '.webp':
            mime_type = 'image/webp'
            
        with open(file_path, "rb") as image_file:
            b64 = base64.b64encode(image_file.read()).decode('utf-8')
            return (f"data:{mime_type};base64,{b64}", mime_type)
            
    except Exception as e:
        print(f"  Error loading local logo from {file_path}: {e}")
        return None
