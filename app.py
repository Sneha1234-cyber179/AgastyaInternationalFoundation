###############################################
# dashboard_all.py
# Unified Dashboard that launches:
#  - Donor Menu (existing code)
#  - Program Team app (existing code)
#  - Vendor Management app (existing code)
#
# Save and run: python dashboard_all.py
###############################################

import os
import datetime
import tkinter as tk
from tkinter import *
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# ---- Google Sheets imports used by modules ----
import gspread
from google.oauth2.service_account import Credentials
import re

# ------------------------------
# 1) Donor module (kept unchanged, wrapped to open in a Toplevel)
# ------------------------------
# Google Sheets config used by donor module (keep as you had)
SHEET_NAME_DONOR = "AgastyaInternationalFoundation"        # Google Sheet name
WORKSHEET_NAME_DONOR = "Donar"        # Tab name inside the sheet
JSON_KEY_FILE_DONOR = r"C:\Users\User\Downloads\donormenuapp-c696ed3a5cbb.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Try connecting to Google Sheets for donor module
try:
    creds_donor = Credentials.from_service_account_file(JSON_KEY_FILE_DONOR, scopes=SCOPES)
    client_donor = gspread.authorize(creds_donor)
    sheet_file_donor = client_donor.open(SHEET_NAME_DONOR)
    sheet_donor = sheet_file_donor.worksheet(WORKSHEET_NAME_DONOR)
    print("✅ Donor: Connected to Google Sheet successfully!")
except Exception as e:
    print("❌ Donor: Error connecting to Google Sheets:", e)
    sheet_donor = None


class DonorDashboardWindow:
    """Wrap the original DonorDashboard to run inside a Toplevel window."""
    def __init__(self, master):
        # create a new top-level window
        self.win = Toplevel(master)
        self.win.title("Donor Menu - Google Sheets Integrated")
        self.win.geometry("900x700+200+50")
        self.win.config(bg="white")

        title = Label(self.win, text="Donor Menu", font=("times new roman", 28, "bold"),
                      bg="white", fg="black")
        title.pack(pady=10)

        Button(self.win, text="➤ Add New Donor", font=("times new roman", 14, "bold"),
               bg="lightblue", command=self.add_new_donor).pack(pady=10)

        Button(self.win, text="➤ Select Existing Donor", font=("times new roman", 14, "bold"),
               bg="lightgreen", command=self.select_existing_donor).pack(pady=10)

        self.frame = Frame(self.win, bg="white")
        self.frame.pack(fill=BOTH, expand=True)

    # ========== ADD NEW DONOR ==========
    def add_new_donor(self):
        self.clear_frame()

        Label(self.frame, text="Add New Donor Details", font=("times new roman", 16, "bold"),
              bg="white").pack(pady=10)

        fields = [
            "Donor Name", "Version Book", "Total Unique Child", "Total Exposure",
            "Cost per Unique Child", "Cost per Exposure", "Donor Relation",
            "Point of Contact", "Project ID"
        ]

        self.entries = {}

        for field in fields:
            fr = Frame(self.frame, bg="white")
            fr.pack(pady=5)

            Label(fr, text=field + ":", font=("times new roman", 12, "bold"),
                  width=22, anchor="w", bg="white").pack(side=LEFT)

            ent = Entry(fr, font=("times new roman", 12), width=35)
            ent.pack(side=LEFT)
            self.entries[field] = ent

        Button(self.frame, text="Save Donor", font=("times new roman", 13, "bold"),
               bg="lightcoral", command=self.save_donor_to_sheet).pack(pady=20)

    def save_donor_to_sheet(self):
        global sheet_donor
        if not sheet_donor:
            messagebox.showerror("Error", "Google Sheet not connected.")
            return

        data = [self.entries[f].get().strip() for f in self.entries]

        if data[0] == "":
            messagebox.showwarning("Warning", "Donor Name is required.")
            return

        try:
            sheet_donor.append_row(data)
            messagebox.showinfo("Success", f"Donor '{data[0]}' saved to Google Sheet.")
            self.clear_frame()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save donor:\n{e}")

    # ========== SELECT EXISTING DONOR ==========
    def select_existing_donor(self):
        self.clear_frame()

        Label(self.frame, text="Select Existing Donor", font=("times new roman", 16, "bold"),
              bg="white").pack(pady=10)

        try:
            records = sheet_donor.get_all_values() if sheet_donor else []
            donors = [row[0] for row in records[1:] if row]
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load donors list:\n{e}")
            return

        if not donors:
            Label(self.frame, text="No donors found.", bg="white",
                  font=("times new roman", 13)).pack()
            return

        self.donor_var = StringVar()
        combo = ttk.Combobox(self.frame, textvariable=self.donor_var,
                             values=donors, state="readonly",
                             font=("times new roman", 12))
        combo.pack(pady=5)
        combo.bind("<<ComboboxSelected>>", self.load_donor_details)

        self.details_frame = Frame(self.frame, bg="white")
        self.details_frame.pack(pady=15)

    def load_donor_details(self, event=None):
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        donor_name = self.donor_var.get()
        records = sheet_donor.get_all_values() if sheet_donor else []
        headers = records[0] if records else []

        donor_data = None
        for row in records[1:]:
            if row and row[0] == donor_name:
                donor_data = row
                break

        if not donor_data:
            messagebox.showerror("Error", "Donor not found.")
            return

        self.edit_entries = {}

        for i, field in enumerate(headers):
            fr = Frame(self.details_frame, bg="white")
            fr.pack(pady=5)

            Label(fr, text=field + ":", font=("times new roman", 12, "bold"),
                  width=22, anchor="w", bg="white").pack(side=LEFT)

            ent = Entry(fr, font=("times new roman", 12), width=35)
            ent.pack(side=LEFT)
            ent.insert(0, donor_data[i] if i < len(donor_data) else "")
            self.edit_entries[field] = ent

        Button(self.details_frame, text="Update Donor", font=("times new roman", 13, "bold"),
               bg="lightgreen", command=self.update_donor_data).pack(pady=20)

    def update_donor_data(self):
        donor_name = self.donor_var.get()
        new_data = [self.edit_entries[f].get().strip() for f in self.edit_entries]

        records = sheet_donor.get_all_values() if sheet_donor else []

        for i, row in enumerate(records[1:], start=2):
            if row and row[0] == donor_name:
                range_to_update = f"A{i}:I{i}"
                sheet_donor.update(range_to_update, [new_data])
                messagebox.showinfo("Success", "Donor updated successfully.")
                return

        messagebox.showwarning("Warning", "Donor not found.")

    def clear_frame(self):
        for widget in self.frame.winfo_children():
            widget.destroy()

# ------------------------------
# 2) Program Team module (wrapped into a class)
# ------------------------------
# ProgramTeam uses its own sheet config - preserved
SCOPE_PT = ["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"]

# Use the same service account JSON you used in ProgramTeam code
JSON_KEY_FILE_PT = r"C:\Users\User\Downloads\donormenuapp-c696ed3a5cbb.json"
SHEET_URL_PT = "https://docs.google.com/spreadsheets/d/1rppbJqgrgBI_L5PYucD44uBTC3AIzyUYDCteVRPDPUE/edit"
WORKSHEET_NAME_PT = "ProgramTeam"

# Connect for ProgramTeam
try:
    creds_pt = Credentials.from_service_account_file(JSON_KEY_FILE_PT, scopes=SCOPE_PT)
    client_pt = gspread.authorize(creds_pt)
    sheet_pt = client_pt.open_by_url(SHEET_URL_PT).worksheet(WORKSHEET_NAME_PT)
    print("✅ ProgramTeam: Connected to Google Sheet successfully!")
except Exception as e:
    print("❌ ProgramTeam: Error connecting to Google Sheets:", e)
    sheet_pt = None

# preserved lists
regions = ["N1", "N2", "Gujarat", "MH1", "NK2", "NK2SK1",
           "SK2", "Tamilnadu", "APTS", "Kupam"]

versions = [
    "Actilearn 1.0",
    "Actilearn Junior",
    "Papertronics",
    "ISEE",
    "Financial Literacy",
    "Plastic Smart",
    "ClimateQuest",
    "Chemagica"
]

languages = [
    "Hindi", "English", "Kannada", "Tamil", "Telugu", "Malayalam",
    "Marathi", "Gujarati", "Punjabi", "Bengali", "Odia",
    "Urdu", "Assamese", "Konkani", "Manipuri", "Sanskrit"
]


class ProgramTeamWindow:
    def __init__(self, master):
        self.win = Toplevel(master)
        self.win.title("Program Team Data Manager")
        self.win.geometry("900x650")

        # Notebook
        self.notebook = ttk.Notebook(self.win)
        self.tab_enter = ttk.Frame(self.notebook)
        self.tab_view = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_enter, text="Enter Data")
        self.notebook.add(self.tab_view, text="View Data")
        self.notebook.pack(expand=True, fill='both')

        # Build Enter tab UI
        self.build_enter_tab()

        # Load view data on start
        self.load_view_data()

    # ---------- functions adapted ----------
    def browse_lr(self):
        filepath = filedialog.askopenfilename(
            title="Select LR Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.gif")]
        )
        if filepath:
            self.lr_path_var.set(filepath)

    def is_number(self, value):
        return value.isdigit()

    def is_valid_email(self, email):
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return re.match(pattern, email) is not None

    def validate_region(self, event=None):
        if self.region_var.get() not in regions:
            messagebox.showerror("Invalid", "Please select a valid Region!")
            self.region_var.set("")

    def number_only(self, event):
        if event.char.isalpha():
            messagebox.showerror("Invalid", "Only numbers allowed!")
            return "break"

    def clear_placeholder(self, event):
        if self.poc_entry.get() == "example@gmail.com":
            self.poc_entry.delete(0, tk.END)
            self.poc_entry.configure(foreground="black")

    def save_data(self):
        if not sheet_pt:
            messagebox.showerror("Error", "Google Sheet not connected.")
            return

        region = self.region_var.get()
        version = self.version_var.get()
        language = self.language_var.get()
        qty = self.qty_entry.get()
        grade = self.grade_entry.get()
        total = self.total_entry.get()
        poc = self.poc_entry.get()
        lr_path = self.lr_path_var.get()

        if not all([region, version, language, qty, grade, total, poc, lr_path]):
            messagebox.showerror("Error", "All fields must be filled!")
            return

        if not self.is_number(qty):
            messagebox.showerror("Error", "Quantity must be a number!")
            return

        if not self.is_number(grade):
            messagebox.showerror("Error", "Grade must be a number!")
            return

        if not self.is_number(total):
            messagebox.showerror("Error", "Total must be a number!")
            return

        if not self.is_valid_email(poc):
            messagebox.showerror("Error", "Enter a valid email!")
            return

        try:
            sheet_pt.append_row([region, version, language, qty, grade, total, poc, lr_path])
            messagebox.showinfo("Success", "Data saved successfully!")

            self.qty_entry.delete(0, tk.END)
            self.grade_entry.delete(0, tk.END)
            self.total_entry.delete(0, tk.END)
            self.poc_entry.delete(0, tk.END)
            self.lr_path_var.set("")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data:\n{e}")

    def build_enter_tab(self):
        # variables
        self.region_var = tk.StringVar()
        self.version_var = tk.StringVar()
        self.language_var = tk.StringVar()
        self.lr_path_var = tk.StringVar()

        labels = ["Region", "Version", "Language", "Quantity", "Grade", "Total", "Point of Contact", "LR Image"]
        for i, text in enumerate(labels):
            ttk.Label(self.tab_enter, text=text, font=("Arial", 11)).grid(row=i, column=0, padx=25, pady=10, sticky="w")

        self.region_cb = ttk.Combobox(self.tab_enter, textvariable=self.region_var, values=regions)
        self.version_cb = ttk.Combobox(self.tab_enter, textvariable=self.version_var, values=versions)
        self.language_cb = ttk.Combobox(self.tab_enter, textvariable=self.language_var, values=languages)

        self.qty_entry = ttk.Entry(self.tab_enter)
        self.grade_entry = ttk.Entry(self.tab_enter)
        self.total_entry = ttk.Entry(self.tab_enter)
        self.poc_entry = ttk.Entry(self.tab_enter)

        self.region_cb.grid(row=0, column=1)
        self.version_cb.grid(row=1, column=1)
        self.language_cb.grid(row=2, column=1)
        self.qty_entry.grid(row=3, column=1)
        self.grade_entry.grid(row=4, column=1)
        self.total_entry.grid(row=5, column=1)
        self.poc_entry.grid(row=6, column=1)

        ttk.Button(self.tab_enter, text="Browse", command=self.browse_lr).grid(row=7, column=1, sticky="w")

        # Placeholder for POC
        self.poc_entry.insert(0, "example@gmail.com")
        self.poc_entry.configure(foreground="gray")
        self.poc_entry.bind("<FocusIn>", self.clear_placeholder)

        # Region Validation
        self.region_cb.bind("<FocusOut>", self.validate_region)
        self.region_cb.bind("<Return>", self.validate_region)

        # Number Restriction
        self.qty_entry.bind("<KeyPress>", self.number_only)
        self.grade_entry.bind("<KeyPress>", self.number_only)
        self.total_entry.bind("<KeyPress>", self.number_only)

        entries = [self.region_cb, self.version_cb, self.language_cb, self.qty_entry, self.grade_entry, self.total_entry, self.poc_entry]
        self.navigation_order = entries

        # Enter -> next field
        for i in range(len(entries) - 1):
            entries[i].bind("<Return>", lambda e, next_widget=entries[i+1]: next_widget.focus())

        # Backspace -> previous field
        def move_prev(event):
            widget = event.widget
            if widget in self.navigation_order:
                idx = self.navigation_order.index(widget)
                if idx > 0:
                    self.navigation_order[idx - 1].focus()

        for e in entries:
            e.bind("<BackSpace>", move_prev)

        # ALT + TAB -> Go back one field
        def alt_tab_back(event):
            widget = self.win.focus_get()
            if widget in self.navigation_order:
                idx = self.navigation_order.index(widget)
                if idx > 0:
                    self.navigation_order[idx - 1].focus()

        self.win.bind("<Alt-Tab>", alt_tab_back)

        ttk.Button(self.tab_enter, text="SAVE", command=self.save_data).grid(row=9, column=0, columnspan=2, pady=25)

    # ========== VIEW TAB ==========
    def load_view_data(self):
        for widget in self.tab_view.winfo_children():
            widget.destroy()

        ttk.Label(self.tab_view, text="Select Region", font=("Arial", 12)).grid(row=0, column=0, padx=10, pady=10)

        filter_var = tk.StringVar()
        region_filter = ttk.Combobox(self.tab_view, textvariable=filter_var, values=regions)
        region_filter.grid(row=0, column=1, padx=10)

        table = ttk.Treeview(
            self.tab_view,
            columns=("Region", "Version", "Language", "Quantity", "Grade", "Total", "POC", "LR"),
            show="headings"
        )

        for col in table["columns"]:
            table.heading(col, text=col)
            table.column(col, width=120)

        table.grid(row=1, column=0, columnspan=4, padx=15, pady=20)

        def filter_rows(event=None):
            table.delete(*table.get_children())
            try:
                rows = sheet_pt.get_all_records() if sheet_pt else []
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load rows:\n{e}")
                return

            for r in rows:
                # ensure keys exist; handle differences by lower/upper/capitalization tolerance
                region_val = r.get("Region") or r.get("region") or r.get("REGION") or ""
                if region_val == filter_var.get():
                    table.insert("", "end", values=(
                        r.get("Region", ""), r.get("Version", ""), r.get("Language", ""), r.get("Quantity", ""),
                        r.get("Grade", ""), r.get("Total", ""), r.get("POC", ""), r.get("LR", "")
                    ))

        region_filter.bind("<<ComboboxSelected>>", filter_rows)

# ------------------------------
# 3) Vendor module (kept largely unchanged — wrapped)
# ------------------------------
SERVICE_ACCOUNT_FILE_VENDOR = r"C:\Users\User\Downloads\VENDOR\agastyainternationalfoundation-fdeb6350084a.json"
SPREADSHEET_TITLE_VENDOR = "AgastyaInternationalFoundation"
WORKSHEET_NAME_VENDOR = "Vendorsheet"

IMAGES_SAVE_DIR = os.path.join(os.getcwd(), "uploaded_vendor_images")
if not os.path.exists(IMAGES_SAVE_DIR):
    os.makedirs(IMAGES_SAVE_DIR)

PRICE_MAP = {
    "Actilearn 1.0": 250,
    "Actilearn Junior": 180,
    "Papertronics": 220,
    "ISEE": 300,
    "Financial Literacy": 200,
    "Plastic Smart": 150,
    "ClimateQuest": 275,
    "Chemagica": 230,
}

VERSIONS = list(PRICE_MAP.keys())
LANGUAGES = [
    "English","Hindi","Kannada","Tamil","Telugu","Malayalam",
    "Marathi","Gujarati","Punjabi","Bengali","Odia","Assamese","Urdu"
]

# Connect vendor sheets
try:
    creds_vendor = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE_VENDOR, scopes=SCOPE_PT)
    client_vendor = gspread.authorize(creds_vendor)
    sh_vendor = client_vendor.open(SPREADSHEET_TITLE_VENDOR)
    ws_vendor = sh_vendor.worksheet(WORKSHEET_NAME_VENDOR)
    print("✅ Vendor: Connected to Google Sheet successfully!")
except Exception as e:
    print("❌ Vendor: Error connecting to Google Sheets:", e)
    ws_vendor = None


class VendorAppWindow:
    def __init__(self, master):
        self.win = Toplevel(master)
        self.win.title("Vendor Management System")
        self.win.geometry("1050x620")
        self.win.resizable(False, False)

        self.invoice_items = []
        self.selected_index = None

        self.create_ui()

    def create_ui(self):
        left = ttk.Frame(self.win, padding=12)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="Vendor Name:").grid(row=0, column=0, sticky=tk.W)
        self.vendor_var = tk.StringVar()
        self.vendor_entry = ttk.Entry(left, textvariable=self.vendor_var, width=34)
        self.vendor_entry.grid(row=1, column=0, pady=4)
        self.vendor_entry.bind('<Return>', lambda e: e.widget.tk_focusNext().focus())

        ttk.Label(left, text="Notes / Manual ID:").grid(row=2, column=0, sticky=tk.W)
        self.notes_txt = ScrolledText(left, width=34, height=4)
        self.notes_txt.grid(row=3, column=0, pady=4)

        ttk.Label(left, text="PAN:").grid(row=4, column=0, sticky=tk.W)
        self.pan_var = tk.StringVar()
        self.pan_entry = ttk.Entry(left, textvariable=self.pan_var, width=34)
        self.pan_entry.grid(row=5, column=0, pady=4)

        ttk.Label(left, text="GST:").grid(row=6, column=0, sticky=tk.W)
        self.gst_var = tk.StringVar()
        self.gst_entry = ttk.Entry(left, textvariable=self.gst_var, width=34)
        self.gst_entry.grid(row=7, column=0, pady=4)

        ttk.Label(left, text="Upload PAN/GST Image:").grid(row=8, column=0, sticky=tk.W)
        upload_frame = ttk.Frame(left)
        upload_frame.grid(row=9, column=0, pady=4)
        self.pan_img_var = tk.StringVar()
        self.gst_img_var = tk.StringVar()
        ttk.Button(upload_frame, text="Upload PAN Image", command=lambda: self.browse_image('pan')).pack(side=tk.LEFT, padx=4)
        ttk.Button(upload_frame, text="Upload GST Image", command=lambda: self.browse_image('gst')).pack(side=tk.LEFT, padx=4)
        ttk.Label(left, textvariable=self.pan_img_var, width=40).grid(row=10, column=0, sticky=tk.W)
        ttk.Label(left, textvariable=self.gst_img_var, width=40).grid(row=11, column=0, sticky=tk.W)

        ttk.Label(left, text="Version:").grid(row=12, column=0, sticky=tk.W)
        self.version_var = tk.StringVar()
        self.version_cb = ttk.Combobox(left, textvariable=self.version_var, values=VERSIONS, state='readonly', width=32)
        self.version_cb.grid(row=13, column=0, pady=4)

        ttk.Label(left, text="Language:").grid(row=14, column=0, sticky=tk.W)
        self.lang_var = tk.StringVar()
        self.lang_cb = ttk.Combobox(left, textvariable=self.lang_var, values=LANGUAGES, state='readonly', width=32)
        self.lang_cb.grid(row=15, column=0, pady=4)

        ttk.Label(left, text="Quantity:").grid(row=16, column=0, sticky=tk.W)
        self.qty_var = tk.StringVar()
        vcmd = (self.win.register(lambda P: P.isdigit() or P==""), '%P')
        self.qty_entry = ttk.Entry(left, textvariable=self.qty_var, validate='key', validatecommand=vcmd, width=34)
        self.qty_entry.grid(row=17, column=0, pady=4)

        btn_frame = ttk.Frame(left)
        btn_frame.grid(row=18, column=0, pady=10)
        ttk.Button(btn_frame, text="Add / Update Line", command=self.add_update_line).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Clear Form", command=self.clear_form).pack(side=tk.LEFT, padx=6)

        self.submit_btn = ttk.Button(left, text="Submit All to Google Sheet", command=self.submit_all, state='disabled')
        self.submit_btn.grid(row=19, column=0, pady=6)

        right = ttk.Frame(self.win, padding=12)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(right, text="Invoice Preview:").pack(anchor=tk.W)
        self.invoice_list = tk.Listbox(right, width=70, height=28)
        self.invoice_list.pack(fill=tk.BOTH, expand=True)
        self.invoice_list.bind('<<ListboxSelect>>', self.load_selected)

        self.total_var = tk.StringVar(value="Total: 0")
        ttk.Label(right, textvariable=self.total_var, font=(None, 12, 'bold')).pack(anchor=tk.E, pady=6)

    # image handling
    def browse_image(self, kind):
        path = filedialog.askopenfilename(title="Select image", filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp")])
        if not path:
            return
        dest = os.path.join(IMAGES_SAVE_DIR, f"{int(datetime.datetime.now().timestamp())}_{os.path.basename(path)}")
        try:
            with open(path, 'rb') as r, open(dest, 'wb') as w:
                w.write(r.read())
        except Exception as e:
            messagebox.showerror("Image Save Error", f"Could not save image: {e}")
            return
        if kind == 'pan':
            self.pan_img_var.set(os.path.basename(dest))
            self.pan_img_path = dest
        else:
            self.gst_img_var.set(os.path.basename(dest))
            self.gst_img_path = dest
        messagebox.showinfo("Saved", f"Saved image: {os.path.basename(dest)}")

    def add_update_line(self):
        vendor = self.vendor_var.get().strip()
        notes = self.notes_txt.get("1.0", tk.END).strip()
        pan = self.pan_var.get().strip()
        gst = self.gst_var.get().strip()
        version = self.version_var.get().strip()
        lang = self.lang_var.get().strip()
        qty = self.qty_var.get().strip()
        pan_img = getattr(self, 'pan_img_path', '')
        gst_img = getattr(self, 'gst_img_path', '')

        if not (vendor and pan and gst and version and lang and qty):
            messagebox.showwarning("Missing Data", "All fields except notes are required.")
            return

        try:
            qty_int = int(qty)
        except:
            messagebox.showwarning("Invalid", "Quantity must be whole number.")
            return

        unit_price = PRICE_MAP.get(version, 0)
        amount = qty_int * unit_price

        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "vendor": vendor,
            "notes": notes,
            "pan": pan,
            "gst": gst,
            "version": version,
            "language": lang,
            "qty": qty_int,
            "unit_price": unit_price,
            "amount": amount,
            "pan_img": pan_img,
            "gst_img": gst_img
        }

        self.invoice_items.append(entry)
        self.refresh_invoice()
        self.clear_form(keep_vendor=True)

    def refresh_invoice(self):
        self.invoice_list.delete(0, tk.END)
        total = 0
        for i, it in enumerate(self.invoice_items):
            text = f"{i+1}. {it['version']} | {it['language']} | Qty {it['qty']} | Amount {it['amount']}"
            self.invoice_list.insert(tk.END, text)
            total += it['amount']
        self.total_var.set(f"Total: {total}")
        self.toggle_submit()

    def load_selected(self, event=None):
        sel = self.invoice_list.curselection()
        if not sel:
            return
        idx = sel[0]
        it = self.invoice_items[idx]
        self.selected_index = idx

        self.vendor_var.set(it["vendor"])
        self.notes_txt.delete("1.0", tk.END)
        self.notes_txt.insert(tk.END, it["notes"])
        self.pan_var.set(it["pan"])
        self.gst_var.set(it["gst"])
        self.version_var.set(it["version"])
        self.lang_var.set(it["language"])
        self.qty_var.set(str(it["qty"]))

        self.pan_img_var.set(os.path.basename(it["pan_img"]))
        self.gst_img_var.set(os.path.basename(it["gst_img"]))

        self.pan_img_path = it["pan_img"]
        self.gst_img_path = it["gst_img"]

        self.status_var.set("Editing line")

    def clear_form(self, keep_vendor=False):
        if not keep_vendor:
            self.vendor_var.set("")
        self.notes_txt.delete("1.0", tk.END)
        self.pan_var.set("")
        self.gst_var.set("")
        self.version_var.set("")
        self.lang_var.set("")
        self.qty_var.set("")
        self.pan_img_var.set("")
        self.gst_img_var.set("")
        self.pan_img_path = ""
        self.gst_img_path = ""
        self.selected_index = None
        self.status_var.set("Ready")

    def submit_all(self):
        if not self.invoice_items:
            messagebox.showinfo("Empty", "No invoice lines to submit.")
            return
        if not ws_vendor:
            messagebox.showerror("Sheets Error", "Vendor Google Sheet not connected.")
            return
        try:
            for it in self.invoice_items:
                ws_vendor.append_row([
                    it["timestamp"], it["vendor"], it["notes"], it["pan"], it["gst"],
                    it["version"], it["language"], it["qty"], it["unit_price"],
                    it["amount"], os.path.basename(it["pan_img"]), os.path.basename(it["gst_img"])
                ])
            messagebox.showinfo("Success", "Vendor data submitted!")
            self.invoice_items = []
            self.refresh_invoice()
        except Exception as e:
            messagebox.showerror("Submit Error", f"Could not submit:\n{e}")

# ------------------------------
# Main Dashboard (three buttons)
# ------------------------------
class MainDashboard:
    def __init__(self, master):
        self.master = master
        master.title("Unified Dashboard - Donor / Program Team / Vendor")
        master.geometry("480x240+300+150")
        master.resizable(False, False)

        lbl = ttk.Label(master, text="Choose Module", font=("Arial", 16))
        lbl.pack(pady=12)

        btn_frame = ttk.Frame(master)
        btn_frame.pack(pady=10, padx=10, fill='x')

        # Donor
        donor_btn = ttk.Button(btn_frame, text="Open Donor Menu", command=self.open_donor)
        donor_btn.pack(fill='x', pady=6)

        # Program Team
        pt_btn = ttk.Button(btn_frame, text="Open Program Team", command=self.open_program_team)
        pt_btn.pack(fill='x', pady=6)

        # Vendor
        vendor_btn = ttk.Button(btn_frame, text="Open Vendor Management", command=self.open_vendor)
        vendor_btn.pack(fill='x', pady=6)

    def open_donor(self):
        DonorDashboardWindow(self.master)

    def open_program_team(self):
        ProgramTeamWindow(self.master)

    def open_vendor(self):
        VendorAppWindow(self.master)


if __name__ == "__main__":
    root = tk.Tk()
    MainDashboard(root)
    root.mainloop()
