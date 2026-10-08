import requests
from bs4 import BeautifulSoup

URL = "https://analyst-assessment-production.up.railway.app/communities/bellhaven-of-maplewood"

response = requests.get(URL, timeout=30)

print("Status code:", response.status_code)
print("Page size:", len(response.text), "characters")

soup = BeautifulSoup(response.text, "html.parser")

print("\nPAGE TITLE")
print("=" * 60)

print(soup.title.get_text(" ", strip=True) if soup.title else "No title")

print("\nHEADINGS")
print("=" * 60)

for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
    text = heading.get_text(" ", strip=True)
    if text:
        print(text)

print("\nPAGE TEXT")
print("=" * 60)

print(soup.get_text("\n", strip=True))