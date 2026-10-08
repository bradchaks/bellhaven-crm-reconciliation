import json
from collections import Counter


# ---------------------------------------------------------
# LOAD CRM DATA
# ---------------------------------------------------------

with open("crm_accounts.json", "r", encoding="utf-8") as file:
    accounts = json.load(file)


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def money(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def is_bellhaven_related(account):
    """
    Identify accounts that appear to belong to the
    Bellhaven organisation or one of its parent structures.
    """

    name = (account.get("name") or "").lower()
    parent_name = (account.get("parent_name") or "").lower()

    return (
        "bellhaven" in name
        or "bellhaven" in parent_name
    )


def protected(account):
    """
    SOP protection rule:
    If lifetime revenue AND outstanding AR are both > 0,
    the existing account must not be re-parented.
    """

    return (
        money(account.get("lifetime_revenue")) > 0
        and money(account.get("outstanding_ar")) > 0
    )


# ---------------------------------------------------------
# FILTER BELLHAVEN-RELATED ACCOUNTS
# ---------------------------------------------------------

bellhaven_accounts = [
    account
    for account in accounts
    if is_bellhaven_related(account)
]


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

print("=" * 80)
print("BELLHAVEN CRM AUDIT")
print("=" * 80)

print()
print(f"Total CRM accounts:       {len(accounts)}")
print(f"Bellhaven-related:        {len(bellhaven_accounts)}")


# ---------------------------------------------------------
# PARENT SUMMARY
# ---------------------------------------------------------

parent_counts = Counter(
    account.get("parent_name") or "[No Parent]"
    for account in bellhaven_accounts
)

print()
print("=" * 80)
print("PARENT SUMMARY")
print("=" * 80)

for parent, count in parent_counts.most_common():
    print(f"{count:>3} | {parent}")


# ---------------------------------------------------------
# DETAILED ACCOUNT AUDIT
# ---------------------------------------------------------

print()
print("=" * 80)
print("BELLHAVEN-RELATED ACCOUNTS")
print("=" * 80)

for account in sorted(
    bellhaven_accounts,
    key=lambda x: (
        x.get("parent_name") or "",
        x.get("name") or ""
    )
):

    account_id = account.get("account_id")
    name = account.get("name")
    parent = account.get("parent_name") or "[No Parent]"
    status = account.get("status") or "[blank]"
    city = account.get("billing_city") or ""
    state = account.get("billing_state") or ""
    zip_code = account.get("billing_zip") or ""

    revenue = money(account.get("lifetime_revenue"))
    ar = money(account.get("outstanding_ar"))

    duplicate = account.get("duplicate_of_account")
    chow = account.get("chow_current_account")

    protection = "PROTECTED" if protected(account) else "NOT PROTECTED"

    print()
    print("-" * 80)

    print(f"Account ID:       {account_id}")
    print(f"Name:             {name}")
    print(f"Parent:           {parent}")
    print(f"Status:           {status}")
    print(f"Location:         {city}, {state} {zip_code}")
    print(f"Lifetime revenue: ${revenue:,.2f}")
    print(f"Outstanding AR:   ${ar:,.2f}")
    print(f"Protection:       {protection}")

    print(
        "Duplicate of:     "
        + (str(duplicate) if duplicate else "[none]")
    )

    print(
        "CHOW destination: "
        + (str(chow) if chow else "[none]")
    )


# ---------------------------------------------------------
# PROTECTED ACCOUNT SUMMARY
# ---------------------------------------------------------

protected_accounts = [
    account
    for account in bellhaven_accounts
    if protected(account)
]

print()
print("=" * 80)
print("PROTECTED ACCOUNTS")
print("=" * 80)

print()
print(
    "These accounts have BOTH lifetime revenue and outstanding AR."
)
print(
    "They must NOT be directly re-parented under the SOP."
)

print()

for account in protected_accounts:

    print(
        f"{account.get('account_id')} | "
        f"{account.get('name')} | "
        f"Parent: {account.get('parent_name')} | "
        f"Revenue: ${money(account.get('lifetime_revenue')):,.2f} | "
        f"AR: ${money(account.get('outstanding_ar')):,.2f}"
    )


# ---------------------------------------------------------
# STATUS SUMMARY
# ---------------------------------------------------------

status_counts = Counter(
    account.get("status") or "[blank]"
    for account in bellhaven_accounts
)

print()
print("=" * 80)
print("STATUS SUMMARY")
print("=" * 80)

for status, count in status_counts.most_common():
    print(f"{count:>3} | {status}")


# ---------------------------------------------------------
# CARE TYPE SUMMARY
# ---------------------------------------------------------

care_counts = Counter(
    account.get("care_type") or "[blank]"
    for account in bellhaven_accounts
)

print()
print("=" * 80)
print("CARE TYPE SUMMARY")
print("=" * 80)

for care_type, count in care_counts.most_common():
    print(f"{count:>3} | {care_type}")


# ---------------------------------------------------------
# DUPLICATE / CHOW SUMMARY
# ---------------------------------------------------------

duplicates = [
    account
    for account in bellhaven_accounts
    if account.get("duplicate_of_account")
]

chow_accounts = [
    account
    for account in bellhaven_accounts
    if account.get("chow_current_account")
]


print()
print("=" * 80)
print("SPECIAL CASE SUMMARY")
print("=" * 80)

print(f"Already marked duplicates: {len(duplicates)}")
print(f"Accounts with CHOW destination: {len(chow_accounts)}")


# ---------------------------------------------------------
# SAVE AUDIT DATA
# ---------------------------------------------------------

audit_data = {
    "total_crm_accounts": len(accounts),
    "bellhaven_related_accounts": len(bellhaven_accounts),
    "parent_summary": dict(parent_counts),
    "protected_accounts": [
        account.get("account_id")
        for account in protected_accounts
    ],
    "duplicate_accounts": [
        account.get("account_id")
        for account in duplicates
    ],
    "chow_accounts": [
        account.get("account_id")
        for account in chow_accounts
    ]
}

with open(
    "crm_audit_summary.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        audit_data,
        file,
        indent=2,
        ensure_ascii=False
    )


print()
print("=" * 80)
print("CRM AUDIT COMPLETE")
print("=" * 80)

print()
print("Saved summary to: crm_audit_summary.json")