# Bellhaven Senior Living — CRM Reconciliation & Sync

A safe, auditable reconciliation workflow for comparing Bellhaven Senior Living's public website locations against CRM account records.

The solution identifies discrepancies between the website and CRM, generates proposed changes, provides a human review step, and only writes approved changes to the CRM.

---

## Overview

The assessment required a workflow that could:

1. Scrape every Bellhaven location from the website.
2. Match website locations to CRM accounts.
3. Identify discrepancies such as:
   - incorrect parent accounts
   - outdated names
   - CRM accounts no longer appearing on the website
   - duplicate accounts
   - website locations without CRM accounts
4. Provide evidence for proposed changes.
5. Require explicit human approval before changing the CRM.
6. Protect financially sensitive accounts according to the provided SOP.
7. Support safe daily reruns without repeatedly generating the same proposals.

The implementation separates **discovery**, **proposal generation**, and **CRM writes**.

---

## Solution Architecture

```text
Bellhaven Website
       |
       v
scrape_website.py
       |
       v
website_locations.json
       |
       v
generate_proposals.py
       |
       v
proposals.json
       |
       v
review_app.py
       |
       |  Human reviews evidence
       |
       +------ Reject ------> No CRM change
       |
       +------ Approve -----> CRM PATCH
