import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk
import base64
import xml.etree.ElementTree as ET
import os
import shutil
import socket
import ssl
import concurrent.futures
import threading
import time
# Optional: ftplib reserved for future auth checks
# import ftplib

# Feature flag: set to False to hide/disable connectivity checks entirely
ENABLE_CONNECTIVITY_CHECK = True

# Global to hold the selected XML path
selected_xml_path = None

# -------- Helpers --------
ONES = {
    "ZERO": 0, "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
    "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9,
    "TEN": 10, "ELEVEN": 11, "TWELVE": 12, "THIRTEEN": 13, "FOURTEEN": 14,
    "FIFTEEN": 15, "SIXTEEN": 16, "SEVENTEEN": 17, "EIGHTEEN": 18, "NINETEEN": 19
}
TENS = {
    "TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FIFTY": 50,
    "SIXTY": 60, "SEVENTY": 70, "EIGHTY": 80, "NINETY": 90
}


def reassign_colours(servers_el: ET.Element):
    """Reassign Colour values across all <Server> blocks in strict 1..7 cycle after sorting."""
    srvs = [s for s in list(servers_el) if s.tag == 'Server']
    for idx, s in enumerate(srvs, start=1):
        colour_el = s.find('Colour')
        if colour_el is None:
            colour_el = ET.SubElement(s, 'Colour')
        colour_el.text = str(((idx - 1) % 7) + 1)


def name_to_index(name: str) -> int:
    """Infer an ordinal index from names like 'One', 'Fourteen', 'TwentyOne', '21'.
    Returns a positive int if recognized, else a large fallback for alpha sort.
    """
    if not name:
        return 10_000
    s = name.strip().upper().replace(" ", "").replace("-", "")
    # Direct digits anywhere in the name
    digits = ''.join(ch for ch in s if ch.isdigit())
    if digits:
        try:
            v = int(digits)
            if v > 0:
                return v
        except ValueError:
            pass
    # Exact 0..19
    if s in ONES:
        return ONES[s]
    # Exact tens
    if s in TENS:
        return TENS[s]
    # Concatenated tens+ones (e.g., TWENTYONE)
    for t_word, t_val in sorted(TENS.items(), key=lambda kv: -len(kv[0])):
        if s.startswith(t_word):
            rem = s[len(t_word):]
            if not rem:
                return t_val
            if rem in ONES:
                return t_val + ONES[rem]
    # Fallback for common variants (e.g., ONEHUNDREDTWENTYTHREE -> ignore >99)
    return 10_000


def get_servers_root(tree_root: ET.Element) -> ET.Element:
    servers = tree_root.find('Servers')
    if servers is None:
        servers = ET.SubElement(tree_root, 'Servers')
    return servers


def collect_existing(servers_el: ET.Element):
    existing = []
    for srv in list(servers_el):
        if srv.tag != 'Server':
            continue
        name_el = srv.find('Name')
        host_el = srv.find('Host')
        colour_el = srv.find('Colour')
        existing.append({
            'el': srv,
            'name': name_el.text.strip() if name_el is not None and name_el.text else '',
            'host': host_el.text.strip() if host_el is not None and host_el.text else '',
            'colour': int(colour_el.text) if colour_el is not None and colour_el.text and colour_el.text.isdigit() else None
        })
    return existing


def next_colour(existing):
    """Cycle colours 1..7 based on the last server's colour. If none, start at 1."""
    last_colour = None
    if existing:
        # Use the last element order in the file
        for i in range(len(existing)-1, -1, -1):
            c = existing[i]['colour']
            if isinstance(c, int):
                last_colour = c
                break
    if not last_colour:
        return 1
    return (last_colour % 7) + 1


def pretty_indent(tree: ET.ElementTree):
    """Indent with tabs to resemble FileZilla output. Uses ET.indent if available; otherwise manual."""
    if hasattr(ET, 'indent'):
        ET.indent(tree, space="\t", level=0)
        return

    def _indent(elem, level=0):
        i = "\n" + "\t" * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "\t"
            for idx, e in enumerate(list(elem)):
                _indent(e, level + 1)
                if not e.tail or not e.tail.strip():
                    e.tail = i + ("\t" if idx < len(elem) - 1 else "")
        else:
            if not elem.text or not elem.text.strip():
                elem.text = None
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
    _indent(tree.getroot())


def ensure_sorted_by_name_numeric(servers_el: ET.Element):
    srvs = [s for s in list(servers_el) if s.tag == 'Server']
    srvs_sorted = sorted(
        srvs,
        key=lambda s: (name_to_index((s.find('Name').text if s.find('Name') is not None and s.find('Name').text else '').strip()),
                       (s.find('Name').text if s.find('Name') is not None and s.find('Name').text else '').lower())
    )
    if srvs_sorted != srvs:
        # Clear and re-append in sorted order
        for s in srvs:
            servers_el.remove(s)
        for s in srvs_sorted:
            servers_el.append(s)


# -------- UI Actions --------

def choose_xml_file():
    """Open a Finder-style dialog to choose the FileZilla XML file."""
    global selected_xml_path
    path = filedialog.askopenfilename(
        title="Select FileZilla Sites XML",
        filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
    )
    if path:
        selected_xml_path = path
        xml_path_var.set(path)
        add_button.config(state=tk.NORMAL)
        reassign_button.config(state=tk.NORMAL)
        if ENABLE_CONNECTIVITY_CHECK:
            test_button.config(state=tk.NORMAL)


def add_printer():
    """Append or update a <Server> in the chosen XML with FileZilla-style formatting.
    Features: Base64 encoding, duplicate checking, numeric-aware sort, full-colour reassign (1..7 cycle), and .bak backup.
    """
    global selected_xml_path

    if not selected_xml_path:
        messagebox.showerror("No XML Selected", "Please select the FileZilla XML file first.")
        return

    name = name_entry.get().strip()
    ip = ip_entry.get().strip()
    access_code = access_entry.get().strip()
    colour_text = colour_entry.get().strip()

    if not (name and ip and access_code):
        messagebox.showerror("Missing Data", "Printer Name, IP Address, and Access Code are required.")
        return

    # Determine colour: if provided, validate 1..7; else temporary cycle from last (will be overwritten by global reassignment).
    cval = None
    if colour_text:
        try:
            cval = int(colour_text)
            if cval < 1 or cval > 7:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Colour", "Colour must be an integer from 1 to 7.")
            return

    # Base64 encode the access code
    encoded_pass = base64.b64encode(access_code.encode("utf-8")).decode("utf-8")

    try:
        tree = ET.parse(selected_xml_path)
        root = tree.getroot()
        servers_el = get_servers_root(root)
        existing = collect_existing(servers_el)

        # Auto-colour cycle if not provided
        if cval is None:
            cval = next_colour(existing)

        # Duplicate detection by Name or Host
        dup_by_name = next((e for e in existing if e['name'].lower() == name.lower()), None)
        dup_by_host = next((e for e in existing if e['host'] == ip), None)

        target_el = None
        if dup_by_name or dup_by_host:
            # Prefer exact name match if both exist
            target_el = (dup_by_name or dup_by_host)['el']
            if not messagebox.askyesno(
                "Duplicate Found",
                "An entry with the same Name or Host exists.\n\n"
                f"Overwrite this existing entry?\n\n"
                f"Existing Name: {dup_by_name['name'] if dup_by_name else dup_by_host['name']}\n"
                f"Existing Host: {dup_by_host['host'] if dup_by_host else dup_by_name['host']}"
            ):
                return
        else:
            target_el = ET.SubElement(servers_el, 'Server')

        # Populate/overwrite fields
        def set_text(tag, value):
            el = target_el.find(tag)
            if el is None:
                el = ET.SubElement(target_el, tag)
            el.text = value

        set_text('Host', ip)
        set_text('Port', '990')
        set_text('Protocol', '3')
        set_text('Type', '0')
        set_text('User', 'bblp')
        pass_el = target_el.find('Pass')
        if pass_el is None:
            pass_el = ET.SubElement(target_el, 'Pass')
        pass_el.set('encoding', 'base64')
        pass_el.text = encoded_pass
        set_text('Logontype', '1')
        set_text('PasvMode', 'MODE_DEFAULT')
        set_text('EncodingType', 'Auto')
        set_text('BypassProxy', '0')
        set_text('Name', name)
        set_text('Colour', str(cval))
        set_text('SyncBrowsing', '0')
        set_text('DirectoryComparison', '0')

        # Sort servers by numeric-aware name
        ensure_sorted_by_name_numeric(servers_el)

        # Reassign colours 1..7 across the full list to maintain the cycle
        reassign_colours(servers_el)

        # Backup original
        bak_path = selected_xml_path + ".bak"
        try:
            shutil.copy2(selected_xml_path, bak_path)
        except Exception:
            # Non-fatal
            pass

        # Pretty-print and write
        tree_strict = tree  # keep same object
        pretty_indent(tree_strict)
        tree_strict.write(selected_xml_path, encoding='UTF-8', xml_declaration=True)

        messagebox.showinfo(
            "Success",
            f"""Printer '{name}' added/updated.
Colours reassigned globally to maintain 1→7 cycle.
Sorted by Name.
Backup saved as:
{bak_path}"""
        )

        # Clear inputs
        name_entry.delete(0, tk.END)
        ip_entry.delete(0, tk.END)
        access_entry.delete(0, tk.END)
        colour_entry.delete(0, tk.END)

    except Exception as e:
        messagebox.showerror("Error Writing XML", f"{e}")


def reassign_only():
    """Load the chosen XML, sort by numeric-aware name, reassign colours 1..7, and write back (with .bak)."""
    global selected_xml_path

    if not selected_xml_path:
        messagebox.showerror("No XML Selected", "Please select the FileZilla XML file first.")
        return
    try:
        tree = ET.parse(selected_xml_path)
        root = tree.getroot()
        servers_el = get_servers_root(root)

        ensure_sorted_by_name_numeric(servers_el)
        reassign_colours(servers_el)

        bak_path = selected_xml_path + ".bak"
        try:
            shutil.copy2(selected_xml_path, bak_path)
        except Exception:
            pass

        pretty_indent(tree)
        tree.write(selected_xml_path, encoding='UTF-8', xml_declaration=True)

        messagebox.showinfo(
            "Colours Reassigned",
            f"""All printers sorted by Name and Colours reassigned to 1→7 cycle.
Backup saved as:
{bak_path}"""
        )
    except Exception as e:
        messagebox.showerror("Error Writing XML", f"{e}")


# -------- Connectivity Check (Reachability over implicit FTPS) --------

def _tls_reachability(host: str, port: int = 990, timeout: float = 10.0) -> (bool, str):
    """Attempt TCP connect and TLS handshake to confirm FTPS implicit availability.
    Returns (ok, detail). Uses permissive SSL context (self-signed OK).
    """
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            ctx = ssl.create_default_context()
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # Restrict to secure protocols only
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                # If handshake succeeds, we're good
                return True, "TLS handshake OK"
    except Exception as e:
        return False, str(e)


def test_connectivity_reachability(xml_path: str, update_row_cb, done_cb, max_workers: int = 5):
    """Run reachability tests in a thread pool and update UI via callbacks.
    update_row_cb(name, host, ok, detail)
    done_cb()
    """
    def _worker(entries):
        for name, host in entries:
            ok, detail = _tls_reachability(host)
            update_row_cb(name, host, ok, detail)

    # Parse XML and collect (Name, Host)
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        servers_el = get_servers_root(root)
        pairs = []
        for srv in servers_el.findall('Server'):
            name = (srv.findtext('Name') or '').strip()
            host = (srv.findtext('Host') or '').strip()
            if not name or not host:
                continue
            pairs.append((name, host))
        # Sort for deterministic order
        pairs.sort(key=lambda p: (name_to_index(p[0]), p[0].lower()))
    except Exception as e:
        # Fallback: report error via first row
        update_row_cb("<parse error>", "-", False, str(e))
        done_cb()
        return

    # Chunk work and run in pool
    chunks = [pairs[i::max_workers] for i in range(max_workers)] if pairs else []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_worker, chunk) for chunk in chunks]
        for _ in concurrent.futures.as_completed(futs):
            pass
    done_cb()


def open_connectivity_window():
    if not selected_xml_path:
        messagebox.showerror("No XML Selected", "Please select the FileZilla XML file first.")
        return

    win = tk.Toplevel(root)
    win.title("Connectivity Check — Reachability (Implicit FTPS)")
    win.geometry("800x400")

    cols = ("Name", "Host", "Result", "Detail")
    treeview = ttk.Treeview(win, columns=cols, show="headings")
    for c in cols:
        treeview.heading(c, text=c)
        treeview.column(c, width=180 if c != "Detail" else 360, anchor="w")
    treeview.pack(fill="both", expand=True, padx=10, pady=10)

    # Pre-populate rows
    try:
        tree = ET.parse(selected_xml_path)
        root_el = tree.getroot()
        servers_el = get_servers_root(root_el)
        rows = []
        for srv in servers_el.findall('Server'):
            name = (srv.findtext('Name') or '').strip()
            host = (srv.findtext('Host') or '').strip()
            if not name or not host:
                continue
            iid = treeview.insert('', 'end', values=(name, host, 'Pending…', ''))
            rows.append((iid, name, host))
    except Exception as e:
        messagebox.showerror("Parse Error", str(e))
        win.destroy()
        return

    status_var = tk.StringVar(value="Running reachability tests…")
    status = tk.Label(win, textvariable=status_var, anchor="w")
    status.pack(fill="x", padx=10, pady=(0,10))

    stop_flag = {"stop": False}

    def update_row(name, host, ok, detail):
        # Find iid by name+host (simple linear; small N)
        for iid, n, h in rows:
            if n == name and h == host:
                treeview.item(iid, values=(n, h, "OK" if ok else "FAIL", detail))
                break

    def done():
        status_var.set("Done.")

    threading.Thread(target=test_connectivity_reachability, args=(selected_xml_path, update_row, done), daemon=True).start()

# -------- GUI --------
root = tk.Tk()
root.title("Add Printer to FileZilla XML")

# File chooser row
xml_path_var = tk.StringVar(value="<No file selected>")
choose_btn = tk.Button(root, text="Select XML…", command=choose_xml_file)
choose_btn.grid(row=0, column=0, padx=10, pady=(12, 6), sticky="w")
xml_label = tk.Label(root, textvariable=xml_path_var, anchor="w", width=60)
xml_label.grid(row=0, column=1, padx=10, pady=(12, 6), sticky="w")

# Labels and Entry fields
row = 1

tk.Label(root, text="Printer Name").grid(row=row + 0, column=0, padx=10, pady=5, sticky="e")
tk.Label(root, text="IP Address").grid(row=row + 1, column=0, padx=10, pady=5, sticky="e")
tk.Label(root, text="Access Code").grid(row=row + 2, column=0, padx=10, pady=5, sticky="e")
tk.Label(root, text="Colour (1-7, optional)").grid(row=row + 3, column=0, padx=10, pady=5, sticky="e")

name_entry = tk.Entry(root)
ip_entry = tk.Entry(root)
access_entry = tk.Entry(root)
colour_entry = tk.Entry(root)

name_entry.grid(row=row + 0, column=1, padx=10, pady=5, sticky="we")
ip_entry.grid(row=row + 1, column=1, padx=10, pady=5, sticky="we")
access_entry.grid(row=row + 2, column=1, padx=10, pady=5, sticky="we")
colour_entry.grid(row=row + 3, column=1, padx=10, pady=5, sticky="we")

# Buttons (disabled until XML file is chosen)
add_button = tk.Button(root, text="Add / Update Printer", command=add_printer, state=tk.DISABLED)
add_button.grid(row=row + 4, column=0, pady=12, sticky="we")
reassign_button = tk.Button(root, text="Reassign Colours Now", command=reassign_only, state=tk.DISABLED)
reassign_button.grid(row=row + 4, column=1, pady=12, sticky="we")

# Connectivity test button (flagged)
if ENABLE_CONNECTIVITY_CHECK:
    test_button = tk.Button(root, text="Test Connectivity", command=open_connectivity_window, state=tk.DISABLED)
    test_button.grid(row=row + 5, column=0, columnspan=2, pady=(0,12), sticky="we")
else:
    test_button = tk.Button(root, text="Test Connectivity", state=tk.DISABLED)
    test_button.grid(row=row + 5, column=0, columnspan=2, pady=(0,12), sticky="we")

# Make column 1 grow
root.grid_columnconfigure(1, weight=1)

root.mainloop()
