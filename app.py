# streamlit_app.py
# Streamlit Dashboard: Donor / Program Team / Vendor
# Option C folder layout: Uploads/Donor, Uploads/ProgramTeam, Uploads/Vendor
#
# Deploy on Streamlit Cloud:
# - Add SERVICE_ACCOUNT_JSON in Secrets (full JSON)
# - Add SHEET_DONOR, WORKSHEET_DONOR, SHEET_PROGRAM_URL (optional), WORKSHEET_PROGRAM,
#   SHEET_VENDOR, WORKSHEET_VENDOR
# - Add DRIVE_ROOT_FOLDER_ID (optional). If not present the app will create Uploads root in Drive.
# - Add SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS if you want email sending
# - Add ADMIN_PASSWORD for a simple login gate (optional)
#
# Run locally:
#   pip install -r requirements.txt
#   streamlit run streamlit_app.py

import os
import io
import json
import time
import datetime
import tempfile
import smtplib
from email.message import EmailMessage
from pathlib import Path

import streamlit as st
import gspread
import pandas as pd
from fpdf import FPDF

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Agastya Dashboard", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Sheet defaults (change via Secrets or Env)
SHEET_DONOR = st.secrets.get("SHEET_DONOR", os.environ.get("SHEET_DONOR", "AgastyaInternationalFoundation"))
WORKSHEET_DONOR = st.secrets.get("WORKSHEET_DONOR", os.environ.get("WORKSHEET_DONOR", "Donar"))

SHEET_PROGRAM_URL = st.secrets.get("SHEET_PROGRAM_URL", os.environ.get("SHEET_PROGRAM_URL", ""))
WORKSHEET_PROGRAM = st.secrets.get("WORKSHEET_PROGRAM", os.environ.get("WORKSHEET_PROGRAM", "ProgramTeam"))

SHEET_VENDOR = st.secrets.get("SHEET_VENDOR", os.environ.get("SHEET_VENDOR", "AgastyaInternationalFoundation"))
WORKSHEET_VENDOR = st.secrets.get("WORKSHEET_VENDOR", os.environ.get("WORKSHEET_VENDOR", "Vendorsheet"))

# Drive root folder id (optional) - if not set, app will create a folder named "Uploads" in Drive.
DRIVE_ROOT_FOLDER_ID = st.secrets.get("DRIVE_ROOT_FOLDER_ID", os.environ.get("DRIVE_ROOT_FOLDER_ID"))

# Simple auth (optional)
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin"))

# local uploads cache (if desired)
UPLOAD_DIR = Path("uploaded_vendor_images")
UPLOAD_DIR.mkdir(exist_ok=True)

# -------------------- AUTH HELPERS --------------------
@st.cache_resource
def load_service_account():
    """
    Returns credentials object and JSON dict
    """
    # Try Streamlit secrets first
    sa_json = None
    if "SERVICE_ACCOUNT_JSON" in st.secrets:
        sa_json = st.secrets["SERVICE_ACCOUNT_JSON"]
    else:
        sa_json = os.environ.get("SERVICE_ACCOUNT_JSON")
    if not sa_json:
        return None, "SERVICE_ACCOUNT_JSON not found. Set in Streamlit Secrets."
    try:
        sa = json.loads(sa_json)
    except Exception as e:
        return None, f"Failed to parse SERVICE_ACCOUNT_JSON: {e}"
    # write to temp file for google libs
    fd, tmp = tempfile.mkstemp(prefix="sa-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(sa, f)
    creds = Credentials.from_service_account_file(tmp, scopes=SCOPES)
    return creds, None

creds, cred_err = load_service_account()
if cred_err:
    st.warning("Google credentials not configured: " + cred_err)
    ALLOW_SHEETS = False
else:
    ALLOW_SHEETS = True
    # initialize clients
    gs_client = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

# -------------------- DRIVE HELPERS --------------------
def find_drive_folder(name, parent_id=None):
    """Return folder id if exists, else None"""
    q = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    res = drive_service.files().list(q=q, fields="files(id,name)").execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None

def create_drive_folder(name, parent_id=None):
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    file = drive_service.files().create(body=metadata, fields="id").execute()
    return file.get("id")

def ensure_folder_path(root_id=None):
    """Ensure Uploads/Donor, Uploads/ProgramTeam, Uploads/Vendor exist. Returns dict of ids."""
    # root folder "Uploads"
    folder_ids = {}
    root = root_id
    if not root:
        # try to find Uploads at top-level
        root = find_drive_folder("Uploads")
        if not root:
            root = create_drive_folder("Uploads")
    # subfolders
    for sub in ["Donor", "ProgramTeam", "Vendor"]:
        fid = find_drive_folder(sub, parent_id=root)
        if not fid:
            fid = create_drive_folder(sub, parent_id=root)
        folder_ids[sub] = fid
    return root, folder_ids

def upload_file_to_drive(file_bytes, filename, mimetype, parent_folder_id):
    fh = io.BytesIO(file_bytes)
    media = MediaIoBaseUpload(fh, mimetype=mimetype, resumable=True)
    metadata = {"name": filename, "parents": [parent_folder_id]}
    file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()
    return file.get("id")

# -------------------- GOOGLE SHEETS HELPERS --------------------
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

# -------------------- PDF / Email HELPERS --------------------
def generate_invoice_pdf(invoice_lines: list, vendor_name: str):
    """Generate simple invoice PDF (in memory) and return bytes."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Invoice - {vendor_name}", ln=True)
    pdf.ln(4)
    pdf.set_font("Arial", "", 12)
    # header
    pdf.cell(60, 10, "Version", 1)
    pdf.cell(40, 10, "Language", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(30, 10, "Unit", 1)
    pdf.cell(30, 10, "Amount", 1, ln=True)
    total = 0
    for it in invoice_lines:
        pdf.cell(60, 10, str(it.get("version", ""))[:30], 1)
        pdf.cell(40, 10, str(it.get("language", ""))[:18], 1)
        pdf.cell(30, 10, str(it.get("qty", "")), 1)
        pdf.cell(30, 10, str(it.get("unit_price", "")), 1)
        pdf.cell(30, 10, str(it.get("amount", "")), 1, ln=True)
        total += float(it.get("amount", 0))
    pdf.ln(6)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Total: {total}", ln=True)
    out = pdf.output(dest="S").encode("latin1")
    return out

def send_email_with_attachment(smtp_host, smtp_port, username, password, to_email, subject, body, attachment_bytes=None, attachment_name=None):
    msg = EmailMessage()
    msg["From"] = username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if attachment_bytes and attachment_name:
        msg.add_attachment(attachment_bytes, maintype="application", subtype="pdf", filename=attachment_name)
    server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
    server.starttls()
    server.login(username, password)
    server.send_message(msg)
    server.quit()

# -------------------- UI & MODULES --------------------
# simple login gate
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def show_login():
    st.sidebar.title("Login")
    pw = st.sidebar.text_input("Admin password", type="password")
    if st.sidebar.button("Login"):
        if pw == ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.sidebar.success("Authenticated")
        else:
            st.sidebar.error("Wrong password")

if not st.session_state.authenticated:
    show_login()
    st.title("Agastya Dashboard (Streamlit)")
    st.write("Please log in from the left sidebar to use the dashboard.")
    st.stop()

# ensure Drive folders (once)
if ALLOW_SHEETS:
    try:
        ROOT_ID, SUBFOLDERS = ensure_folder_path(DRIVE_ROOT_FOLDER_ID)
    except Exception as e:
        st.error("Drive initialization error: " + str(e))
        ALLOW_SHEETS = False
        SUBFOLDERS = {}
else:
    SUBFOLDERS = {}

st.title("Agastya - Unified Dashboard")
st.write("Choose a module below:")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🧾 Donor Menu", key="btn_donor", use_container_width=True):
        st.session_state.active = "donor"
with col2:
    if st.button("📋 Program Team", key="btn_program", use_container_width=True):
        st.session_state.active = "program"
with col3:
    if st.button("🏷 Vendor Management", key="btn_vendor", use_container_width=True):
        st.session_state.active = "vendor"

active = st.session_state.get("active", "donor")

# ---------- DONOR ----------
def donor_module():
    st.header("Donor Menu")
    ws, err = (open_ws_by_title_or_url(gs_client, title=SHEET_DONOR, worksheet=WORKSHEET_DONOR) if ALLOW_SHEETS else (None, "Sheets disabled"))
    if err and ALLOW_SHEETS:
        st.error("Donor sheet error: " + err)

    sub = st.radio("Action", ["Add New Donor", "Select / Update Donor"])
    if sub == "Add New Donor":
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
                       cost_per_unique_child, cost_per_exposure, donor_relation, poc, project_id]
                if not ALLOW_SHEETS:
                    st.info("Sheets not available — preview only.")
                    st.write(row)
                else:
                    try:
                        ws.append_row(row)
                        st.success("Donor saved to sheet.")
                    except Exception as e:
                        st.error("Save failed: " + str(e))
    else:
        # select donor
        if not ALLOW_SHEETS:
            st.info("Sheets not configured.")
            return
        try:
            records = ws.get_all_values()
            donors = [r[0] for r in records[1:] if r]
        except Exception as e:
            st.error("Load donors failed: " + str(e))
            return
        if not donors:
            st.info("No donors found.")
            return
        sel = st.selectbox("Select donor", donors)
        idx = donors.index(sel) + 2
        row_vals = ws.row_values(idx)
        headers = records[0]
        st.write("Edit fields and click Update")
        updated = []
        for i, h in enumerate(headers):
            val = row_vals[i] if i < len(row_vals) else ""
            updated.append(st.text_input(h, value=val, key=f"donor_{i}"))
        if st.button("Update Donor"):
            try:
                ws.update(f"A{idx}:I{idx}", [updated])
                st.success("Donor updated.")
            except Exception as e:
                st.error("Update failed: " + str(e))

# ---------- PROGRAM ----------
def program_module():
    st.header("Program Team")
    ws, err = (open_ws_by_title_or_url(gs_client, url=SHEET_PROGRAM_URL, worksheet=WORKSHEET_PROGRAM) if (ALLOW_SHEETS and SHEET_PROGRAM_URL)
               else (open_ws_by_title_or_url(gs_client, title=SHEET_DONOR, worksheet=WORKSHEET_PROGRAM) if ALLOW_SHEETS else (None, "Sheets disabled")))
    if err and ALLOW_SHEETS:
        st.error("Program sheet error: " + err)

    tab = st.radio("Mode", ["Enter Data", "View Data"])
    regions = ["N1", "N2", "Gujarat", "MH1", "NK2", "NK2SK1", "SK2", "Tamilnadu", "APTS", "Kupam"]
    versions = ["Actilearn 1.0", "Actilearn Junior", "Papertronics", "ISEE", "Financial Literacy", "Plastic Smart", "ClimateQuest", "Chemagica"]
    languages = ["Hindi", "English", "Kannada", "Tamil", "Telugu", "Malayalam", "Marathi", "Gujarati", "Punjabi", "Bengali", "Odia", "Urdu"]

    if tab == "Enter Data":
        region = st.selectbox("Region", regions)
        version = st.selectbox("Version", versions)
        language = st.selectbox("Language", languages)
        qty = st.text_input("Quantity")
        grade = st.text_input("Grade")
        total = st.text_input("Total")
        poc = st.text_input("Point of Contact (POC)", value="example@gmail.com")
        lr = st.file_uploader("LR Image (optional)", type=["png", "jpg", "jpeg"])
        if st.button("Save"):
            if not all([region, version, language, qty, grade, total, poc]):
                st.warning("All fields required.")
            elif not (qty.isdigit() and grade.isdigit() and total.isdigit()):
                st.warning("Quantity/Grade/Total must be numbers.")
            else:
                lr_fname = ""
                if lr:
                    # upload to Drive ProgramTeam folder
                    if ALLOW_SHEETS and SUBFOLDERS.get("ProgramTeam"):
                        content = lr.read()
                        fname = f"{int(time.time())}_{lr.name}"
                        fid = upload_file_to_drive(content, fname, "image/jpeg", SUBFOLDERS["ProgramTeam"])
                        lr_fname = fname + f" (drive id:{fid})"
                row = [region, version, language, qty, grade, total, poc, lr_fname]
                if not ALLOW_SHEETS:
                    st.info("Preview only: " + str(row))
                else:
                    try:
                        ws.append_row(row)
                        st.success("Program entry saved.")
                    except Exception as e:
                        st.error("Save failed: " + str(e))
    else:
        if not ALLOW_SHEETS:
            st.info("Sheets not configured.")
            return
        try:
            data = ws.get_all_records()
            df = pd.DataFrame(data)
            st.dataframe(df)
        except Exception as e:
            st.error("Load failed: " + str(e))

# ---------- VENDOR ----------
def vendor_module():
    st.header("Vendor Management")
    # invoice lines in session
    if "invoice_items" not in st.session_state:
        st.session_state.invoice_items = []

    vendor_name = st.text_input("Vendor Name")
    notes = st.text_area("Notes / Manual ID")
    pan = st.text_input("PAN")
    gst = st.text_input("GST")
    version = st.selectbox("Version", ["Actilearn 1.0", "Actilearn Junior", "Papertronics", "ISEE", "Financial Literacy", "Plastic Smart", "ClimateQuest", "Chemagica"])
    language = st.selectbox("Language", ["English","Hindi","Kannada","Tamil","Telugu","Malayalam","Marathi","Gujarati"])
    qty = st.text_input("Quantity")
    pan_img = st.file_uploader("PAN image", type=["png","jpg","jpeg"], key="pan")
    gst_img = st.file_uploader("GST image", type=["png","jpg","jpeg"], key="gst")

    if st.button("Add / Update Line"):
        if not (vendor_name and pan and gst and version and language and qty):
            st.warning("All fields required.")
        elif not qty.isdigit():
            st.warning("Quantity must be integer.")
        else:
            qty_i = int(qty)
            PRICE_MAP = {"Actilearn 1.0":250,"Actilearn Junior":180,"Papertronics":220,"ISEE":300,"Financial Literacy":200,"Plastic Smart":150,"ClimateQuest":275,"Chemagica":230}
            unit = PRICE_MAP.get(version, 200)
            amt = qty_i * unit
            pan_fname = ""
            gst_fname = ""
            # upload images to Drive
            if pan_img and ALLOW_SHEETS and SUBFOLDERS.get("Vendor"):
                content = pan_img.read()
                pan_fname = f"{int(time.time())}_{pan_img.name}"
                pan_id = upload_file_to_drive(content, pan_fname, "image/jpeg", SUBFOLDERS["Vendor"])
                pan_fname = pan_fname + f" (drive id:{pan_id})"
            if gst_img and ALLOW_SHEETS and SUBFOLDERS.get("Vendor"):
                content = gst_img.read()
                gst_fname = f"{int(time.time())}_{gst_img.name}"
                gst_id = upload_file_to_drive(content, gst_fname, "image/jpeg", SUBFOLDERS["Vendor"])
                gst_fname = gst_fname + f" (drive id:{gst_id})"
            entry = {"timestamp": datetime.datetime.now().isoformat(), "vendor": vendor_name, "notes": notes, "pan": pan, "gst": gst, "version": version, "language": language, "qty": qty_i, "unit_price": unit, "amount": amt, "pan_img": pan_fname, "gst_img": gst_fname}
            st.session_state.invoice_items.append(entry)
            st.success("Line added to invoice preview.")

    st.subheader("Invoice preview")
    if st.session_state.invoice_items:
        for i, it in enumerate(st.session_state.invoice_items, start=1):
            st.write(f"{i}. {it['version']} | {it['language']} | Qty {it['qty']} | Amount {it['amount']}")
            if it.get("pan_img"):
                st.write("PAN:", it["pan_img"])
            if it.get("gst_img"):
                st.write("GST:", it["gst_img"])
    else:
        st.info("No invoice lines yet.")

    if st.button("Submit all to Google Sheets (and optionally email invoice)"):
        if not st.session_state.invoice_items:
            st.info("No lines to submit.")
        else:
            # append rows to sheet
            if not ALLOW_SHEETS:
                st.info("Sheets not configured. Preview only.")
            else:
                try:
                    ws_v, err = open_ws_by_title_or_url(gs_client, title=SHEET_VENDOR, worksheet=WORKSHEET_VENDOR)
                    if err:
                        st.error("Could not open vendor sheet: " + err)
                        return
                    for it in st.session_state.invoice_items:
                        ws_v.append_row([it["timestamp"], it["vendor"], it["notes"], it["pan"], it["gst"], it["version"], it["language"], it["qty"], it["unit_price"], it["amount"], it["pan_img"], it["gst_img"]])
                    st.success("All lines saved to Vendorsheet.")
                except Exception as e:
                    st.error("Save failed: " + str(e))
                    return

            # generate invoice pdf
            pdf_bytes = generate_invoice_pdf(st.session_state.invoice_items, vendor_name or "Vendor")
            # save to Drive inside Vendor folder as invoice pdf
            if ALLOW_SHEETS and SUBFOLDERS.get("Vendor"):
                fname = f"invoice_{int(time.time())}_{(vendor_name or 'vendor')}.pdf"
                fid = upload_file_to_drive(pdf_bytes, fname, "application/pdf", SUBFOLDERS["Vendor"])
                st.success(f"Invoice PDF uploaded to Drive (id: {fid}).")

            # optionally email: check secrets
            smtp_host = st.secrets.get("SMTP_HOST", os.environ.get("SMTP_HOST"))
            smtp_port = int(st.secrets.get("SMTP_PORT", os.environ.get("SMTP_PORT", 587))) if (st.secrets.get("SMTP_PORT", None) or os.environ.get("SMTP_PORT", None)) else 587
            smtp_user = st.secrets.get("SMTP_USER", os.environ.get("SMTP_USER"))
            smtp_pass = st.secrets.get("SMTP_PASS", os.environ.get("SMTP_PASS"))
            send_to = st.text_input("Email to send invoice to (leave blank to skip)", value="")
            if send_to and smtp_host and smtp_user and smtp_pass:
                try:
                    send_email_with_attachment(smtp_host, smtp_port, smtp_user, smtp_pass, send_to, f"Invoice for {vendor_name or 'Vendor'}", "Please find invoice attached.", pdf_bytes, f"invoice_{vendor_name or 'vendor'}.pdf")
                    st.success("Email sent.")
                except Exception as e:
                    st.error("Email failed: " + str(e))

            # clear session invoice
            st.session_state.invoice_items = []

# Router
if active == "donor":
    donor_module()
elif active == "program":
    program_module()
elif active == "vendor":
    vendor_module()

st.write("---")
st.markdown("Built for Agastya International Foundation — Streamlit edition.")
