# streamlit_app.py
# Streamlit replacement for your Tkinter dashboard_all.py
# Usage:
#  - Locally: set SERVICE_ACCOUNT_JSON env var or use .streamlit/secrets.toml
#  - Streamlit Cloud: add SERVICE_ACCOUNT_JSON in Secrets (app settings)
#
# Run locally:
#   pip install -r requirements.txt
#   streamlit run streamlit_app.py

import os
import io
import json
import tempfile
import datetime
import re
from typing import List, Dict

import streamlit as st
from google.oauth2.service_account import Credentials
import gspread
from werkzeug.utils import secure_filename

# ---------- Config ----------
UPLOAD_DIR = os.path.join(os.getcwd(), "uploaded_vendor_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# default sheet names (override via Streamlit secrets or env)
SHEET_DONOR = st.secrets.get("SHEET_DONOR", os.environ.get("SHEET_DONOR", "AgastyaInternationalFoundation"))
WORKSHEET_DONOR = st.secrets.get("WORKSHEET_DONOR", os.environ.get("WORKSHEET_DONOR", "Donar"))

SHEET_PROGRAM_URL = st.secrets.get("SHEET_PROGRAM_URL", os.environ.get("SHEET_PROGRAM_URL", ""))
WORKSHEET_PROGRAM = st.secrets.get("WORKSHEET_PROGRAM", os.environ.get("WORKSHEET_PROGRAM", "ProgramTeam"))

SHEET_VENDOR = st.secrets.get("SHEET_VENDOR", os.environ.get("SHEET_VENDOR", "AgastyaInternationalFoundation"))
WORKSHEET_VENDOR = st.secrets.get("WORKSHEET_VENDOR", os.environ.get("WORKSHEET_VENDOR", "Vendorsheet"))

# ---------- Google Sheets authentication ----------
def get_service_account_json_path() -> (str | None):
    """
    Priority:
     1) st.secrets["SERVICE_ACCOUNT_JSON"]
     2) env var SERVICE_ACCOUNT_JSON
     3) env var SERVICE_ACCOUNT_FILE (a path in repo)
    Returns path to temp JSON file or None
    """
    # 1) Streamlit secrets
    sa_json = None
    if "SERVICE_ACCOUNT_JSON" in st.secrets:
        sa_json = st.secrets["SERVICE_ACCOUNT_JSON"]
    # 2) env var
    if not sa_json:
        sa_json = os.environ.get("SERVICE_ACCOUNT_JSON")

    if sa_json:
        fd, tmp = tempfile.mkstemp(prefix="sa-", suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write(sa_json)
        return tmp

    # 3) file path env var
    file_path = os.environ.get("SERVICE_ACCOUNT_FILE")
    if file_path and os.path.exists(file_path):
        return file_path

    return None

@st.cache_resource
def init_gspread_client():
    path = get_service_account_json_path()
    if not path:
        return None, "No service account JSON found. Put it in Streamlit Secrets as SERVICE_ACCOUNT_JSON or set SERVICE_ACCOUNT_FILE env var."
    try:
        creds = Credentials.from_service_account_file(path, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client, None
    except Exception as e:
        return None, str(e)

gclient, gerr = init_gspread_client()

def open_ws_by_title_or_url(client, title=None, url=None, worksheet=None):
    try:
        if url:
            sh = client.open_by_url(url)
        else:
            sh = client.open(title)
        ws = sh.worksheet(worksheet)
        return ws, None
    except Exception as e:
        return None, str(e)

# ---------- Helpers ----------
def show_error(msg: str):
    st.error(msg)

def show_success(msg: str):
    st.success(msg)

def save_uploaded_file(uploaded_file, dest_folder=UPLOAD_DIR):
    if not uploaded_file:
        return ""
    ts = int(datetime.datetime.now().timestamp())
    safe_name = secure_filename(uploaded_file.name)
    fname = f"{ts}_{safe_name}"
    dest_path = os.path.join(dest_folder, fname)
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return fname

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Unified Dashboard", layout="wide")
st.title("Unified Dashboard — Donor / Program Team / Vendor")

if not gclient:
    st.warning("Google Sheets not configured: " + (gerr or "unknown"))
    st.info("Provide service account JSON as Streamlit secret SERVICE_ACCOUNT_JSON, then redeploy. Also share target sheets with that service-account email.")
    # still allow local testing (UI flows) but disable sheet writes
    allow_sheets = False
else:
    allow_sheets = True

tab = st.tabs(["Dashboard", "Donor", "Program Team", "Vendor"])
# ---------------- Dashboard ----------------
with tab[0]:
    st.header("Navigation")
    st.markdown("""
    - Donor: add / view donors (writes to the 'Donar' worksheet)
    - Program Team: add / view program entries
    - Vendor: build invoice lines, upload PAN/GST images, submit to Vendorsheet
    """)
    st.write("Sheet config (can override in Streamlit secrets or env):")
    st.write(f"- SHEET_DONOR: **{SHEET_DONOR}**  | WORKSHEET_DONOR: **{WORKSHEET_DONOR}**")
    st.write(f"- SHEET_PROGRAM_URL: **{SHEET_PROGRAM_URL or '(not set)'}**  | WORKSHEET_PROGRAM: **{WORKSHEET_PROGRAM}**")
    st.write(f"- SHEET_VENDOR: **{SHEET_VENDOR}**  | WORKSHEET_VENDOR: **{WORKSHEET_VENDOR}**")

# ---------------- Donor ----------------
with tab[1]:
    st.header("Donor Menu")
    with st.form("donor_form"):
        dn = st.text_input("Donor Name")
        version_book = st.text_input("Version Book")
        total_unique_child = st.text_input("Total Unique Child")
        total_exposure = st.text_input("Total Exposure")
        cost_per_unique_child = st.text_input("Cost per Unique Child")
        cost_per_exposure = st.text_input("Cost per Exposure")
        donor_relation = st.text_input("Donor Relation")
        poc = st.text_input("Point of Contact")
        project_id = st.text_input("Project ID")
        submitted = st.form_submit_button("Save Donor")
    if submitted:
        if not dn:
            st.warning("Donor Name is required.")
        else:
            row = [dn, version_book, total_unique_child, total_exposure,
                   cost_per_unique_child, cost_per_exposure, donor_relation,
                   poc, project_id]
            if not allow_sheets:
                st.info("Sheet not configured — local preview only. Data: " + str(row))
            else:
                ws, err = open_ws_by_title_or_url(gclient, title=SHEET_DONOR, worksheet=WORKSHEET_DONOR)
                if err:
                    show_error("Could not open Donor worksheet: " + err)
                else:
                    try:
                        ws.append_row(row)
                        show_success(f"Donor '{dn}' saved to Google Sheet.")
                    except Exception as e:
                        show_error("Save failed: " + str(e))

    # list donors
    st.subheader("Existing donors")
    donors_list = []
    if allow_sheets:
        ws, err = open_ws_by_title_or_url(gclient, title=SHEET_DONOR, worksheet=WORKSHEET_DONOR)
        if err:
            st.info("Could not load donors: " + err)
        else:
            try:
                vals = ws.get_all_values()
                donors_list = [r[0] for r in vals[1:] if r]
            except Exception as e:
                st.info("Load error: " + str(e))
    if donors_list:
        st.write("\n".join(["- " + d for d in donors_list]))
    else:
        st.write("No donors found or sheet not available.")

# ---------------- Program Team ----------------
with tab[2]:
    st.header("Program Team")
    with st.form("program_form"):
        region = st.text_input("Region")
        version = st.text_input("Version")
        language = st.text_input("Language")
        qty = st.text_input("Quantity")
        grade = st.text_input("Grade")
        total = st.text_input("Total")
        poc2 = st.text_input("Point of Contact (POC)")
        lr = st.text_input("LR Path (optional)")
        prog_submit = st.form_submit_button("Save Program Entry")
    if prog_submit:
        if not all([region, version, language, qty, grade, total, poc2, lr]):
            st.warning("All fields must be filled (LR is considered required here to match prior code).")
        else:
            if not qty.isdigit() or not grade.isdigit() or not total.isdigit():
                st.warning("Quantity, Grade and Total must be numbers.")
            else:
                vals = [region, version, language, qty, grade, total, poc2, lr]
                if not allow_sheets:
                    st.info("Sheet not configured — local preview only. Data: " + str(vals))
                else:
                    ws, err = (open_ws_by_title_or_url(gclient, url=SHEET_PROGRAM_URL, worksheet=WORKSHEET_PROGRAM) if SHEET_PROGRAM_URL
                               else open_ws_by_title_or_url(gclient, title=SHEET_DONOR, worksheet=WORKSHEET_PROGRAM))
                    if err:
                        show_error("Could not open Program worksheet: " + err)
                    else:
                        try:
                            ws.append_row(vals)
                            show_success("Program entry saved.")
                        except Exception as e:
                            show_error("Save failed: " + str(e))
    # view rows
    st.subheader("Program entries (preview)")
    rows = []
    if allow_sheets:
        ws, err = (open_ws_by_title_or_url(gclient, url=SHEET_PROGRAM_URL, worksheet=WORKSHEET_PROGRAM) if SHEET_PROGRAM_URL
                   else open_ws_by_title_or_url(gclient, title=SHEET_DONOR, worksheet=WORKSHEET_PROGRAM))
        if not err:
            try:
                rows = ws.get_all_records()
            except Exception as e:
                st.info("Could not read rows: " + str(e))
    if rows:
        st.dataframe(rows)
    else:
        st.write("No rows or sheet unavailable.")

# ---------------- Vendor ----------------
with tab[3]:
    st.header("Vendor Management")
    if "invoice_items" not in st.session_state:
        st.session_state.invoice_items = []

    col1, col2 = st.columns(2)
    with col1:
        vendor_name = st.text_input("Vendor Name", key="vendor_name")
        pan = st.text_input("PAN")
        gst = st.text_input("GST")
        version_v = st.selectbox("Version", ["Actilearn 1.0", "Actilearn Junior", "Papertronics", "ISEE", "Financial Literacy", "Plastic Smart", "ClimateQuest", "Chemagica"], index=0)
        language_v = st.selectbox("Language", ["English","Hindi","Kannada","Tamil","Telugu","Malayalam","Marathi","Gujarati","Punjabi","Bengali","Odia","Assamese","Urdu"])
        qty_v = st.text_input("Quantity")
    with col2:
        pan_img = st.file_uploader("Upload PAN image", type=["png","jpg","jpeg","bmp"], key="pan_upload")
        gst_img = st.file_uploader("Upload GST image", type=["png","jpg","jpeg","bmp"], key="gst_upload")
        add_line = st.button("Add / Update Line")

    if add_line:
        if not (vendor_name and pan and gst and version_v and language_v and qty_v):
            st.warning("All fields required.")
        else:
            if not qty_v.isdigit():
                st.warning("Quantity must be integer.")
            else:
                q_i = int(qty_v)
                price_map = {"Actilearn 1.0":250,"Actilearn Junior":180,"Papertronics":220,"ISEE":300,"Financial Literacy":200,"Plastic Smart":150,"ClimateQuest":275,"Chemagica":230}
                unit = price_map.get(version_v, 200)
                amt = q_i * unit
                pan_fname = save_uploaded_file(pan_img) if pan_img else ""
                gst_fname = save_uploaded_file(gst_img) if gst_img else ""
                entry = {"timestamp": datetime.datetime.now().isoformat(),"vendor":vendor_name,"notes":"","pan":pan,"gst":gst,"version":version_v,"language":language_v,"qty":q_i,"unit_price":unit,"amount":amt,"pan_img":pan_fname,"gst_img":gst_fname}
                st.session_state.invoice_items.append(entry)
                show_success("Line added to invoice preview.")

    st.subheader("Invoice preview")
    if st.session_state.invoice_items:
        for i, it in enumerate(st.session_state.invoice_items, start=1):
            st.write(f"{i}. {it['version']} | {it['language']} | Qty {it['qty']} | Amount {it['amount']}  — PAN: {it['pan']} GST: {it['gst']}")
            if it.get("pan_img"):
                st.write("PAN image:", it["pan_img"])
            if it.get("gst_img"):
                st.write("GST image:", it["gst_img"])
    else:
        st.write("No invoice lines")

    if st.button("Submit all to Google Sheets"):
        if not st.session_state.invoice_items:
            st.info("No lines to submit.")
        else:
            if not allow_sheets:
                st.info("Sheet not configured — local preview only.")
            else:
                ws, err = open_ws_by_title_or_url(gclient, title=SHEET_VENDOR, worksheet=WORKSHEET_VENDOR)
                if err:
                    show_error("Could not open vendor worksheet: " + err)
                else:
                    try:
                        for it in st.session_state.invoice_items:
                            ws.append_row([it["timestamp"], it["vendor"], it["notes"], it["pan"], it["gst"], it["version"], it["language"], it["qty"], it["unit_price"], it["amount"], it["pan_img"], it["gst_img"]])
                        st.session_state.invoice_items = []
                        show_success("Submitted all vendor lines to Google Sheets.")
                    except Exception as e:
                        show_error("Submit failed: " + str(e))

    st.write("---")
    st.write("Uploaded images are stored in server folder:", UPLOAD_DIR)
