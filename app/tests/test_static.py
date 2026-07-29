"""Server-side frontend wiring: the real app, but no browser.

The browser-driven tests in test_frontend.py serve frontend/ from a bare
static server, so nothing there proves FastAPI itself hands those files out.
That's what this file is for.
"""

import re

from app import config

FRONTEND_DIR = config.BASE_DIR / "frontend"


def test_frontend_is_served(client):
    index = client.get("/")
    assert index.status_code == 200
    assert "<title>Pronunciation Coach</title>" in index.text

    for path in ("/app.js", "/style.css"):
        asset = client.get(path)
        assert asset.status_code == 200, path


def test_the_frontend_mount_does_not_shadow_the_api(client):
    """The static route is mounted last precisely so /api/* still wins."""
    assert client.get("/api/phrases/categories").status_code == 200


def test_docs_are_served(client):
    # The Dockerfile healthcheck hits /docs; keep it reachable.
    assert client.get("/docs").status_code == 200


def test_index_html_defines_every_element_id_app_js_uses():
    """app.js resolves every element at load; a renamed id blanks the page."""
    app_js = (FRONTEND_DIR / "app.js").read_text()
    index_html = (FRONTEND_DIR / "index.html").read_text()

    element_ids = set(re.findall(r'getElementById\("([^"]+)"\)', app_js))
    assert element_ids, "no getElementById calls found — did app.js change shape?"

    missing = [i for i in sorted(element_ids) if f'id="{i}"' not in index_html]
    assert not missing, f"ids used by app.js but absent from index.html: {missing}"
