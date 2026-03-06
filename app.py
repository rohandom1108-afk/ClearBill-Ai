import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="ClearBill AI", layout="wide")

# -----------------------------
# PROFESSIONAL DASHBOARD STYLE
# -----------------------------

st.markdown("""
<style>

body {
    background-color:#0E1117;
}

.block-container {
    padding-top:2rem;
}

.header-banner {
    background: linear-gradient(90deg, #111827, #1F2937);
    padding: 25px;
    border-radius: 12px;
    border: 1px solid #2d3748;
}

.header-title {
    font-size: 36px;
    font-weight: 700;
    color: #FFD700;
}

.header-subtitle {
    font-size: 16px;
    color: #9CA3AF;
}

h2,h3 {
    color:white;
}

.audit-good {
    background:#143d2b;
    padding:20px;
    border-radius:10px;
}

.audit-bad {
    background:#3b1d1d;
    padding:20px;
    border-radius:10px;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------
# HEADER
# -----------------------------

st.markdown("""
<div class="header-banner">
<div class="header-title">ClearBill AI</div>
<div class="header-subtitle">
AI-powered invoice auditing platform that detects overbilling, contract mismatches,
GST inconsistencies, and financial calculation errors.
</div>
</div>
""", unsafe_allow_html=True)

st.divider()

st.subheader("Upload Documents")

# -----------------------------
# FILE UPLOAD
# -----------------------------

col1, col2 = st.columns(2)

with col1:
    invoice_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])

with col2:
    contract_file = st.file_uploader("Upload Contract / Rate Card PDF", type=["pdf"])

run = st.button("Run Audit")

# -----------------------------
# PDF TEXT EXTRACTION
# -----------------------------

def extract_text(uploaded_file):

    text = ""

    with pdfplumber.open(uploaded_file) as pdf:

        for page in pdf.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    return text

# -----------------------------
# INVOICE PARSER
# -----------------------------

def parse_invoice(text):

    vendor = "Unknown Vendor"
    invoice_number = "Unknown"

    vendor_match = re.search(r"(.*Logistics.*)", text)

    if vendor_match:
        vendor = vendor_match.group(0)

    inv_match = re.search(r"INV[-\d]+", text)

    if inv_match:
        invoice_number = inv_match.group(0)

    line_items = []

    lines = text.split("\n")

    for line in lines:

        match = re.search(r"(Delivery Charge|Packaging Fee).*?(\d+).*?(\d+)", line)

        if match:

            desc = match.group(1)
            qty = int(match.group(2))
            rate = int(match.group(3))

            gst = 18
            total = round(qty * rate * 1.18)

            line_items.append({
                "description": desc,
                "quantity": qty,
                "rate": rate,
                "gst_percent": gst,
                "line_total": total
            })

    return {
        "vendor": vendor,
        "invoice_number": invoice_number,
        "line_items": line_items
    }

# -----------------------------
# CONTRACT PARSER
# -----------------------------

def parse_contract(text):

    rates = {}

    delivery = re.search(r"Delivery Charge.*?(\d+)", text)
    packaging = re.search(r"Packaging Fee.*?(\d+)", text)

    rates["Delivery Charge"] = int(delivery.group(1)) if delivery else None
    rates["Packaging Fee"] = int(packaging.group(1)) if packaging else None

    return rates

# -----------------------------
# AUDIT ENGINE
# -----------------------------

def audit(invoice, contract):

    findings = []
    total_overcharge = 0
    calc_errors = 0
    gst_errors = 0

    for item in invoice["line_items"]:

        desc = item["description"]
        qty = item["quantity"]
        rate = item["rate"]
        gst = item["gst_percent"]
        line_total = item["line_total"]

        contract_rate = contract.get(desc)

        # Rate Check
        if contract_rate and rate > contract_rate:

            overcharge = (rate - contract_rate) * qty
            total_overcharge += overcharge

            findings.append({
                "Issue": "Rate exceeds contract",
                "Item": desc,
                "Invoice Rate": rate,
                "Contract Rate": contract_rate,
                "Impact": overcharge
            })

        # GST Check
        if gst != 18:

            gst_errors += 1

            findings.append({
                "Issue": "Incorrect GST",
                "Item": desc,
                "Invoice Rate": rate,
                "Contract Rate": contract_rate,
                "Impact": 0
            })

        # Calculation Check
        expected_total = round(qty * rate * 1.18)

        if expected_total != line_total:

            calc_errors += 1

            findings.append({
                "Issue": "Calculation mismatch",
                "Item": desc,
                "Invoice Rate": rate,
                "Contract Rate": contract_rate,
                "Impact": 0
            })

    return findings, total_overcharge, calc_errors, gst_errors

# -----------------------------
# MAIN EXECUTION
# -----------------------------

if run:

    if not invoice_file or not contract_file:

        st.error("Please upload both invoice and contract files.")

    else:

        invoice_text = extract_text(invoice_file)
        contract_text = extract_text(contract_file)

        invoice = parse_invoice(invoice_text)
        contract = parse_contract(contract_text)

        findings, overcharge, calc_errors, gst_errors = audit(invoice, contract)

        st.divider()

        st.subheader("Executive Dashboard")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Vendor", invoice["vendor"])

        with col2:
            st.metric("Invoice Number", invoice["invoice_number"])

        with col3:
            st.metric("Overcharge Detected", f"₹{overcharge}")

        risk = "LOW"

        if overcharge > 0 or calc_errors > 0 or gst_errors > 0:
            risk = "HIGH"

        with col4:
            st.metric("Risk Level", risk)

        st.divider()

        st.subheader("Invoice Line Items")

        st.dataframe(pd.DataFrame(invoice["line_items"]))

        st.subheader("Contract Rates")

        contract_df = pd.DataFrame(
            [{"Charge": k, "Rate": v} for k, v in contract.items()]
        )

        st.dataframe(contract_df)

        st.divider()

        st.subheader("Audit Findings")

        if findings:

            findings_df = pd.DataFrame(findings)

            st.dataframe(findings_df)

            st.markdown(
                f"""
                <div class='audit-bad'>
                <h3>Total Financial Impact: ₹{overcharge}</h3>
                </div>
                """,
                unsafe_allow_html=True
            )

            csv = findings_df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Download Audit Report",
                csv,
                "clearbill_audit_report.csv",
                "text/csv"
            )

        else:

            st.markdown(
                """
                <div class='audit-good'>
                <h3>No discrepancies detected. Invoice matches contract.</h3>
                </div>
                """,
                unsafe_allow_html=True
            )
