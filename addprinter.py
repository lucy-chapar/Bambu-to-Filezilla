import tkinter as tk
from tkinter import messagebox, filedialog
import base64
import xml.etree.ElementTree as ET
import os

# Global to hold the selected XML path
selected_xml_path = None


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


def add_printer():
    """Append a new <Server> to the chosen XML file with FileZilla-style formatting."""
    global selected_xml_path

    if not selected_xml_path:
        messagebox.showerror("No XML Selected", "Please select the FileZilla XML file first.")
        return

    name = name_entry.get().strip()
    ip = ip_entry.get().strip()
    access_code = access_entry.get().strip()
    colour = colour_entry.get().strip()

    if not (name and ip and access_code):
        messagebox.showerror("Missing Data", "Printer Name, IP Address, and Access Code are required.")
        return

    # Validate colour (optional; default to 1 if empty). Must be 1-7
    if not colour:
        colour = "1"
    try:
        cval = int(colour)
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

        # Find or create <Servers>
        servers = root.find('Servers')
        if servers is None:
            servers = ET.SubElement(root, 'Servers')

        # Create <Server> block
        server = ET.SubElement(servers, 'Server')
        ET.SubElement(server, 'Host').text = ip
        ET.SubElement(server, 'Port').text = '990'
        ET.SubElement(server, 'Protocol').text = '3'
        ET.SubElement(server, 'Type').text = '0'
        ET.SubElement(server, 'User').text = 'bblp'
        ET.SubElement(server, 'Pass', encoding="base64").text = encoded_pass
        ET.SubElement(server, 'Logontype').text = '1'
        ET.SubElement(server, 'PasvMode').text = 'MODE_DEFAULT'
        ET.SubElement(server, 'EncodingType').text = 'Auto'
        ET.SubElement(server, 'BypassProxy').text = '0'
        ET.SubElement(server, 'Name').text = name
        ET.SubElement(server, 'Colour').text = str(cval)
        ET.SubElement(server, 'SyncBrowsing').text = '0'
        ET.SubElement(server, 'DirectoryComparison').text = '0'

        # Pretty-print with tabs like FileZilla export
        if hasattr(ET, 'indent'):
            # Python 3.9+
            ET.indent(tree, space="\t", level=0)

        # Write back (force XML declaration)
        tree.write(selected_xml_path, encoding='UTF-8', xml_declaration=True)

        messagebox.showinfo(
            "Success",
            f"Printer '{name}' added to:\n{selected_xml_path}"
        )

        # Clear inputs for next entry
        name_entry.delete(0, tk.END)
        ip_entry.delete(0, tk.END)
        access_entry.delete(0, tk.END)
        colour_entry.delete(0, tk.END)

    except Exception as e:
        messagebox.showerror("Error Writing XML", f"{e}")


# GUI Setup
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
tk.Label(root, text="Colour (1-7)").grid(row=row + 3, column=0, padx=10, pady=5, sticky="e")

name_entry = tk.Entry(root)
ip_entry = tk.Entry(root)
access_entry = tk.Entry(root)
colour_entry = tk.Entry(root)

name_entry.grid(row=row + 0, column=1, padx=10, pady=5, sticky="we")
ip_entry.grid(row=row + 1, column=1, padx=10, pady=5, sticky="we")
access_entry.grid(row=row + 2, column=1, padx=10, pady=5, sticky="we")
colour_entry.grid(row=row + 3, column=1, padx=10, pady=5, sticky="we")

# Add button (disabled until XML file is chosen)
add_button = tk.Button(root, text="Add Printer", command=add_printer, state=tk.DISABLED)
add_button.grid(row=row + 4, column=0, columnspan=2, pady=12)

# Make column 1 grow
root.grid_columnconfigure(1, weight=1)

root.mainloop()
