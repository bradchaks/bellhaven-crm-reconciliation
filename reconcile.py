import json
import re
from difflib import SequenceMatcher


# =========================================================
# LOAD DATA
# =========================================================

with open("website_locations.json", "r", encoding="utf-8") as file:
    website_locations = json.load(file)

with open("crm_accounts.json", "r", encoding="utf-8") as file:
    crm_accounts = json.load(file)


# =========================================================
# NORMALIZATION
# =========================================================

def normalize(value):
    if value is None:
        return ""

    value = str(value).lower().strip()

    # Remove punctuation
    value = re.sub(r"[^a-z0-9]+", " ", value)

    # Collapse spaces
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_zip(value):
    if value is None:
        return ""

    return re.sub(r"[^0-9]", "", str(value))


def normalize_address(value):
    """
    Normalize common street abbreviations so that:
    Street = St
    Road = Rd
    Avenue = Ave
    etc.
    """

    value = normalize(value)

    replacements = {
        " street": " st",
        " road": " rd",
        " avenue": " ave",
        " boulevard": " blvd",
        " drive": " dr",
        " lane": " ln",
        " court": " ct",
        " highway": " hwy",
        " parkway": " pkwy",
        " place": " pl",
        " west": " w",
        " east": " e",
        " north": " n",
        " south": " s",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def similarity(value1, value2):
    value1 = normalize(value1)
    value2 = normalize(value2)

    if not value1 or not value2:
        return 0

    return SequenceMatcher(
        None,
        value1,
        value2
    ).ratio()


# =========================================================
# ACCOUNT HELPERS
# =========================================================

def revenue(account):
    try:
        return float(account.get("lifetime_revenue") or 0)
    except (TypeError, ValueError):
        return 0


def outstanding_ar(account):
    try:
        return float(account.get("outstanding_ar") or 0)
    except (TypeError, ValueError):
        return 0


def is_protected(account):
    """
    SOP:
    Revenue AND outstanding AR > 0 means the account
    must not be directly re-parented.
    """

    return (
        revenue(account) > 0
        and outstanding_ar(account) > 0
    )


def is_bellhaven_related(account):
    name = normalize(account.get("name"))
    parent = normalize(account.get("parent_name"))

    return (
        "bellhaven" in name
        or "bellhaven" in parent
    )


# =========================================================
# WEBSITE → CRM MATCHING
# =========================================================

def score_match(website, account):

    website_name = normalize(website.get("name"))
    crm_name = normalize(account.get("name"))

    website_address = normalize_address(
        website.get("address")
    )

    crm_address = normalize_address(
        account.get("billing_street")
    )

    website_city = normalize(
        website.get("city")
    )

    crm_city = normalize(
        account.get("billing_city")
    )

    website_state = normalize(
        website.get("state")
    )

    crm_state = normalize(
        account.get("billing_state")
    )

    website_zip = normalize_zip(
        website.get("zip")
    )

    crm_zip = normalize_zip(
        account.get("billing_zip")
    )

    name_score = similarity(
        website_name,
        crm_name
    )

    address_score = similarity(
        website_address,
        crm_address
    )

    city_match = (
        website_city != ""
        and website_city == crm_city
    )

    state_match = (
        website_state != ""
        and website_state == crm_state
    )

    zip_match = (
        website_zip != ""
        and website_zip == crm_zip
    )

    score = (
        name_score * 40
        + address_score * 30
        + (10 if city_match else 0)
        + (10 if state_match else 0)
        + (10 if zip_match else 0)
    )

    return {
        "score": round(score, 2),
        "name_similarity": round(name_score, 3),
        "address_similarity": round(address_score, 3),
        "city_match": city_match,
        "state_match": state_match,
        "zip_match": zip_match,
    }


# =========================================================
# FIND WEBSITE MATCHES
# =========================================================

website_matches = []

used_crm_ids = set()

for website in website_locations:

    candidates = []

    for account in crm_accounts:

        evidence = score_match(
            website,
            account
        )

        candidates.append({
            "account": account,
            "evidence": evidence
        })

    candidates.sort(
        key=lambda item: item["evidence"]["score"],
        reverse=True
    )

    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None

    crm = best["account"]
    evidence = best["evidence"]

    second_score = (
        second["evidence"]["score"]
        if second
        else 0
    )

    margin = evidence["score"] - second_score

    # Strong identity evidence
    confident = (
        evidence["score"] >= 85
        and margin >= 10
        and evidence["city_match"]
        and evidence["state_match"]
        and evidence["zip_match"]
    )

    if confident:
        classification = "CONFIDENT_MATCH"
        used_crm_ids.add(
            crm.get("account_id")
        )
    elif evidence["score"] >= 65:
        classification = "MATCH_NEEDS_REVIEW"
    else:
        classification = "WEBSITE_NO_CONFIDENT_CRM_MATCH"

    website_matches.append({
        "website": website,
        "crm_account": crm,
        "evidence": evidence,
        "classification": classification,
        "second_best_score": round(second_score, 2),
        "margin": round(margin, 2)
    })


# =========================================================
# CRM → WEBSITE ANALYSIS
# =========================================================

crm_related_accounts = [
    account
    for account in crm_accounts
    if is_bellhaven_related(account)
]


crm_not_on_website = []

for account in crm_related_accounts:

    account_id = account.get("account_id")

    if account_id not in used_crm_ids:

        crm_not_on_website.append(account)


# =========================================================
# DUPLICATE CANDIDATES
# =========================================================

duplicate_candidates = []

for i in range(len(crm_related_accounts)):

    account_a = crm_related_accounts[i]

    for j in range(i + 1, len(crm_related_accounts)):

        account_b = crm_related_accounts[j]

        name_score = similarity(
            account_a.get("name"),
            account_b.get("name")
        )

        address_score = similarity(
            normalize_address(
                account_a.get("billing_street")
            ),
            normalize_address(
                account_b.get("billing_street")
            )
        )

        city_match = (
            normalize(account_a.get("billing_city"))
            == normalize(account_b.get("billing_city"))
        )

        state_match = (
            normalize(account_a.get("billing_state"))
            == normalize(account_b.get("billing_state"))
        )

        zip_match = (
            normalize_zip(account_a.get("billing_zip"))
            == normalize_zip(account_b.get("billing_zip"))
        )

        # Very strong duplicate signal:
        # same/similar name + same location
        if (
            name_score >= 0.85
            and address_score >= 0.85
            and city_match
            and state_match
            and zip_match
        ):

            duplicate_candidates.append({
                "account_1": account_a,
                "account_2": account_b,
                "name_similarity": round(
                    name_score,
                    3
                ),
                "address_similarity": round(
                    address_score,
                    3
                ),
                "protected_account_1": is_protected(
                    account_a
                ),
                "protected_account_2": is_protected(
                    account_b
                )
            })


# =========================================================
# PARENT / NAME / STATUS ISSUES
# =========================================================

parent_issues = []
name_issues = []

for result in website_matches:

    if result["classification"] != "CONFIDENT_MATCH":
        continue

    website = result["website"]
    crm = result["crm_account"]

    website_name = normalize(
        website.get("name")
    )

    crm_name = normalize(
        crm.get("name")
    )

    # Parent should normally be Bellhaven Senior Living
    parent_name = normalize(
        crm.get("parent_name")
    )

    correct_parent = (
        parent_name
        == normalize("Bellhaven Senior Living (Parent Account)")
    )

    if not correct_parent:

        parent_issues.append({
            "website": website,
            "crm_account": crm,
            "protected": is_protected(crm),
            "current_parent": crm.get("parent_name"),
            "expected_parent":
                "Bellhaven Senior Living (Parent Account)"
        })

    # Flag meaningful name differences
    if website_name != crm_name:

        name_issues.append({
            "website": website,
            "crm_account": crm,
            "website_name": website.get("name"),
            "crm_name": crm.get("name")
        })


# =========================================================
# PRINT REPORT
# =========================================================

print()
print("=" * 80)
print("BELLHAVEN RECONCILIATION REPORT")
print("=" * 80)

print()
print(f"Website locations:          {len(website_locations)}")
print(f"CRM accounts:               {len(crm_accounts)}")
print(f"Bellhaven-related CRM:      {len(crm_related_accounts)}")

print()
print("=" * 80)
print("WEBSITE → CRM")
print("=" * 80)

for number, result in enumerate(
    website_matches,
    start=1
):

    website = result["website"]
    crm = result["crm_account"]
    evidence = result["evidence"]

    print()
    print(
        f"{number}. "
        f"{website.get('name')}"
    )

    print(
        f"   CRM: {crm.get('name')}"
    )

    print(
        f"   CRM ID: {crm.get('account_id')}"
    )

    print(
        f"   Parent: {crm.get('parent_name')}"
    )

    print(
        f"   Score: {evidence['score']}"
    )

    print(
        f"   Location evidence: "
        f"city={evidence['city_match']}, "
        f"state={evidence['state_match']}, "
        f"ZIP={evidence['zip_match']}"
    )

    print(
        f"   Classification: "
        f"{result['classification']}"
    )


print()
print("=" * 80)
print("PARENT ISSUES")
print("=" * 80)

if not parent_issues:
    print("None found.")

else:

    for issue in parent_issues:

        crm = issue["crm_account"]

        print()
        print(
            f"Website: "
            f"{issue['website']['name']}"
        )

        print(
            f"CRM: "
            f"{crm.get('name')}"
        )

        print(
            f"CRM ID: "
            f"{crm.get('account_id')}"
        )

        print(
            f"Current parent: "
            f"{issue['current_parent']}"
        )

        print(
            f"Expected parent: "
            f"{issue['expected_parent']}"
        )

        print(
            f"Protected: "
            f"{issue['protected']}"
        )


print()
print("=" * 80)
print("NAME DIFFERENCES")
print("=" * 80)

if not name_issues:
    print("None found.")

else:

    for issue in name_issues:

        print()
        print(
            f"Website name: "
            f"{issue['website_name']}"
        )

        print(
            f"CRM name:     "
            f"{issue['crm_name']}"
        )

        print(
            f"CRM ID:       "
            f"{issue['crm_account'].get('account_id')}"
        )


print()
print("=" * 80)
print("CRM ACCOUNTS NOT FOUND ON CURRENT WEBSITE")
print("=" * 80)

for account in crm_not_on_website:

    print(
        f"{account.get('account_id')} | "
        f"{account.get('name')} | "
        f"{account.get('billing_city')}, "
        f"{account.get('billing_state')} | "
        f"Parent: {account.get('parent_name')} | "
        f"Revenue: ${revenue(account):,.2f} | "
        f"AR: ${outstanding_ar(account):,.2f}"
    )


print()
print("=" * 80)
print("DUPLICATE CANDIDATES")
print("=" * 80)

if not duplicate_candidates:

    print("None found.")

else:

    for candidate in duplicate_candidates:

        a = candidate["account_1"]
        b = candidate["account_2"]

        print()
        print(
            f"ACCOUNT 1: "
            f"{a.get('account_id')} | "
            f"{a.get('name')}"
        )

        print(
            f"ACCOUNT 2: "
            f"{b.get('account_id')} | "
            f"{b.get('name')}"
        )

        print(
            f"Name similarity: "
            f"{candidate['name_similarity']}"
        )

        print(
            f"Address similarity: "
            f"{candidate['address_similarity']}"
        )

        print(
            f"Protected account 1: "
            f"{candidate['protected_account_1']}"
        )

        print(
            f"Protected account 2: "
            f"{candidate['protected_account_2']}"
        )


# =========================================================
# SUMMARY
# =========================================================

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

confident_count = sum(
    1
    for result in website_matches
    if result["classification"]
    == "CONFIDENT_MATCH"
)

review_count = sum(
    1
    for result in website_matches
    if result["classification"]
    == "MATCH_NEEDS_REVIEW"
)

no_match_count = sum(
    1
    for result in website_matches
    if result["classification"]
    == "WEBSITE_NO_CONFIDENT_CRM_MATCH"
)

print(
    f"Confident website matches:       {confident_count}"
)

print(
    f"Matches needing review:          {review_count}"
)

print(
    f"Website locations without match: {no_match_count}"
)

print(
    f"CRM accounts not on website:     "
    f"{len(crm_not_on_website)}"
)

print(
    f"Duplicate candidates:            "
    f"{len(duplicate_candidates)}"
)

print(
    f"Parent issues among matches:     "
    f"{len(parent_issues)}"
)

print(
    f"Name differences among matches:  "
    f"{len(name_issues)}"
)


# =========================================================
# SAVE COMPLETE REPORT
# =========================================================

report = {
    "website_matches": website_matches,
    "crm_not_on_website": crm_not_on_website,
    "duplicate_candidates": duplicate_candidates,
    "parent_issues": parent_issues,
    "name_issues": name_issues,
    "summary": {
        "website_locations": len(website_locations),
        "crm_accounts": len(crm_accounts),
        "bellhaven_related_crm": len(crm_related_accounts),
        "confident_matches": confident_count,
        "matches_needing_review": review_count,
        "website_without_match": no_match_count,
        "crm_not_on_website": len(crm_not_on_website),
        "duplicate_candidates": len(
            duplicate_candidates
        ),
        "parent_issues": len(parent_issues),
        "name_differences": len(name_issues)
    }
}


with open(
    "reconciliation_report.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        report,
        file,
        indent=2,
        ensure_ascii=False
    )


print()
print("=" * 80)
print("RECONCILIATION COMPLETE")
print("=" * 80)

print()
print(
    "Saved to: reconciliation_report.json"
)