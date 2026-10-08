import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://analyst-assessment-production.up.railway.app"
COMMUNITIES_URL = f"{BASE_URL}/communities"

response = requests.get(COMMUNITIES_URL, timeout=30)

print("Status code:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

community_links = []

for link in soup.find_all("a", href=True):
    href = link["href"]

    if href.startswith("/communities/"):
        full_url = urljoin(BASE_URL, href)

        if full_url not in community_links:
            community_links.append(full_url)

print()
print("COMMUNITIES FOUND")
print("=" * 60)

for url in community_links:
    print(url)

print()
print("Total communities:", len(community_links))