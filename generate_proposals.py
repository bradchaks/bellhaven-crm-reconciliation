import json
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

CRM_API_TOKEN = os.getenv("CRM_API_TOKEN")

BASE_URL = "https://analyst-assessment-production.up.railway.app"
ACCOUNTS_URL = f"{BASE_URL}/api/v1/accounts"

CRM_FILE = "crm_accounts.json"
WEBSITE_FILE = "website_locations.json"
PROPOSALS_FILE = "proposals.json"

BELLHAVEN_PARENT_NAME = "Bellhaven Senior Living (Parent Account)"


# ============================================================
# SAFETY CHECK
# ============================================================

if not CRM_API_TOKEN:
    raise RuntimeError(
        "CRM_API_TOKEN was not found in .env. "
        "Make sure your .env file contains CRM_API_TOKEN."
    )


# ============================================================
# BASIC HELPERS
# ============================================================

def now_utc():
    return datetime.now(timezone.utc).isoformat()


def normalise(value):
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace(".", "")
        .replace(",", "")
        .replace("-", " ")
    )


def normalise_zip(value):
    if value is None:
        return ""

    return "".join(
        character
        for character in str(value)
        if character.isalnum()
    ).lower()


def load_json(filename, default):
    if not os.path.exists(filename):
        return default

    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def save_json(filename, data):
    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# CRM API
# ============================================================

def crm_headers():
    return {
        "Authorization": f"Bearer {CRM_API_TOKEN}",
        "Content-Type": "application/json"
    }


def fetch_all_crm_accounts():
    """
    Fetch the CURRENT CRM state directly from the API.

    The generator never relies only on crm_accounts.json for
    decision-making because that file is only a snapshot.
    """

    all_accounts = []

    page = 1
    page_size = 50

    while True:

        response = requests.get(
            ACCOUNTS_URL,
            headers=crm_headers(),
            params={
                "page": page,
                "page_size": page_size
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if isinstance(data, dict):

            accounts = data.get(
                "accounts",
                []
            )

            if not accounts:
                accounts = data.get(
                    "data",
                    []
                )

            if not accounts:
                accounts = data.get(
                    "items",
                    []
                )

        elif isinstance(data, list):

            accounts = data

        else:

            raise RuntimeError(
                "Unexpected CRM API response format."
            )

        if not accounts:
            break

        all_accounts.extend(accounts)

        if len(accounts) < page_size:
            break

        page += 1

    return all_accounts


# ============================================================
# FINANCIAL SAFETY
# ============================================================

def lifetime_revenue(account):
    try:
        return float(
            account.get(
                "lifetime_revenue",
                0
            ) or 0
        )
    except (
        TypeError,
        ValueError
    ):
        return 0.0


def outstanding_ar(account):
    try:
        return float(
            account.get(
                "outstanding_ar",
                0
            ) or 0
        )
    except (
        TypeError,
        ValueError
    ):
        return 0.0


def has_revenue(account):
    return lifetime_revenue(account) > 0


def has_outstanding_ar(account):
    return outstanding_ar(account) > 0


def is_financially_protected(account):
    """
    Critical Bellhaven SOP protection.

    An account with BOTH lifetime revenue and outstanding
    AR must not be treated as a normal stale account.
    """

    return (
        has_revenue(account)
        and has_outstanding_ar(account)
    )


def has_zero_financial_history(account):
    """
    Conservative automatic-stale rule.

    We only automatically generate stale proposals where
    BOTH lifetime revenue and outstanding AR are zero.
    """

    return (
        lifetime_revenue(account) == 0
        and outstanding_ar(account) == 0
    )


# ============================================================
# WEBSITE MATCHING
# ============================================================

def website_location_matches_account(
    account,
    website_location
):
    """
    Match using strong location evidence first and exact
    facility name as a secondary signal.

    This is intentionally conservative.
    """

    account_city = normalise(
        account.get("billing_city")
    )

    account_state = normalise(
        account.get("billing_state")
    )

    account_zip = normalise_zip(
        account.get("billing_zip")
    )

    website_city = normalise(
        website_location.get("city")
    )

    website_state = normalise(
        website_location.get("state")
    )

    website_zip = normalise_zip(
        website_location.get("zip")
    )

    # Strong match: city + state + ZIP.
    if (
        account_city
        and account_state
        and account_zip
        and account_city == website_city
        and account_state == website_state
        and account_zip == website_zip
    ):
        return True

    # Secondary exact-name match.
    account_name = normalise(
        account.get("name")
    )

    website_name = normalise(
        website_location.get("name")
    )

    if (
        account_name
        and website_name
        and account_name == website_name
    ):
        return True

    return False


def account_is_on_website(
    account,
    website_locations
):
    for location in website_locations:

        if website_location_matches_account(
            account,
            location
        ):
            return True

    return False


# ============================================================
# BELLHAVEN ACCOUNT IDENTIFICATION
# ============================================================

def is_bellhaven_child_account(
    account,
    parent_id
):
    """
    A stale-account candidate must be a child of the
    Bellhaven Senior Living parent.

    The parent account itself is excluded.
    """

    account_id = account.get(
        "account_id"
    )

    if not account_id:
        return False

    if account_id == parent_id:
        return False

    return (
        account.get("parent_id")
        == parent_id
    )


# ============================================================
# DUPLICATE SAFETY
# ============================================================

def get_duplicate_survivor_ids(
    proposals,
    crm_accounts
):
    """
    Collect every account that is known to be a surviving
    duplicate.

    We use BOTH:
      1. Applied DUPLICATE_RESOLUTION proposals
      2. duplicate_of_account references in the CRM

    This protects the survivor even if the generator is run
    after the proposal history has changed.
    """

    survivor_ids = set()

    # --------------------------------------------------------
    # Existing CRM duplicate relationships
    # --------------------------------------------------------

    duplicate_ids = set()

    for account in crm_accounts:

        duplicate_of = account.get(
            "duplicate_of_account"
        )

        if duplicate_of:
            duplicate_ids.add(
                duplicate_of
            )

    # If account A is marked duplicate_of_account = B,
    # then B is the surviving account.
    survivor_ids.update(
        duplicate_ids
    )

    # --------------------------------------------------------
    # Applied duplicate-resolution proposals
    # --------------------------------------------------------

    for proposal in proposals:

        if (
            proposal.get("proposal_type")
            != "DUPLICATE_RESOLUTION"
        ):
            continue

        if (
            proposal.get("review_status")
            != "APPLIED"
        ):
            continue

        survivor_id = proposal.get(
            "surviving_account_id"
        )

        if survivor_id:
            survivor_ids.add(
                survivor_id
            )

        # Also support a future proposal structure where
        # the surviving account may be stored in evidence.
        evidence = proposal.get(
            "evidence",
            {}
        )

        survivor = evidence.get(
            "survivor",
            {}
        )

        evidence_survivor_id = survivor.get(
            "account_id"
        )

        if evidence_survivor_id:
            survivor_ids.add(
                evidence_survivor_id
            )

    return survivor_ids


# ============================================================
# PROPOSAL HELPERS
# ============================================================

def proposal_id_for_stale_account(
    account_id
):
    return f"stale-crm-{account_id}"


def proposal_exists(
    proposals,
    proposal_id
):
    return any(
        proposal.get("proposal_id")
        == proposal_id
        for proposal in proposals
    )


def build_stale_proposal(
    account
):
    account_id = account.get(
        "account_id"
    )

    return {
        "proposal_id":
            proposal_id_for_stale_account(
                account_id
            ),

        "proposal_type":
            "STALE_CRM_ACCOUNT",

        "action":
            "UPDATE_ACCOUNT",

        "account_id":
            account_id,

        "account_name":
            account.get("name"),

        "review_status":
            "PENDING",

        "protected":
            False,

        "changes": {
            "status": "Inactive",

            "note": (
                "Marked inactive following "
                "website-to-CRM reconciliation. "
                "This Bellhaven-parent account does "
                "not appear on the current Bellhaven "
                "website and has no lifetime revenue "
                "or outstanding AR."
            )
        },

        "reason": (
            "This account is under the Bellhaven "
            "Senior Living parent but does not appear "
            "among the current Bellhaven website "
            "locations. It has no lifetime revenue "
            "and no outstanding AR, so it is eligible "
            "for review as a stale CRM account."
        ),

        "evidence": {
            "crm_name":
                account.get("name"),

            "crm_address":
                account.get("billing_street"),

            "crm_city":
                account.get("billing_city"),

            "crm_state":
                account.get("billing_state"),

            "crm_zip":
                account.get("billing_zip"),

            "parent_id":
                account.get("parent_id"),

            "parent_name":
                account.get("parent_name"),

            "website_location_found":
                False,

            "lifetime_revenue":
                lifetime_revenue(account),

            "outstanding_ar":
                outstanding_ar(account),

            "status":
                account.get("status")
        },

        "generated_at":
            now_utc()
    }


# ============================================================
# RETIRE INVALID OLD PENDING PROPOSALS
# ============================================================

def retire_invalid_pending_proposals(
    proposals,
    crm_accounts,
    website_locations,
    parent_id,
    survivor_ids
):
    """
    Handle proposals generated by an older version of the
    generator.

    We do NOT delete them because that would destroy audit
    history.

    Instead, an obsolete PENDING proposal is marked
    SUPERSEDED with a clear explanation.

    This is particularly important for the old Owosso
    survivor proposal.
    """

    retired_count = 0

    current_accounts = {
        account.get("account_id"): account
        for account in crm_accounts
        if account.get("account_id")
    }

    for proposal in proposals:

        if proposal.get(
            "review_status"
        ) != "PENDING":
            continue

        if proposal.get(
            "proposal_type"
        ) != "STALE_CRM_ACCOUNT":
            continue

        account_id = proposal.get(
            "account_id"
        )

        account = current_accounts.get(
            account_id
        )

        # ----------------------------------------------------
        # Missing CRM account.
        # ----------------------------------------------------

        if account is None:

            proposal["review_status"] = (
                "SUPERSEDED"
            )

            proposal["reviewed_at"] = (
                now_utc()
            )

            proposal["review_note"] = (
                "Automatically superseded because "
                "the CRM account could not be found "
                "in the current CRM dataset."
            )

            retired_count += 1

            continue

        # ----------------------------------------------------
        # No longer a Bellhaven child.
        # ----------------------------------------------------

        if not is_bellhaven_child_account(
            account,
            parent_id
        ):

            proposal["review_status"] = (
                "SUPERSEDED"
            )

            proposal["reviewed_at"] = (
                now_utc()
            )

            proposal["review_note"] = (
                "Automatically superseded because "
                "the account is no longer a direct "
                "child of the Bellhaven Senior Living "
                "parent."
            )

            retired_count += 1

            continue

        # ----------------------------------------------------
        # Already inactive.
        # ----------------------------------------------------

        if normalise(
            account.get("status")
        ) == "inactive":

            proposal["review_status"] = (
                "SUPERSEDED"
            )

            proposal["reviewed_at"] = (
                now_utc()
            )

            proposal["review_note"] = (
                "Automatically superseded because "
                "the CRM account is already inactive."
            )

            retired_count += 1

            continue

        # ----------------------------------------------------
        # It is now present on the website.
        # ----------------------------------------------------

        if account_is_on_website(
            account,
            website_locations
        ):

            proposal["review_status"] = (
                "SUPERSEDED"
            )

            proposal["reviewed_at"] = (
                now_utc()
            )

            proposal["review_note"] = (
                "Automatically superseded because "
                "the CRM account now matches a current "
                "Bellhaven website location."
            )

            retired_count += 1

            continue

        # ----------------------------------------------------
        # Account is a duplicate survivor.
        # ----------------------------------------------------

        if account_id in survivor_ids:

            proposal["review_status"] = (
                "SUPERSEDED"
            )

            proposal["reviewed_at"] = (
                now_utc()
            )

            proposal["review_note"] = (
                "Automatically superseded because "
                "this account is the surviving account "
                "from a duplicate-resolution decision "
                "and must be retained in the CRM."
            )

            retired_count += 1

            continue

        # ----------------------------------------------------
        # Financial protection.
        # ----------------------------------------------------

        if is_financially_protected(
            account
        ):

            proposal["review_status"] = (
                "SUPERSEDED"
            )

            proposal["reviewed_at"] = (
                now_utc()
            )

            proposal["review_note"] = (
                "Automatically superseded because "
                "the current CRM data shows both "
                "lifetime revenue and outstanding AR. "
                "The account requires financial protection "
                "and must not be treated as a normal "
                "stale-account deactivation."
            )

            retired_count += 1

            continue

        # ----------------------------------------------------
        # Non-zero financial history.
        #
        # Conservative policy: do not leave an automatic
        # stale proposal pending for an account that has
        # financial history.
        # ----------------------------------------------------

        if not has_zero_financial_history(
            account
        ):

            proposal["review_status"] = (
                "SUPERSEDED"
            )

            proposal["reviewed_at"] = (
                now_utc()
            )

            proposal["review_note"] = (
                "Automatically superseded because "
                "the current CRM account has financial "
                "history. The conservative generator "
                "only proposes automatic stale-account "
                "changes for accounts with zero revenue "
                "and zero outstanding AR."
            )

            retired_count += 1

    return retired_count


# ============================================================
# MAIN GENERATOR
# ============================================================

def generate_proposals():

    print("=" * 60)
    print("BELLHAVEN PROPOSAL GENERATION")
    print("=" * 60)

    # --------------------------------------------------------
    # Load website locations.
    # --------------------------------------------------------

    website_locations = load_json(
        WEBSITE_FILE,
        []
    )

    if not website_locations:

        raise RuntimeError(
            f"No website locations were found in "
            f"{WEBSITE_FILE}."
        )

    # --------------------------------------------------------
    # Fetch live CRM state.
    # --------------------------------------------------------

    crm_accounts = fetch_all_crm_accounts()

    if not crm_accounts:

        raise RuntimeError(
            "The CRM API returned no accounts."
        )

    # Keep a fresh local snapshot.
    save_json(
        CRM_FILE,
        crm_accounts
    )

    print()
    print(
        f"Current CRM accounts: "
        f"{len(crm_accounts)}"
    )

    print(
        f"Current website locations: "
        f"{len(website_locations)}"
    )

    # --------------------------------------------------------
    # Find Bellhaven parent.
    # --------------------------------------------------------

    parent_matches = [
        account
        for account in crm_accounts
        if normalise(
            account.get("name")
        )
        == normalise(
            BELLHAVEN_PARENT_NAME
        )
    ]

    if not parent_matches:

        raise RuntimeError(
            "Bellhaven Senior Living parent account "
            "could not be found."
        )

    if len(parent_matches) > 1:

        raise RuntimeError(
            "Multiple Bellhaven Senior Living parent "
            "accounts were found. Refusing to generate "
            "proposals until the parent is unambiguous."
        )

    bellhaven_parent = parent_matches[0]

    parent_id = bellhaven_parent.get(
        "account_id"
    )

    print(
        f"Bellhaven parent ID: "
        f"{parent_id}"
    )

    # --------------------------------------------------------
    # Load proposal history.
    # --------------------------------------------------------

    proposals = load_json(
        PROPOSALS_FILE,
        []
    )

    if not isinstance(
        proposals,
        list
    ):

        raise RuntimeError(
            "proposals.json must contain a JSON list."
        )

    # --------------------------------------------------------
    # Find duplicate survivors.
    # --------------------------------------------------------

    survivor_ids = get_duplicate_survivor_ids(
        proposals,
        crm_accounts
    )

    if survivor_ids:

        print()
        print(
            "Duplicate survivor protection:"
        )

        for survivor_id in sorted(
            survivor_ids
        ):
            print(
                f"  {survivor_id}"
            )

    # --------------------------------------------------------
    # Retire obsolete pending proposals from older runs.
    # --------------------------------------------------------

    retired_count = (
        retire_invalid_pending_proposals(
            proposals,
            crm_accounts,
            website_locations,
            parent_id,
            survivor_ids
        )
    )

    if retired_count:

        print()
        print(
            f"Obsolete pending proposals "
            f"superseded: {retired_count}"
        )

    # --------------------------------------------------------
    # Build CURRENT stale candidates.
    # --------------------------------------------------------

    candidates = []

    for account in crm_accounts:

        account_id = account.get(
            "account_id"
        )

        if not account_id:
            continue

        # Must be a Bellhaven child account.
        if not is_bellhaven_child_account(
            account,
            parent_id
        ):
            continue

        # Parent account itself is excluded by the helper.

        # ----------------------------------------------------
        # Never propose a surviving duplicate.
        # ----------------------------------------------------

        if account_id in survivor_ids:

            print()
            print(
                "DUPLICATE SURVIVOR EXCLUSION:"
            )

            print(
                f"  {account.get('name')}"
            )

            print(
                f"  Account ID: {account_id}"
            )

            print(
                "  This account is a designated "
                "surviving duplicate."
            )

            continue

        # ----------------------------------------------------
        # Already inactive.
        # ----------------------------------------------------

        if normalise(
            account.get("status")
        ) == "inactive":
            continue

        # ----------------------------------------------------
        # Already marked as a duplicate loser.
        # ----------------------------------------------------

        if account.get(
            "duplicate_of_account"
        ):
            continue

        # ----------------------------------------------------
        # Current website location.
        # ----------------------------------------------------

        if account_is_on_website(
            account,
            website_locations
        ):
            continue

        # ----------------------------------------------------
        # Critical financial protection.
        # ----------------------------------------------------

        if is_financially_protected(
            account
        ):

            print()
            print(
                "FINANCIAL PROTECTION EXCLUSION:"
            )

            print(
                f"  {account.get('name')}"
            )

            print(
                f"  Revenue: "
                f"${lifetime_revenue(account):,.2f}"
            )

            print(
                f"  Outstanding AR: "
                f"${outstanding_ar(account):,.2f}"
            )

            print(
                "  Both revenue and AR are greater "
                "than zero."
            )

            print(
                "  No stale proposal will be generated."
            )

            continue

        # ----------------------------------------------------
        # Conservative financial rule.
        #
        # Only zero-revenue AND zero-AR accounts can be
        # automatically proposed as stale.
        # ----------------------------------------------------

        if not has_zero_financial_history(
            account
        ):
            continue

        candidates.append(
            account
        )

    # --------------------------------------------------------
    # Add genuinely new proposals.
    # --------------------------------------------------------

    new_count = 0

    for account in candidates:

        account_id = account.get(
            "account_id"
        )

        proposal_id = (
            proposal_id_for_stale_account(
                account_id
            )
        )

        # Never duplicate proposal IDs.
        if proposal_exists(
            proposals,
            proposal_id
        ):
            continue

        proposal = build_stale_proposal(
            account
        )

        proposals.append(
            proposal
        )

        new_count += 1

    # --------------------------------------------------------
    # Save proposal history.
    # --------------------------------------------------------

    save_json(
        PROPOSALS_FILE,
        proposals
    )

    # --------------------------------------------------------
    # Calculate final counts.
    # --------------------------------------------------------

    pending = [
        proposal
        for proposal in proposals
        if proposal.get(
            "review_status"
        ) == "PENDING"
    ]

    applied = [
        proposal
        for proposal in proposals
        if proposal.get(
            "review_status"
        ) == "APPLIED"
    ]

    rejected = [
        proposal
        for proposal in proposals
        if proposal.get(
            "review_status"
        ) == "REJECTED"
    ]

    superseded = [
        proposal
        for proposal in proposals
        if proposal.get(
            "review_status"
        ) == "SUPERSEDED"
    ]

    # --------------------------------------------------------
    # Final output.
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("PROPOSAL GENERATION COMPLETE")
    print("=" * 60)

    print(
        f"Total proposals: "
        f"{len(proposals)}"
    )

    print(
        f"Pending: "
        f"{len(pending)}"
    )

    print(
        f"Applied: "
        f"{len(applied)}"
    )

    print(
        f"Rejected: "
        f"{len(rejected)}"
    )

    print(
        f"Superseded: "
        f"{len(superseded)}"
    )

    print(
        f"New proposals generated: "
        f"{new_count}"
    )

    print()
    print(
        "CURRENT PROPOSAL STATUS"
    )

    for proposal in proposals:

        print(
            f"  "
            f"{proposal.get('proposal_id')} | "
            f"{proposal.get('proposal_type')} | "
            f"{proposal.get('review_status')}"
        )

    print()
    print(
        "SAFETY CHECKS"
    )

    print(
        "  [OK] Current CRM data is fetched "
        "before proposal generation."
    )

    print(
        "  [OK] Website locations are checked "
        "against current CRM accounts."
    )

    print(
        "  [OK] Bellhaven parent account is excluded."
    )

    print(
        "  [OK] Duplicate survivors are protected."
    )

    print(
        "  [OK] Duplicate losers already marked "
        "inactive are excluded."
    )

    print(
        "  [OK] Accounts with both revenue and "
        "outstanding AR are protected."
    )

    print(
        "  [OK] Only zero-revenue / zero-AR accounts "
        "can receive automatic stale proposals."
    )

    print(
        "  [OK] Existing APPLIED and REJECTED "
        "proposals are preserved."
    )

    print(
        "  [OK] Obsolete pending proposals are "
        "superseded rather than deleted."
    )

    print(
        "  [OK] Repeated runs do not create "
        "duplicate proposals."
    )

    print(
        "  [OK] This script makes NO CRM writes."
    )

    print(
        "  [OK] CRM changes require explicit "
        "Approve & Apply in review_app.py."
    )

    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    generate_proposals()