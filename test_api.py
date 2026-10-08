import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("CRM_API_TOKEN")

if not token:
    print("ERROR: CRM_API_TOKEN was not found.")
    raise SystemExit(1)

BASE_URL = "https://analyst-assessment-production.up.railway.app/api/v1/accounts"

headers = {
    "Authorization": f"Bearer {token}"
}

all_accounts = []
page = 1
page_size = 50

while True:
    print(f"Fetching page {page}...")

    response = requests.get(
        BASE_URL,
        headers=headers,
        params={
            "page": page,
            "page_size": page_size
        }
    )

    if response.status_code != 200:
        print(f"API request failed on page {page}")
        print("Status code:", response.status_code)
        print(response.text)
        raise SystemExit(1)

    result = response.json()
    accounts = result.get("data", [])

    print(f"  Retrieved {len(accounts)} accounts")

    all_accounts.extend(accounts)

    # If fewer than page_size were returned,
    # we've reached the final page.
    if len(accounts) < page_size:
        break

    page += 1

print()
print("CRM download complete.")
print("Total accounts:", len(all_accounts))

# Save the complete CRM snapshot
with open("crm_accounts.json", "w", encoding="utf-8") as file:
    json.dump(all_accounts, file, indent=2, ensure_ascii=False)

print("Saved to: crm_accounts.json")