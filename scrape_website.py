import json
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


BASE_URL = "https://analyst-assessment-production.up.railway.app"
COMMUNITIES_URL = f"{BASE_URL}/communities"


def get_community_urls():
    """
    Discover community pages from both:
    1. The main homepage
    2. The /communities directory

    This prevents us from missing a community that is linked
    directly from the homepage but not listed in the directory.
    """

    urls = []

    pages_to_check = [
        BASE_URL,
        COMMUNITIES_URL
    ]

    for page_url in pages_to_check:
        print(f"Checking for community links: {page_url}")

        response = requests.get(page_url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()

            if href.startswith("/communities/"):
                url = urljoin(BASE_URL, href)

                if url not in urls:
                    urls.append(url)

    return urls


def scrape_community(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # ---------------------------------------------------------
    # Community name
    # ---------------------------------------------------------

    heading = soup.find("h1")

    if not heading:
        raise ValueError("Could not find community name")

    name = heading.get_text(" ", strip=True)

    # ---------------------------------------------------------
    # Get clean page text
    # ---------------------------------------------------------

    lines = [
        line.strip()
        for line in soup.get_text("\n").splitlines()
        if line.strip()
    ]

    # ---------------------------------------------------------
    # Find address
    # ---------------------------------------------------------

    try:
        address_index = lines.index("Address")

        address_line_1 = lines[address_index + 1]
        address_line_2 = lines[address_index + 2]

    except (ValueError, IndexError):
        raise ValueError("Could not find address")

    # ---------------------------------------------------------
    # Parse city, state and ZIP
    # ---------------------------------------------------------

    address_match = re.match(
        r"^(.*?)\s+([A-Z]{2})\s+(\d{5})$",
        address_line_2
    )

    if not address_match:
        raise ValueError(
            f"Could not parse city/state/ZIP: {address_line_2}"
        )

    city = address_match.group(1).rstrip(",").strip()
    state = address_match.group(2).strip()
    zip_code = address_match.group(3).strip()

    # ---------------------------------------------------------
    # Find care offerings
    # ---------------------------------------------------------

    try:
        care_index = lines.index("Care Offerings")
        administrator_index = lines.index("Administrator")

        care_offerings = lines[
            care_index + 1:administrator_index
        ]

    except (ValueError, IndexError):
        raise ValueError("Could not find care offerings")

    # ---------------------------------------------------------
    # Return structured location
    # ---------------------------------------------------------

    return {
        "name": name,
        "address": address_line_1,
        "city": city,
        "state": state,
        "zip": zip_code,
        "care_offerings": care_offerings,
        "website_url": url
    }


# =============================================================
# MAIN SCRAPER
# =============================================================

print("=" * 60)
print("BELLHAVEN WEBSITE SCRAPER")
print("=" * 60)

community_urls = get_community_urls()

print()
print(f"Found {len(community_urls)} community pages.")

locations = []

for number, url in enumerate(community_urls, start=1):

    print()
    print(f"Scraping {number}/{len(community_urls)}")
    print(url)

    try:
        location = scrape_community(url)

        locations.append(location)

        print(f"  Name: {location['name']}")
        print(f"  Address: {location['address']}")
        print(f"  City: {location['city']}")
        print(f"  State: {location['state']}")
        print(f"  ZIP: {location['zip']}")
        print(f"  Care: {', '.join(location['care_offerings'])}")

    except Exception as error:

        print(f"  ERROR: {error}")

    # Small delay between requests
    time.sleep(0.2)


# =============================================================
# SAVE RESULTS
# =============================================================

with open(
    "website_locations.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        locations,
        file,
        indent=2,
        ensure_ascii=False
    )


print()
print("=" * 60)
print("SCRAPING COMPLETE")
print("=" * 60)
print(f"Locations successfully scraped: {len(locations)}")
print("Saved to: website_locations.json")