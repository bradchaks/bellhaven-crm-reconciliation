import requests
from bs4 import BeautifulSoup

URL = "https://analyst-assessment-production.up.railway.app"

response = requests.get(URL, timeout=30)

print("Status code:", response.status_code)
print("Page size:", len(response.text), "characters")

soup = BeautifulSoup(response.text, "html.parser")

if soup.title:
    print("Page title:", soup.title.get_text(strip=True))
else:
    print("Page title: None")

print("\nLINKS FOUND")
print("=" * 60)

for link in soup.find_all("a", href=True):
    text = link.get_text(" ", strip=True)
    href = link["href"]

    if text:
        print(f"{text} -> {href}")