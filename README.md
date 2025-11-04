# FileZilla Bambu Printer Manager

A Tkinter-based utility for managing **Bambu Lab printer FTP profiles** inside FileZilla’s `sitemanager.xml` configuration file.

This tool is designed for environments with **multiple Bambu P1 / P1P / P1S / X1 / X1C printers**, such as production print farms, labs, and makerspaces.

---

## ✨ Features

| Feature | Description |
|--------|-------------|
| Add / Update Printer | Adds new FTP profiles or updates existing ones cleanly. |
| Auto-Sort | Printers are sorted **numerically by name** (e.g., One → Two → Ten → Eleven). |
| Colour Cycling | Printer colour tags automatically rotate **1 → 7** and repeat. |
| Base64 Password Encoding | Access codes are stored with correct FileZilla encoding. |
| Backup Safety | Every change automatically writes a `.bak` file. |
| Connectivity Check | Validates printers are reachable using a **TLS handshake** on port 990. |

---

## ✅ Requirements

- Python **3.8+**
- No external libraries required (standard library only)
- FileZilla configuration file (`sitemanager.xml`)

---

## 🚀 Usage

### 1. Launch the App
```bash
python3 tkinter_add_printer.py
```

### 2. Select the FileZilla XML
Click:
```
Select XML…
```
Choose your FileZilla **sitemanager.xml** file.

### 3. Add a Printer
| Field | Example | Notes |
|-------|---------|-------|
| Printer Name | `Seven` or `TwentyOne` | Name determines sort order. |
| IP Address | `192.168.1.234` | Must match printer's LAN IP. |
| Access Code | `94679547` | Found on printer screen in LAN FTP settings. |
| Colour | *(optional)* | Leave blank to auto-assign. |

Then click:
```
Add / Update Printer
```

### 4. Reassign Colours / Normalize Ordering
```
Reassign Colours Now
```
Ensures:
- Proper numeric sorting
- Colour cycling across printers

### 5. Check Printer Connectivity
```
Test Connectivity
```
This performs only:
- TCP connect → TLS handshake on **port 990**

It **does not** attempt login or file upload.

---

## 🎨 Colour Assignment Rules

Colours follow a repeating cycle:
```
1, 2, 3, 4, 5, 6, 7, 1, 2, 3, …
```
Based on sorted printer order.

Example for 10 printers:
```
One → Colour 1
Two → Colour 2
Three → Colour 3
Four → Colour 4
Five → Colour 5
Six → Colour 6
Seven → Colour 7
Eight → Colour 1
Nine → Colour 2
Ten → Colour 3
```

---

## 🛟 Backups
Every time the XML is modified, a backup is automatically created:
```
sitemanager.xml.bak
```
If something goes wrong, restore by replacing the modified file with the backup.

---

## 📂 Repository Structure
```
.
├── tkinter_add_printer.py   # The application
└── README.md                 # This file
```

---

## 📝 License
MIT License — free to use, modify, and redistribute.

---

## 💬 Credits
Originally developed to support **multi-printer production workflows** in print farms.

If you add functionality, improvements are welcome.

---
