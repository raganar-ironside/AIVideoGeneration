"""Wikimedia search only: no silent downloads or license approval."""
import os
import re
import html
import requests

def search_commons(query: str, limit: int = 6) -> list[dict]:
    agent = os.environ.get('WIKIMEDIA_USER_AGENT', 'HistoryForgeAI/0.4 (personal research prototype)')
    params = {'action':'query', 'generator':'search', 'gsrsearch':f'filetype:bitmap {query}',
        'gsrnamespace':6, 'gsrlimit':limit, 'prop':'imageinfo',
        'iiprop':'url|extmetadata|mime', 'iiurlwidth':800, 'format':'json'}
    response = requests.get('https://commons.wikimedia.org/w/api.php',params=params,
                            headers={'User-Agent':agent},timeout=20)
    response.raise_for_status()
    results=[]
    for page in response.json().get('query',{}).get('pages',{}).values():
        for info in page.get('imageinfo',[]):
            if info.get('mime') not in {'image/jpeg','image/png','image/webp'}: continue
            metadata=info.get('extmetadata',{})
            def field(name):
                value=metadata.get(name,{}).get('value','')
                return html.unescape(re.sub(r'<[^>]*>','',value)).strip()
            results.append({'title':page.get('title',''), 'preview_url':info.get('thumburl'),
                'file_url':info.get('url'), 'source_url':info.get('descriptionurl'),
                'license':field('LicenseShortName'), 'attribution':field('Artist')})
    return results
