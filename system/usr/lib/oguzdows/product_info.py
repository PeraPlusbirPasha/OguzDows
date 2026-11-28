"""Offline product/release identity shared by PC and ARM; never fetches remotely."""
import json
from pathlib import Path
from urllib.parse import urlsplit


def product_info():
    path = Path(__file__).resolve().parents[2] / 'share/oguzdows/product.json'
    data = json.loads(path.read_text())
    for key in ('release_url', 'connection_guide_url', 'apk_url'):
        url = urlsplit(data[key])
        if (url.scheme != 'https' or url.netloc != 'github.com' or url.query or url.fragment
                or not url.path.startswith('/PeraPlusbirPasha/OguzDows/releases/')):
            raise ValueError('Invalid fixed product link')
    return data
