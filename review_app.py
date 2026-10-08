import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
import html

import requests
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

CRM_API_TOKEN = os.getenv("CRM_API_TOKEN")

BASE_URL = "https://analyst-assessment-production.up.railway.app"
ACCOUNTS_URL = f"{BASE_URL}/api/v1/accounts"

PROPOSALS_FILE = "proposals.json"

HOST = "127.0.0.1"
PORT = 8000


# ============================================================
# SAFETY CHECK
# ============================================================

if not CRM_API_TOKEN:
    raise RuntimeError(
        "CRM_API_TOKEN was not found in .env. "
        "Make sure your .env file contains CRM_API_TOKEN."
    )


# ============================================================
# FILE HELPERS
# ============================================================

def load_proposals():
    if not os.path.exists(PROPOSALS_FILE):
        return []

    with open(
        PROPOSALS_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def save_proposals(proposals):
    with open(
        PROPOSALS_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            proposals,
            file,
            indent=2,
            ensure_ascii=False
        )


def now_utc():
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# CRM API
# ============================================================

def crm_headers():
    return {
        "Authorization": f"Bearer {CRM_API_TOKEN}",
        "Content-Type": "application/json"
    }


def update_crm_account(account_id, changes):
    """
    Send an approved account update to the CRM.

    This function is ONLY called after the reviewer explicitly
    presses APPROVE.
    """

    url = f"{ACCOUNTS_URL}/{account_id}"

    response = requests.patch(
        url,
        headers=crm_headers(),
        json=changes,
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(
            f"CRM API returned HTTP {response.status_code}: "
            f"{response.text}"
        )

    return response


# ============================================================
# HTML HELPERS
# ============================================================

def esc(value):
    if value is None:
        return ""

    return html.escape(str(value))


def render_page(message=""):
    proposals = load_proposals()

    pending = [
        proposal
        for proposal in proposals
        if proposal.get("review_status") == "PENDING"
    ]

    reviewed = [
        proposal
        for proposal in proposals
        if proposal.get("review_status") != "PENDING"
    ]

    page = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Bellhaven CRM Review</title>

    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            margin: 0;
            padding: 30px;
            color: #222;
        }}

        .container {{
            max-width: 1100px;
            margin: auto;
        }}

        h1 {{
            margin-bottom: 5px;
        }}

        .subtitle {{
            color: #666;
            margin-bottom: 25px;
        }}

        .message {{
            background: #e8f4ea;
            border: 1px solid #b7d8bc;
            padding: 14px;
            border-radius: 6px;
            margin-bottom: 20px;
        }}

        .warning {{
            background: #fff4d6;
            border: 1px solid #e3c66b;
            padding: 14px;
            border-radius: 6px;
            margin-bottom: 20px;
        }}

        .proposal {{
            background: white;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .proposal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #ddd;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}

        .proposal-type {{
            font-size: 20px;
            font-weight: bold;
        }}

        .status {{
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 13px;
            font-weight: bold;
        }}

        .pending {{
            background: #fff1c7;
        }}

        .applied {{
            background: #d9f2df;
        }}

        .rejected {{
            background: #f7dddd;
        }}

        .section {{
            margin-top: 20px;
        }}

        .section h3 {{
            margin-bottom: 8px;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            background: #fafafa;
        }}

        th, td {{
            border: 1px solid #ddd;
            padding: 9px;
            text-align: left;
            vertical-align: top;
        }}

        th {{
            width: 220px;
            background: #f0f0f0;
        }}

        pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            background: #f7f7f7;
            padding: 12px;
            border-radius: 5px;
        }}

        .buttons {{
            margin-top: 25px;
            display: flex;
            gap: 12px;
        }}

        button {{
            border: none;
            border-radius: 5px;
            padding: 12px 22px;
            font-size: 15px;
            cursor: pointer;
        }}

        .approve {{
            background: #238636;
            color: white;
        }}

        .reject {{
            background: #cf222e;
            color: white;
        }}

        .approve:hover {{
            background: #1b6f2c;
        }}

        .reject:hover {{
            background: #a91b25;
        }}

        .reviewed {{
            opacity: 0.8;
        }}

        .empty {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            text-align: center;
        }}

        .small {{
            color: #666;
            font-size: 13px;
        }}
    </style>
</head>

<body>

<div class="container">

    <h1>Bellhaven CRM Review</h1>

    <div class="subtitle">
        Human approval is required before any CRM record is changed.
    </div>
"""

    if message:
        page += f"""
        <div class="message">
            {esc(message)}
        </div>
        """

    page += f"""
    <div class="warning">
        <strong>Safety rule:</strong>
        Opening this page does not change the CRM.
        A CRM update only occurs after an explicit
        <strong>Approve & Apply</strong> action.
    </div>

    <h2>Pending proposals ({len(pending)})</h2>
"""

    if not pending:
        page += """
        <div class="empty">
            No proposals are currently waiting for review.
        </div>
        """

    for proposal in pending:
        page += render_pending_proposal(proposal)

    page += f"""
    <h2>Review history ({len(reviewed)})</h2>
"""

    if not reviewed:
        page += """
        <div class="empty">
            No proposals have been reviewed yet.
        </div>
        """

    for proposal in reviewed:
        page += render_reviewed_proposal(proposal)

    page += """
</div>

</body>
</html>
"""

    return page


def render_pending_proposal(proposal):
    proposal_id = proposal.get("proposal_id", "")
    evidence = proposal.get("evidence", {})
    changes = proposal.get("changes", {})

    return f"""
<div class="proposal">

    <div class="proposal-header">

        <div class="proposal-type">
            {esc(proposal.get("proposal_type"))}
        </div>

        <div class="status pending">
            PENDING
        </div>

    </div>

    <table>

        <tr>
            <th>Proposal ID</th>
            <td>{esc(proposal_id)}</td>
        </tr>

        <tr>
            <th>Account</th>
            <td>{esc(proposal.get("account_name"))}</td>
        </tr>

        <tr>
            <th>Account ID</th>
            <td>{esc(proposal.get("account_id"))}</td>
        </tr>

        <tr>
            <th>Action</th>
            <td>{esc(proposal.get("action"))}</td>
        </tr>

        <tr>
            <th>Protected</th>
            <td>{esc(proposal.get("protected"))}</td>
        </tr>

    </table>

    <div class="section">
        <h3>Why this change is proposed</h3>

        <p>
            {esc(proposal.get("reason"))}
        </p>
    </div>

    <div class="section">
        <h3>Proposed CRM changes</h3>

        <pre>{esc(json.dumps(changes, indent=2))}</pre>
    </div>

    <div class="section">
        <h3>Evidence</h3>

        <pre>{esc(json.dumps(evidence, indent=2))}</pre>
    </div>

    <div class="buttons">

        <form method="POST" action="/approve">

            <input
                type="hidden"
                name="proposal_id"
                value="{esc(proposal_id)}"
            >

            <button
                class="approve"
                type="submit"
                onclick="return confirm(
                    'Approve this proposal and apply the change to the CRM?'
                );"
            >
                Approve & Apply
            </button>

        </form>

        <form method="POST" action="/reject">

            <input
                type="hidden"
                name="proposal_id"
                value="{esc(proposal_id)}"
            >

            <button
                class="reject"
                type="submit"
                onclick="return confirm(
                    'Reject this proposal? No CRM change will be made.'
                );"
            >
                Reject
            </button>

        </form>

    </div>

</div>
"""


def render_reviewed_proposal(proposal):
    status = proposal.get("review_status", "")

    css_class = "applied"

    if status == "REJECTED":
        css_class = "rejected"

    return f"""
<div class="proposal reviewed">

    <div class="proposal-header">

        <div class="proposal-type">
            {esc(proposal.get("proposal_type"))}
        </div>

        <div class="status {css_class}">
            {esc(status)}
        </div>

    </div>

    <table>

        <tr>
            <th>Proposal ID</th>
            <td>{esc(proposal.get("proposal_id"))}</td>
        </tr>

        <tr>
            <th>Account</th>
            <td>{esc(proposal.get("account_name"))}</td>
        </tr>

        <tr>
            <th>Account ID</th>
            <td>{esc(proposal.get("account_id"))}</td>
        </tr>

        <tr>
            <th>Reviewed at</th>
            <td>{esc(proposal.get("reviewed_at"))}</td>
        </tr>

        <tr>
            <th>Applied at</th>
            <td>{esc(proposal.get("applied_at"))}</td>
        </tr>

        <tr>
            <th>Review note</th>
            <td>{esc(proposal.get("review_note"))}</td>
        </tr>

    </table>

</div>
"""


# ============================================================
# HTTP SERVER
# ============================================================

class ReviewHandler(BaseHTTPRequestHandler):

    def send_html(self, content, status=200):

        encoded = content.encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(encoded))
        )

        self.end_headers()

        self.wfile.write(encoded)


    def redirect_home(self):

        self.send_response(303)

        self.send_header(
            "Location",
            "/"
        )

        self.end_headers()


    def do_GET(self):

        if self.path == "/":

            page = render_page()

            self.send_html(page)

            return

        self.send_error(404)


    def do_POST(self):

        content_length = int(
            self.headers.get(
                "Content-Length",
                0
            )
        )

        body = self.rfile.read(
            content_length
        ).decode("utf-8")

        form = parse_qs(body)

        proposal_id = form.get(
            "proposal_id",
            [None]
        )[0]

        if not proposal_id:

            self.send_html(
                render_page(
                    "No proposal ID was supplied."
                ),
                status=400
            )

            return

        if self.path == "/approve":

            self.approve_proposal(
                proposal_id
            )

            return

        if self.path == "/reject":

            self.reject_proposal(
                proposal_id
            )

            return

        self.send_error(404)


    def approve_proposal(self, proposal_id):

        proposals = load_proposals()

        proposal = None

        for item in proposals:

            if item.get("proposal_id") == proposal_id:

                proposal = item

                break

        if not proposal:

            self.send_html(
                render_page(
                    f"Proposal {proposal_id} was not found."
                ),
                status=404
            )

            return

        # Prevent double application.
        if proposal.get("review_status") == "APPLIED":

            self.send_html(
                render_page(
                    "This proposal has already been applied."
                )
            )

            return

        # Only PENDING proposals may be approved.
        if proposal.get("review_status") != "PENDING":

            self.send_html(
                render_page(
                    "This proposal is no longer pending."
                )
            )

            return

        try:

            account_id = proposal.get(
                "account_id"
            )

            changes = proposal.get(
                "changes",
                {}
            )

            if not account_id:

                raise RuntimeError(
                    "Proposal does not contain an account ID."
                )

            if not changes:

                raise RuntimeError(
                    "Proposal contains no CRM changes."
                )

            # ==================================================
            # IMPORTANT:
            # THIS IS THE ONLY PLACE THE APP WRITES TO THE CRM.
            #
            # It is reached only after the reviewer explicitly
            # presses the Approve & Apply button.
            # ==================================================

            update_crm_account(
                account_id,
                changes
            )

            proposal["review_status"] = "APPLIED"

            proposal["reviewed_at"] = now_utc()

            proposal["applied_at"] = now_utc()

            proposal["review_note"] = (
                "Approved by reviewer and successfully "
                "applied to CRM."
            )

            save_proposals(proposals)

            self.send_html(
                render_page(
                    f"Proposal {proposal_id} was approved "
                    f"and successfully applied to the CRM."
                )
            )

        except Exception as error:

            # Do NOT mark it as applied if the API failed.

            proposal["review_status"] = "PENDING"

            proposal["review_note"] = (
                f"CRM update failed: {error}"
            )

            save_proposals(proposals)

            self.send_html(
                render_page(
                    f"CRM update failed. "
                    f"No successful application was recorded. "
                    f"Error: {error}"
                ),
                status=500
            )


    def reject_proposal(self, proposal_id):

        proposals = load_proposals()

        proposal = None

        for item in proposals:

            if item.get("proposal_id") == proposal_id:

                proposal = item

                break

        if not proposal:

            self.send_html(
                render_page(
                    f"Proposal {proposal_id} was not found."
                ),
                status=404
            )

            return

        if proposal.get("review_status") != "PENDING":

            self.send_html(
                render_page(
                    "This proposal is no longer pending."
                )
            )

            return

        proposal["review_status"] = "REJECTED"

        proposal["reviewed_at"] = now_utc()

        proposal["review_note"] = (
            "Rejected by reviewer. No CRM change was made."
        )

        save_proposals(proposals)

        self.send_html(
            render_page(
                f"Proposal {proposal_id} was rejected. "
                f"No CRM change was made."
            )
        )


# ============================================================
# START SERVER
# ============================================================

def main():

    print("=" * 70)
    print("BELLHAVEN CRM REVIEW APP")
    print("=" * 70)

    print()
    print(f"Starting local review app on:")
    print(f"http://{HOST}:{PORT}")

    print()
    print("CRM writes occur ONLY after an explicit")
    print("Approve & Apply action.")

    print()
    print("Press CTRL+C to stop the server.")
    print()

    server = HTTPServer(
        (HOST, PORT),
        ReviewHandler
    )

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print("Stopping review app...")

        server.server_close()


if __name__ == "__main__":
    main()