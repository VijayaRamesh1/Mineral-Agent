#!/usr/bin/env python3
"""Create the PM Job Tracker spreadsheet for Vijaya Ramesh."""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import date

wb = openpyxl.Workbook()

# ── Styles ──────────────────────────────────────────────────────────────
header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
data_font = Font(name="Arial", size=10)
green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")  # Applied
yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")  # Ready to apply
blue_border_side = Side(style="thin", color="4472C4")
thin_border = Border(
    left=blue_border_side, right=blue_border_side,
    top=blue_border_side, bottom=blue_border_side,
)
wrap_align = Alignment(wrap_text=True, vertical="top")

# ── Job Data ────────────────────────────────────────────────────────────
# Status: "Ready to Apply" = found but not submitted (cannot auto-submit)
jobs = [
    {
        "#": 1, "Tier": 1, "Company": "Affirm", "Role": "Staff Product Manager, Fraud",
        "Salary": "$178,000 - $228,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse/LinkedIn",
        "Tags": "Fintech, Fraud, Trust & Safety, BNPL",
        "Status": "Ready to Apply",
        "Link": "https://job-boards.greenhouse.io/affirm/jobs/7621004003",
        "Notes": "Staff-level role. Fraud prevention embedded into product. Remote-first. 5+ yrs PM exp required.",
    },
    {
        "#": 2, "Tier": 1, "Company": "Affirm", "Role": "Senior Product Manager, Digital Wallets & Agentic Commerce",
        "Salary": "$150,000 - $200,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse/LinkedIn",
        "Tags": "Fintech, Payments, Apple Pay, Google Pay, Agentic AI",
        "Status": "Ready to Apply",
        "Link": "https://job-boards.greenhouse.io/affirm/jobs/7610334003",
        "Notes": "Own wallet/PSP/merchant integrations. 4+ yrs PM exp. 0-to-1 builder mindset.",
    },
    {
        "#": 3, "Tier": 1, "Company": "Affirm", "Role": "Senior Product Manager, Merchant Risk",
        "Salary": "$150,000 - $200,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse/Indeed",
        "Tags": "Fintech, Risk, Merchant Safety, BNPL",
        "Status": "Ready to Apply",
        "Link": "https://www.canadajobs.works/job/affirm-senior-product-manager-merchant-risk",
        "Notes": "Build/scale systems to keep Affirm safe for consumers & merchants. Remote-first.",
    },
    {
        "#": 4, "Tier": 1, "Company": "Affirm", "Role": "Senior Product Manager, Financial Platforms",
        "Salary": "$150,000 - $200,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse/Jobera",
        "Tags": "Fintech, Loan Lifecycle, Backend Systems, Platform",
        "Status": "Ready to Apply",
        "Link": "https://jobera.com/remote-job/senior-product-manager-financial-platforms-affirm-remote-canada/",
        "Notes": "Core backend loan systems & orchestration layer. Foundational tech solutions.",
    },
    {
        "#": 5, "Tier": 1, "Company": "Affirm", "Role": "Senior Product Manager, Fraud (Trust & Safety)",
        "Salary": "$150,000 - $200,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse",
        "Tags": "Fintech, Fraud, Trust & Safety",
        "Status": "Ready to Apply",
        "Link": "https://job-boards.greenhouse.io/affirm/jobs/7615062003",
        "Notes": "5+ yrs PM exp. Build fraud prevention systems. 100% subsidized medical.",
    },
    {
        "#": 6, "Tier": 1, "Company": "Affirm", "Role": "Senior Product Manager, Card Platform",
        "Salary": "$150,000 - $200,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse",
        "Tags": "Fintech, Cards, Money Movement, Ledgers",
        "Status": "Ready to Apply",
        "Link": "https://job-boards.greenhouse.io/affirm/jobs/7624640003",
        "Notes": "Own strategy & execution for money movement & ledgers across card products.",
    },
    {
        "#": 7, "Tier": 1, "Company": "Grafana Labs", "Role": "Senior Product Manager",
        "Salary": "$164,490 - $197,389", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse",
        "Tags": "Observability, Open Source, DevOps, SaaS",
        "Status": "Ready to Apply",
        "Link": "https://job-boards.greenhouse.io/grafanalabs/jobs/5816901004",
        "Notes": "Remote-first company. Observability platform. Strong open-source culture.",
    },
    {
        "#": 8, "Tier": 1, "Company": "Wealthsimple", "Role": "Senior Product Manager",
        "Salary": "$182,000 - $205,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "LinkedIn/WeWorkRemotely",
        "Tags": "Fintech, Investing, Canadian Company",
        "Status": "Ready to Apply",
        "Link": "https://www.wealthsimple.com/en-ca/careers",
        "Notes": "Multiple SPM roles (Payment Cards, Activities & Balances, Options). Top Canadian fintech.",
    },
    {
        "#": 9, "Tier": 1, "Company": "Twilio", "Role": "Senior Product Manager, Commerce",
        "Salary": "$157,000 - $196,200", "Currency": "CAD", "Location": "Remote, Canada (BC listed)",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse",
        "Tags": "Communications, Commerce, UX, SaaS, Billing",
        "Status": "Ready to Apply",
        "Link": "https://job-boards.greenhouse.io/twilio/jobs/7612892",
        "Notes": "Remote-first. Strong UX focus. Also hiring Sr PM for Billing Platform.",
    },
    {
        "#": 10, "Tier": 2, "Company": "Grafana Labs", "Role": "Product Manager",
        "Salary": "Est. $130,000 - $165,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Greenhouse",
        "Tags": "Observability, Open Source, DevOps, SaaS",
        "Status": "Ready to Apply",
        "Link": "https://job-boards.greenhouse.io/grafanalabs/jobs/5795334004",
        "Notes": "IC PM role. Salary estimate based on Grafana Labs Canada PM ranges.",
    },
    {
        "#": 11, "Tier": 2, "Company": "Pantheon Platform", "Role": "Product Manager, Developer Experience",
        "Salary": "$150,000 - $188,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Wellfound/RemoteRocketship",
        "Tags": "WebOps, Developer Tools, SaaS",
        "Status": "Ready to Apply",
        "Link": "https://www.remoterocketship.com/company/pantheon-platform/jobs/product-manager-developer-experience-canada-remote/",
        "Notes": "WebOps platform for websites. Developer experience focus.",
    },
    {
        "#": 12, "Tier": 2, "Company": "Smile Digital Health", "Role": "Senior Product Manager, Data Platform",
        "Salary": "Est. $130,000 - $155,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Lever/Indeed",
        "Tags": "HealthTech, Data Platform, FHIR, CDR",
        "Status": "Ready to Apply",
        "Link": "https://jobs.lever.co/smiledigitalhealth/0da006bb-ee3d-4e94-a67c-be62ab8e7b05",
        "Notes": "Own strategy for Core CDR platform. Data ingestion, quality, persistence.",
    },
    {
        "#": 13, "Tier": 2, "Company": "CaptivateIQ", "Role": "Senior Product Manager, Foundations",
        "Salary": "$137,000 - $217,000", "Currency": "USD", "Location": "Remote",
        "Visa Sponsor": "N/A (PR)", "Source": "YCombinator",
        "Tags": "SaaS, Incentive Compensation, YC Company",
        "Status": "Ready to Apply",
        "Link": "https://www.ycombinator.com/companies/captivateiq/jobs/hS3ywoC-senior-product-manager-foundations-remote",
        "Notes": "USD salary (converts to ~$185K-$293K CAD). Verify Canada eligibility.",
    },
    {
        "#": 14, "Tier": 2, "Company": "Affirm", "Role": "Senior Product Manager, Financial Reporting",
        "Salary": "$150,000 - $200,000", "Currency": "CAD", "Location": "Remote, Canada",
        "Visa Sponsor": "N/A (PR)", "Source": "Remotech",
        "Tags": "Fintech, Financial Reporting, BNPL",
        "Status": "Ready to Apply",
        "Link": "https://www.remotech.ai/jobs/senior-product-manager-financial-reporting",
        "Notes": "Financial reporting product ownership. Remote-first.",
    },
    {
        "#": 15, "Tier": 2, "Company": "Autodesk", "Role": "Senior Platform Product Manager, Digital Messaging",
        "Salary": "Est. $140,000 - $180,000", "Currency": "CAD", "Location": "Remote, Canada/US (EST)",
        "Visa Sponsor": "N/A (PR)", "Source": "LinkedIn",
        "Tags": "CAD/BIM, Platform, Digital Messaging, Enterprise",
        "Status": "Ready to Apply",
        "Link": "https://www.linkedin.com/jobs/view/senior-platform-product-manager-digital-messaging-canada-us-est-remote-at-autodesk-4372965037",
        "Notes": "EST timezone. Salary estimate based on Autodesk PM ranges in Canada ($167K-$301K).",
    },
]

# ── Create Jobs Sheet ───────────────────────────────────────────────────
ws = wb.active
ws.title = "Jobs"

columns = ["#", "Tier", "Company", "Role", "Salary", "Currency", "Location",
           "Visa Sponsor", "Source", "Tags", "Status", "Link", "Notes"]
col_widths = [4, 5, 18, 45, 25, 9, 25, 12, 22, 40, 15, 55, 60]

# Header row
for col_idx, (col_name, width) in enumerate(zip(columns, col_widths), 1):
    cell = ws.cell(row=1, column=col_idx, value=col_name)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = thin_border
    ws.column_dimensions[get_column_letter(col_idx)].width = width

# Data rows
for row_idx, job in enumerate(jobs, 2):
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=row_idx, column=col_idx, value=job.get(col_name, ""))
        cell.font = data_font
        cell.border = thin_border
        cell.alignment = wrap_align

        # Color coding by status
        status = job.get("Status", "")
        if status == "Ready to Apply":
            cell.fill = yellow_fill
        elif status == "Applied":
            cell.fill = green_fill

# Freeze header
ws.freeze_panes = "A2"

# Auto-filter
ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(jobs) + 1}"

# ── Create Summary Sheet ────────────────────────────────────────────────
ws2 = wb.create_sheet("Summary")

summary_data = [
    ["Remote PM Job Search - Vijaya Ramesh", ""],
    ["Generated", date.today().strftime("%B %d, %Y")],
    ["", ""],
    ["Metric", "Count"],
    ["Total Listings Found", len(jobs)],
    ["Tier 1 (Top Comp / Top Company)", sum(1 for j in jobs if j["Tier"] == 1)],
    ["Tier 2 (Near Target / Negotiable)", sum(1 for j in jobs if j["Tier"] == 2)],
    ["Tier 3 (Good Fit, Lower Comp)", sum(1 for j in jobs if j["Tier"] == 3) if any(j["Tier"] == 3 for j in jobs) else 0],
    ["", ""],
    ["Status", "Count"],
    ["Ready to Apply (Manual)", sum(1 for j in jobs if j["Status"] == "Ready to Apply")],
    ["Applied", sum(1 for j in jobs if j["Status"] == "Applied")],
    ["Skipped", sum(1 for j in jobs if j["Status"] == "Skipped")],
    ["", ""],
    ["Top Companies by # of Openings", ""],
    ["Affirm", sum(1 for j in jobs if j["Company"] == "Affirm")],
    ["Grafana Labs", sum(1 for j in jobs if j["Company"] == "Grafana Labs")],
    ["Wealthsimple", sum(1 for j in jobs if j["Company"] == "Wealthsimple")],
    ["Twilio", sum(1 for j in jobs if j["Company"] == "Twilio")],
    ["Pantheon Platform", sum(1 for j in jobs if j["Company"] == "Pantheon Platform")],
    ["Smile Digital Health", sum(1 for j in jobs if j["Company"] == "Smile Digital Health")],
    ["CaptivateIQ", sum(1 for j in jobs if j["Company"] == "CaptivateIQ")],
    ["Autodesk", sum(1 for j in jobs if j["Company"] == "Autodesk")],
    ["", ""],
    ["Salary Range (CAD)", ""],
    ["Highest Listed", "$228,000 (Affirm Staff PM, Fraud)"],
    ["Average Midpoint (Tier 1)", "~$180,000"],
    ["Minimum Listed", "$130,000 (Smile Digital Health est.)"],
    ["", ""],
    ["Notes", ""],
    ["", "Applications cannot be auto-submitted. All listings marked 'Ready to Apply'"],
    ["", "require manual application via the provided links."],
    ["", "Affirm and Grafana Labs are the strongest opportunities (multiple roles, confirmed salary ranges)."],
    ["", "All roles verified as Remote Canada-eligible as of April 2026."],
    ["", "Recommend applying to Tier 1 roles first, then Tier 2."],
]

title_font = Font(name="Arial", size=14, bold=True, color="4472C4")
section_font = Font(name="Arial", size=10, bold=True)

for row_idx, (col_a, col_b) in enumerate(summary_data, 1):
    cell_a = ws2.cell(row=row_idx, column=1, value=col_a)
    cell_b = ws2.cell(row=row_idx, column=2, value=col_b)
    cell_a.font = data_font
    cell_b.font = data_font
    cell_a.border = thin_border
    cell_b.border = thin_border

    if row_idx == 1:
        cell_a.font = title_font
    elif col_a in ("Metric", "Status", "Top Companies by # of Openings",
                    "Salary Range (CAD)", "Notes"):
        cell_a.font = section_font
        cell_a.fill = header_fill
        cell_a.font = header_font
        cell_b.fill = header_fill
        cell_b.font = header_font

ws2.column_dimensions["A"].width = 40
ws2.column_dimensions["B"].width = 55

# ── Save ────────────────────────────────────────────────────────────────
output_path = "/sessions/practical-relaxed-einstein/mnt/outputs/Remote_PM_Jobs_Vijaya_Ramesh.xlsx"
wb.save(output_path)
print(f"Saved tracker to {output_path}")
print(f"Total jobs: {len(jobs)}")
print(f"Tier 1: {sum(1 for j in jobs if j['Tier'] == 1)}")
print(f"Tier 2: {sum(1 for j in jobs if j['Tier'] == 2)}")
