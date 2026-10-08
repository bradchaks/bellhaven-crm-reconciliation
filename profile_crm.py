import json
from collections import Counter

# Load CRM snapshot
with open("crm_accounts.json", "r", encoding="utf-8") as file:
    accounts = json.load(file)

print("=" * 50)
print("BELLHAVEN CRM PROFILE")
print("=" * 50)

print(f"\nTotal accounts: {len(accounts)}")

# Status
status_counts = Counter(
    account.get("status", "")
    for account in accounts
)

print("\nSTATUS")
for status, count in status_counts.items():
    print(f"  {status or '[blank]'}: {count}")

# Care types
care_type_counts = Counter(
    account.get("care_type", "")
    for account in accounts
)

print("\nCARE TYPES")
for care_type, count in care_type_counts.items():
    print(f"  {care_type or '[blank]'}: {count}")

# Revenue
accounts_with_revenue = [
    account for account in accounts
    if float(account.get("lifetime_revenue", 0) or 0) > 0
]

print("\nREVENUE")
print(f"  Accounts with lifetime revenue: {len(accounts_with_revenue)}")

# Outstanding AR
accounts_with_ar = [
    account for account in accounts
    if float(account.get("outstanding_ar", 0) or 0) > 0
]

print(f"  Accounts with outstanding AR: {len(accounts_with_ar)}")

# Revenue + AR
protected_accounts = [
    account for account in accounts
    if float(account.get("lifetime_revenue", 0) or 0) > 0
    and float(account.get("outstanding_ar", 0) or 0) > 0
]

print(
    f"  Accounts with BOTH revenue and outstanding AR: "
    f"{len(protected_accounts)}"
)

# Duplicate fields
duplicates = [
    account for account in accounts
    if account.get("duplicate_of_account")
]

print("\nDUPLICATES")
print(f"  Accounts already marked as duplicates: {len(duplicates)}")

# CHOW fields
chow_accounts = [
    account for account in accounts
    if account.get("chow_current_account")
]

print("\nCHOW")
print(f"  Accounts with CHOW destination: {len(chow_accounts)}")

# Candidate-created records
candidate_accounts = [
    account for account in accounts
    if account.get("created_by_candidate") is True
]

print("\nCANDIDATE-CREATED")
print(f"  Candidate-created accounts: {len(candidate_accounts)}")

# Parent IDs
parent_counts = Counter(
    account.get("parent_id", "")
    for account in accounts
)

print("\nPARENT ACCOUNTS")
print(f"  Unique parent IDs referenced: {len(parent_counts)}")

# Show protected accounts
print("\nPROTECTED ACCOUNTS")
print("(Revenue history AND outstanding AR > 0)")

for account in protected_accounts:
    print(
        f"  {account['account_id']} | "
        f"{account['name']} | "
        f"Revenue: {account['lifetime_revenue']} | "
        f"AR: {account['outstanding_ar']} | "
        f"Parent: {account['parent_name']}"
    )

print("\n" + "=" * 50)
print("PROFILE COMPLETE")
print("=" * 50)