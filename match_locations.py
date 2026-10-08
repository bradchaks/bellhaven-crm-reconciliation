import json
import re
from difflib import SequenceMatcher


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

with open("website_locations.json", "r", encoding="utf-8") as file:
    website_locations = json.load(file)

with open("crm_accounts.json", "r", encoding="utf-8") as file:
    crm_accounts = json.load(file)


# ---------------------------------------------------------
# NORMALIZATION FUNCTIONS
# ---------------------------------------------------------

def normalize(value):
    """Normalize text for comparison."""

    if value is None:
        return ""

    value = str(value).lower().strip()

    # Replace common punctuation with spaces
    value = re.sub(r"[^a-z0-9]+", " ", value)

    # Collapse multiple spaces
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_zip(value):
    """Normalize ZIP/postcode."""

    if value is None:
        return ""

    return re.sub(r"[^0-9]", "", str(value))


def similarity(value1, value2):
    """Return similarity between two strings from 0 to 1."""

    value1 = normalize(value1)
    value2 = normalize(value2)

    if not value1 or not value2:
        return 0

    return SequenceMatcher(None, value1, value2).ratio()


# ---------------------------------------------------------
# MATCH SCORING
# ---------------------------------------------------------

def calculate_match(website, crm):
    """
    Calculate a match score between a website location
    and a CRM account.
    """

    website_name = normalize(website["name"])
    crm_name = normalize(crm.get("name"))

    website_address = normalize(website["address"])
    crm_address = normalize(crm.get("billing_street"))

    website_city = normalize(website["city"])
    crm_city = normalize(crm.get("billing_city"))

    website_state = normalize(website["state"])
    crm_state = normalize(crm.get("billing_state"))

    website_zip = normalize_zip(website["zip"])
    crm_zip = normalize_zip(crm.get("billing_zip"))

    name_score = similarity(website_name, crm_name)
    address_score = similarity(website_address, crm_address)

    city_match = website_city == crm_city and website_city != ""
    state_match = website_state == crm_state and website_state != ""
    zip_match = website_zip == crm_zip and website_zip != ""

    # -----------------------------------------------------
    # SCORE
    # -----------------------------------------------------

    score = 0

    # Name is useful but addresses are stronger evidence
    score += name_score * 40
    score += address_score * 30

    if city_match:
        score += 10

    if state_match:
        score += 10

    if zip_match:
        score += 10

    return {
        "score": round(score, 2),
        "name_similarity": round(name_score, 3),
        "address_similarity": round(address_score, 3),
        "city_match": city_match,
        "state_match": state_match,
        "zip_match": zip_match,
    }


# ---------------------------------------------------------
# FIND BEST CRM MATCH
# ---------------------------------------------------------

def find_best_match(website):
    """Find the strongest CRM candidate for a website location."""

    candidates = []

    for crm in crm_accounts:

        result = calculate_match(website, crm)

        candidates.append({
            "crm": crm,
            "match": result
        })

    candidates.sort(
        key=lambda item: item["match"]["score"],
        reverse=True
    )

    best = candidates[0]

    second_best = candidates[1] if len(candidates) > 1 else None

    return best, second_best


# ---------------------------------------------------------
# CLASSIFY MATCH
# ---------------------------------------------------------

def classify_match(best, second_best):
    """
    Classify the match.

    This is deliberately conservative.
    We do not want uncertain matches automatically
    changing CRM records.
    """

    score = best["match"]["score"]

    second_score = (
        second_best["match"]["score"]
        if second_best
        else 0
    )

    margin = score - second_score

    if score >= 85 and margin >= 10:
        return "CONFIDENT_MATCH"

    if score >= 65:
        return "MATCH_NEEDS_REVIEW"

    return "NO_CONFIDENT_MATCH"


# ---------------------------------------------------------
# RUN MATCHING
# ---------------------------------------------------------

print("=" * 70)
print("BELLHAVEN CRM MATCHING ANALYSIS")
print("=" * 70)

print()
print(f"Website locations: {len(website_locations)}")
print(f"CRM accounts:      {len(crm_accounts)}")

results = []

for number, website in enumerate(website_locations, start=1):

    best, second_best = find_best_match(website)

    classification = classify_match(
        best,
        second_best
    )

    crm = best["crm"]
    match = best["match"]

    result = {
        "website": website,
        "crm_account": crm,
        "match": match,
        "classification": classification,
        "second_best_crm": (
            second_best["crm"]
            if second_best
            else None
        ),
        "second_best_score": (
            second_best["match"]["score"]
            if second_best
            else None
        )
    }

    results.append(result)

    print()
    print("-" * 70)
    print(f"MATCH {number}/{len(website_locations)}")
    print("-" * 70)

    print("WEBSITE")
    print(f"  Name:    {website['name']}")
    print(f"  Address: {website['address']}")
    print(f"  City:    {website['city']}")
    print(f"  State:   {website['state']}")
    print(f"  ZIP:     {website['zip']}")

    print()
    print("BEST CRM MATCH")
    print(f"  ID:      {crm.get('account_id')}")
    print(f"  Name:    {crm.get('name')}")
    print(f"  Address: {crm.get('billing_street')}")
    print(f"  City:    {crm.get('billing_city')}")
    print(f"  State:   {crm.get('billing_state')}")
    print(f"  ZIP:     {crm.get('billing_zip')}")
    print(f"  Parent:  {crm.get('parent_name')}")

    print()
    print("MATCH EVIDENCE")
    print(f"  Overall score:       {match['score']}")
    print(f"  Name similarity:     {match['name_similarity']}")
    print(f"  Address similarity:  {match['address_similarity']}")
    print(f"  City match:          {match['city_match']}")
    print(f"  State match:         {match['state_match']}")
    print(f"  ZIP match:           {match['zip_match']}")

    print()
    print(f"CLASSIFICATION: {classification}")


# ---------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------

with open(
    "match_results.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        results,
        file,
        indent=2,
        ensure_ascii=False
    )


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

summary = {}

for result in results:

    classification = result["classification"]

    summary[classification] = (
        summary.get(classification, 0) + 1
    )


print()
print("=" * 70)
print("MATCHING SUMMARY")
print("=" * 70)

for classification, count in summary.items():
    print(f"{classification}: {count}")

print()
print("Saved detailed results to:")
print("match_results.json")

print()
print("=" * 70)
print("MATCHING ANALYSIS COMPLETE")
print("=" * 70)