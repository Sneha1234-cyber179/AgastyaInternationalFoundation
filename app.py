"""
Flask web replacement for your Tkinter `dashboard_all.py`.
Single-file deployable app (templates embedded with render_template_string) so you can deploy to Render immediately.

Features implemented:
- /           : Main dashboard with links to modules
- /donor      : View donors, add donor
- /program    : Program team form + view
- /vendor     : Vendor invoice builder, upload images, submit to sheet

Google Sheets auth:
- The app will look for either:
  1) An environment variable named SERVICE_ACCOUNT_JSON containing the full JSON key as a string, OR
  2) A file path set in SERVICE_ACCOUNT_FILE pointing to a JSON key file in the repo.

On startup the app writes SERVICE_ACCOUNT_JSON to a temp file (if provided) and uses it.

Deployment (Render):
- Build command: pip install -r requirements.txt
- Start command: gunicorn app:app
- Add ENV (on Render) for SERVICE_ACCOUNT_JSON: paste the JSON key contents (or upload file in repo and set SERVICE_ACCOUNT_FILE to its path)

requirements.txt (minimum):
Flask
gunicorn
gspread
google-auth
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
pandas

Save this file as app.py in your repo root, add requirements.txt and deploy.
"""

from flask import Flask, request, redirect, url_for, render_template_string, flash, send_from_directory
import os
import tempfile
import json
from werkzeug.utils import secure_filename
import datetime

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

# Configuration
UPLOAD_DIR = os.path.join(os.getcwd(), "uploaded_vendor_images")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Helper: initialize gspread client from env or file
def init_gspread_client(json_env_var='SERVICE_ACCOUNT_JSON', file_env_var='SERVICE_ACCOUNT_FILE'):
    json_path = None
    # If user provided JSON string in ENV
    json_str = os.environ.get(json_env_var)
    if json_str:
        # write to a temp file
        fd, tmp = tempfile.mkstemp(prefix='sa-key-', suffix='.json')
        with os.fdopen(fd, 'w') as f:
            f.write(json_str)
        json_path = tmp
    else:
        # fall back to a file path provided in env
        file_path = os.environ.get(file_env_var)
        if file_path and os.path.exists(file_path):
            json_path = file_path

    if not json_path:
        return None, "No service account JSON found. Set SERVICE_ACCOUNT_JSON (preferred) or SERVICE_ACCOUNT_FILE."

    try:
        creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client, None
    except Exception as e:
        return None, str(e)

# Initialize client at import time (safe for Render)
GSPREAD_CLIENT, GSPREAD_ERROR = init_gspread_client()

# Sheet configuration defaults (you can override with env vars)
SHEET_DONOR = os.environ.get('SHEET_DONOR', 'AgastyaInternationalFoundation')
WORKSHEET_DONOR = os.environ.get('WORKSHEET_DONOR', 'Donar')

SHEET_PROGRAM_URL = os.environ.get('SHEET_PROGRAM_URL', '')
WORKSHEET_PROGRAM = os.environ.get('WORKSHEET_PROGRAM', 'ProgramTeam')

SHEET_VENDOR = os.environ.get('SHEET_VENDOR', 'AgastyaInternationalFoundation')
WORKSHEET_VENDOR = os.environ.get('WORKSHEET_VENDOR', 'Vendorsheet')

# Utility to open worksheet safely
def open_worksheet_by_title_or_url(client, sheet_title=None, sheet_url=None, worksheet_name=None):
    try:
        if sheet_url:
            sh = client.open_by_url(sheet_url)
        else:
            sh = client.open(sheet_title)
        ws = sh.worksheet(worksheet_name)
        return ws, None
    except Exception as e:
        return None, str(e)

# Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'replace_me')

# Templates (simple) - using render_template_string for single-file deploy
INDEX_HTML = """
<!doctype html>
<title>Unified Dashboard</title>
<h1>Unified Dashboard</h1>
<ul>
  <li><a href="/donor">Donor Menu</a></li>
  <li><a href="/program">Program Team</a></li>
  <li><a href="/vendor">Vendor Management</a></li>
</ul>
"""

DONOR_HTML = """
<!doctype html>
<title>Donor Menu</title>
<h1>Donor Menu</h1>
<p>{{ msg }}</p>
<form method="post">
  <label>Donor Name: <input name="Donor Name"></label><br>
  <label>Version Book: <input name="Version Book"></label><br>
  <label>Total Unique Child: <input name="Total Unique Child"></label><br>
  <label>Total Exposure: <input name="Total Exposure"></label><br>
  <label>Cost per Unique Child: <input name="Cost per Unique Child"></label><br>
  <label>Cost per Exposure: <input name="Cost per Exposure"></label><br>
  <label>Donor Relation: <input name="Donor Relation"></label><br>
  <label>Point of Contact: <input name="Point of Contact"></label><br>
  <label>Project ID: <input name="Project ID"></label><br>
  <button type="submit">Save Donor</button>
</form>
<hr>
<h2>Existing donors</h2>
<ul>
{% for d in donors %}
  <li>{{ d }}</li>
{% else %}
  <li>No donors found</li>
{% endfor %}
</ul>
<a href="/">Back</a>
"""

PROGRAM_HTML = """
<!doctype html>
<title>Program Team</title>
<h1>Program Team</h1>
<p>{{ msg }}</p>
<form method="post">
  <label>Region: <input name="Region"></label><br>
  <label>Version: <input name="Version"></label><br>
  <label>Language: <input name="Language"></label><br>
  <label>Quantity: <input name="Quantity"></label><br>
  <label>Grade: <input name="Grade"></label><br>
  <label>Total: <input name="Total"></label><br>
  <label>Point of Contact: <input name="POC"></label><br>
  <label>LR Path (optional): <input name="LR"></label><br>
  <button type="submit">Save</button>
</form>
<hr>
<h2>Entries</h2>
<ul>
{% for r in rows %}
  <li>{{ r }}</li>
{% else %}
  <li>No entries</li>
{% endfor %}
</ul>
<a href="/">Back</a>
"""

VENDOR_HTML = """
<!doctype html>
<title>Vendor Management</title>
<h1>Vendor Management</h1>
<p>{{ msg }}</p>
<form method="post" enctype="multipart/form-data">
  <label>Vendor Name: <input name="vendor"></label><br>
  <label>PAN: <input name="pan"></label><br>
  <label>GST: <input name="gst"></label><br>
  <label>Version: <input name="version"></label><br>
  <label>Language: <input name="language"></label><br>
  <label>Quantity: <input name="qty"></label><br>
  <label>PAN image: <input type="file" name="pan_img"></label><br>
  <label>GST image: <input type="file" name="gst_img"></label><br>
  <button type="submit">Add Line</button>
</form>
<hr>
<h2>Invoice Lines (session-based)</h2>
<ul>
{% for it in invoice %}
  <li>{{ it['version'] }} | {{ it['language'] }} | Qty {{ it['qty'] }} | Amount {{ it['amount'] }}</li>
{% else %}
  <li>No lines</li>
{% endfor %}
</ul>
<form method="post" action="/vendor/submit">
  <button type="submit">Submit All to Google Sheets</button>
</form>
<a href="/">Back</a>
"""

# Simple in-memory store for invoice items per process (not persistent; ok for small teams)
INVOICE_ITEMS = []

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

# ---------------- Donor ----------------
@app.route('/donor', methods=['GET', 'POST'])
def donor():
    msg = ''
    donors = []
    if not GSPREAD_CLIENT:
        msg = f"Google Sheets not configured: {GSPREAD_ERROR}"
        return render_template_string(DONOR_HTML, msg=msg, donors=donors)

    try:
        ws, err = open_worksheet_by_title_or_url(GSPREAD_CLIENT, sheet_title=SHEET_DONOR, worksheet_name=WORKSHEET_DONOR)
        if err:
            msg = f"Could not open donor worksheet: {err}"
            return render_template_string(DONOR_HTML, msg=msg, donors=donors)

        if request.method == 'POST':
            # collect fields in the same order as original
            fields = [
                "Donor Name", "Version Book", "Total Unique Child", "Total Exposure",
                "Cost per Unique Child", "Cost per Exposure", "Donor Relation",
                "Point of Contact", "Project ID"
            ]
            row = [request.form.get(f, '') for f in fields]
            if not row[0]:
                msg = 'Donor Name is required.'
            else:
                try:
                    ws.append_row(row)
                    msg = f"Donor '{row[0]}' saved."
                except Exception as e:
                    msg = f"Save failed: {e}"

        # load donors list
        records = ws.get_all_values()
        donors = [r[0] for r in records[1:] if r]
    except Exception as e:
        msg = f"Error: {e}"

    return render_template_string(DONOR_HTML, msg=msg, donors=donors)

# ---------------- Program Team ----------------
@app.route('/program', methods=['GET', 'POST'])
def program():
    msg = ''
    rows = []
    if not GSPREAD_CLIENT:
        msg = f"Google Sheets not configured: {GSPREAD_ERROR}"
        return render_template_string(PROGRAM_HTML, msg=msg, rows=rows)

    try:
        ws, err = open_worksheet_by_title_or_url(GSPREAD_CLIENT, sheet_url=SHEET_PROGRAM_URL, worksheet_name=WORKSHEET_PROGRAM) if SHEET_PROGRAM_URL else open_worksheet_by_title_or_url(GSPREAD_CLIENT, sheet_title=SHEET_DONOR, worksheet_name=WORKSHEET_PROGRAM)
        if err:
            msg = f"Could not open program worksheet: {err}"
            return render_template_string(PROGRAM_HTML, msg=msg, rows=rows)

        if request.method == 'POST':
            vals = [
                request.form.get('Region',''), request.form.get('Version',''), request.form.get('Language',''),
                request.form.get('Quantity',''), request.form.get('Grade',''), request.form.get('Total',''),
                request.form.get('POC',''), request.form.get('LR','')
            ]
            try:
                ws.append_row(vals)
                msg = 'Saved program entry.'
            except Exception as e:
                msg = f"Save failed: {e}"

        rows = ws.get_all_records()
    except Exception as e:
        msg = f"Error: {e}"

    return render_template_string(PROGRAM_HTML, msg=msg, rows=rows)

# ---------------- Vendor ----------------
@app.route('/vendor', methods=['GET', 'POST'])
def vendor():
    msg = ''
    global INVOICE_ITEMS
    if request.method == 'POST':
        vendor = request.form.get('vendor','').strip()
        pan = request.form.get('pan','').strip()
        gst = request.form.get('gst','').strip()
        version = request.form.get('version','').strip()
        language = request.form.get('language','').strip()
        qty = request.form.get('qty','').strip()

        if not (vendor and pan and gst and version and language and qty):
            msg = 'All fields required.'
        else:
            try:
                qty_i = int(qty)
            except:
                msg = 'Quantity must be integer.'
                return render_template_string(VENDOR_HTML, msg=msg, invoice=INVOICE_ITEMS)

            # save images
            pan_img = request.files.get('pan_img')
            gst_img = request.files.get('gst_img')
            pan_fname = ''
            gst_fname = ''
            if pan_img and pan_img.filename:
                pan_fname = secure_filename(f"{int(datetime.datetime.now().timestamp())}_{pan_img.filename}")
                pan_img.save(os.path.join(UPLOAD_DIR, pan_fname))
            if gst_img and gst_img.filename:
                gst_fname = secure_filename(f"{int(datetime.datetime.now().timestamp())}_{gst_img.filename}")
                gst_img.save(os.path.join(UPLOAD_DIR, gst_fname))

            unit_price = 0
            # a simple price map mimic
            PRICE_MAP = {
                "Actilearn 1.0": 250,
                "Actilearn Junior": 180,
                "Papertronics": 220,
                "ISEE": 300,
            }
            unit_price = PRICE_MAP.get(version, 200)
            amount = qty_i * unit_price

            entry = {
                'vendor': vendor, 'pan': pan, 'gst': gst, 'version': version,
                'language': language, 'qty': qty_i, 'unit_price': unit_price, 'amount': amount,
                'pan_img': pan_fname, 'gst_img': gst_fname, 'timestamp': datetime.datetime.now().isoformat()
            }
            INVOICE_ITEMS.append(entry)
            msg = 'Line added.'

    return render_template_string(VENDOR_HTML, msg=msg, invoice=INVOICE_ITEMS)

@app.route('/vendor/submit', methods=['POST'])
def vendor_submit():
    global INVOICE_ITEMS
    msg = ''
    if not GSPREAD_CLIENT:
        flash(f"Google Sheets not configured: {GSPREAD_ERROR}")
        return redirect(url_for('vendor'))

    try:
        ws, err = open_worksheet_by_title_or_url(GSPREAD_CLIENT, sheet_title=SHEET_VENDOR, worksheet_name=WORKSHEET_VENDOR)
        if err:
            flash(f"Could not open vendor worksheet: {err}")
            return redirect(url_for('vendor'))

        for it in INVOICE_ITEMS:
            ws.append_row([
                it['timestamp'], it['vendor'], it['pan'], it['gst'], it['version'], it['language'], it['qty'], it['unit_price'], it['amount'], it['pan_img'], it['gst_img']
            ])
        INVOICE_ITEMS = []
        flash('Submitted all vendor lines to Google Sheets.')
    except Exception as e:
        flash(f'Submit failed: {e}')

    return redirect(url_for('vendor'))

# Route to serve uploaded images (for convenience)
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

if __name__ == '__main__':
    # Local debug server
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
