
import os
import re
import html
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

APP_NAME = "CK3 Loc Vanilla Change Checker"

# Matches typical Paradox localization lines:
# key:0 "Text"
# key:1 "Text"
# key: "Text"
# Also tolerates leading spaces.
LOC_RE = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')

# Language header lines like:
# l_english:
# l_russian:
LANG_HEADER_RE = re.compile(r'^\s*l_[A-Za-z_]+:\s*$')


def normalize_value(value: str) -> str:
    """
    Keep the value mostly raw, but normalize line endings and surrounding whitespace.
    CK3 localization text can contain formatting, variables, icons, color tags, etc.
    We do NOT strip internal spaces or unescape CK3 sequences.
    """
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def read_loc_folder(folder: Path):
    """
    Returns:
      dict[key] = {
          "value": str,
          "file": str,
          "line": int,
          "duplicates": list[entry]
      }

    If a key appears multiple times, the last occurrence wins.
    Duplicates are still kept for diagnostics.
    """
    data = {}
    folder = Path(folder)

    for path in sorted(folder.rglob("*.yml")):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="cp1251", errors="replace")

        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            if line.lstrip().startswith("#"):
                continue
            if LANG_HEADER_RE.match(line):
                continue

            match = LOC_RE.match(line)
            if not match:
                continue

            key, value = match.groups()
            entry = {
                "value": normalize_value(value),
                "file": str(path),
                "line": line_no,
            }

            if key in data:
                previous = data[key]
                duplicates = previous.get("duplicates", [])
                duplicates.append({
                    "value": previous["value"],
                    "file": previous["file"],
                    "line": previous["line"],
                })
                entry["duplicates"] = duplicates
            else:
                entry["duplicates"] = []

            data[key] = entry

    return data


def escape(s):
    if s is None:
        return ""
    return html.escape(str(s), quote=False)


def rel_path(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except Exception:
        return str(path)


def make_report(
    mod_folder: Path,
    old_folder: Path,
    new_folder: Path,
    changed,
    missing_old,
    missing_new,
    mod_duplicates,
    old_count,
    new_count,
    mod_count,
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_path = Path.cwd() / f"ck3_loc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    changed_blocks = []
    for item in changed:
        key = item["key"]
        mod = item["mod"]
        old = item["old"]
        new = item["new"]

        changed_blocks.append(f"""
<section class="key-card">
  <div class="green-separator"></div>
  <div class="key-header">
    <div>
      <h2>{escape(key)}</h2>
      <div class="fileline">Mod file: {escape(rel_path(mod["file"], mod_folder))}:{mod["line"]}</div>
      <div class="fileline">Old vanilla: {escape(rel_path(old["file"], old_folder))}:{old["line"]}</div>
      <div class="fileline">New vanilla: {escape(rel_path(new["file"], new_folder))}:{new["line"]}</div>
    </div>
  </div>

  <div class="values">
    <div class="value-box mod">
      <div class="label">YOUR MOD</div>
      <pre>{escape(mod["value"])}</pre>
    </div>
    <div class="value-box old">
      <div class="label">OLD VANILLA</div>
      <pre>{escape(old["value"])}</pre>
    </div>
    <div class="value-box new">
      <div class="label">NEW VANILLA</div>
      <pre>{escape(new["value"])}</pre>
    </div>
  </div>
</section>
""")

    missing_old_html = ""
    if missing_old:
        rows = "\n".join(
            f"<tr><td>{escape(x['key'])}</td><td>{escape(rel_path(x['mod']['file'], mod_folder))}:{x['mod']['line']}</td></tr>"
            for x in missing_old
        )
        missing_old_html = f"""
<details class="diagnostic collapsed-section">
  <summary>Mod keys not found in old vanilla — {len(missing_old)}</summary>
  <p>This is usually fine if these are custom mod keys. This section is collapsed by default so it does not clutter the main report.</p>
  <table><tr><th>Key</th><th>Mod file</th></tr>{rows}</table>
</details>
"""

    missing_new_html = ""
    if missing_new:
        rows = "\n".join(
            f"<tr><td>{escape(x['key'])}</td><td>{escape(rel_path(x['mod']['file'], mod_folder))}:{x['mod']['line']}</td><td>{escape(rel_path(x['old']['file'], old_folder))}:{x['old']['line']}</td></tr>"
            for x in missing_new
        )
        missing_new_html = f"""
<section class="diagnostic warning">
  <h2>Keys that existed in old vanilla but are missing in new vanilla</h2>
  <p>Paradox may have removed or renamed these keys.</p>
  <table><tr><th>Key</th><th>Mod file</th><th>Old vanilla</th></tr>{rows}</table>
</section>
"""

    duplicates_html = ""
    if mod_duplicates:
        rows = "\n".join(
            f"<tr><td>{escape(k)}</td><td>{count}</td></tr>"
            for k, count in sorted(mod_duplicates.items())
        )
        duplicates_html = f"""
<section class="diagnostic">
  <h2>Duplicate keys in the mod folder</h2>
  <p>The last found value was used for comparison.</p>
  <table><tr><th>Key</th><th>Previous occurrences</th></tr>{rows}</table>
</section>
"""

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CK3 Localization Report</title>
<style>
  :root {{
    --bg: #101410;
    --card: #171d17;
    --card2: #1d241d;
    --text: #edf5ed;
    --muted: #aebaae;
    --green: #31d36b;
    --green2: #1f8f49;
    --border: #2b382b;
    --old: #292418;
    --new: #182524;
    --mod: #211d2a;
  }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: "Segoe UI", Arial, sans-serif;
    line-height: 1.45;
  }}
  header {{
    padding: 28px 36px;
    background: linear-gradient(135deg, #162216, #111711);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  h1 {{
    margin: 0 0 10px 0;
    font-size: 28px;
  }}
  .summary {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 18px;
  }}
  .pill {{
    background: var(--card2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 8px 12px;
    color: var(--muted);
  }}
  main {{
    padding: 28px 36px 60px;
  }}
  .key-card {{
    margin: 0 0 28px 0;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 12px 28px rgba(0,0,0,.25);
  }}
  .green-separator {{
    height: 7px;
    background: linear-gradient(90deg, var(--green), var(--green2));
  }}
  .key-header {{
    padding: 18px 20px 8px;
  }}
  .key-header h2 {{
    margin: 0 0 8px 0;
    color: #dfffe9;
    font-size: 21px;
    word-break: break-word;
  }}
  .fileline {{
    color: var(--muted);
    font-size: 13px;
    margin: 2px 0;
    word-break: break-word;
  }}
  .values {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
    padding: 14px 20px 20px;
  }}
  @media (min-width: 1100px) {{
    .values {{
      grid-template-columns: 1fr 1fr 1fr;
    }}
  }}
  .value-box {{
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    min-width: 0;
  }}
  .value-box.mod {{ background: var(--mod); }}
  .value-box.old {{ background: var(--old); }}
  .value-box.new {{ background: var(--new); }}
  .label {{
    padding: 9px 12px;
    background: rgba(255,255,255,.045);
    color: #d8f8df;
    font-weight: 700;
    letter-spacing: .04em;
    font-size: 12px;
  }}
  pre {{
    margin: 0;
    padding: 13px 12px 16px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-family: Consolas, "Courier New", monospace;
    font-size: 14px;
  }}
  .diagnostic {{
    margin: 28px 0;
    padding: 20px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
  }}
  details.diagnostic {{
    padding: 0;
  }}
  details.diagnostic > summary {{
    cursor: pointer;
    padding: 18px 20px;
    color: #dfffe9;
    font-size: 18px;
    font-weight: 700;
    list-style-position: inside;
  }}
  details.diagnostic > p,
  details.diagnostic > table {{
    margin-left: 20px;
    margin-right: 20px;
  }}
  details.diagnostic > table {{
    width: calc(100% - 40px);
    margin-bottom: 20px;
  }}
  .diagnostic.warning {{
    border-color: #67562b;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 14px;
  }}
  th, td {{
    border-bottom: 1px solid var(--border);
    padding: 9px 8px;
    text-align: left;
    vertical-align: top;
    word-break: break-word;
  }}
  th {{
    color: #dfffe9;
  }}
  .empty {{
    padding: 26px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    color: var(--muted);
  }}
</style>
</head>
<body>
<header>
  <h1>CK3 Localization Vanilla Change Report</h1>
  <div>Created: {escape(now)}</div>
  <div class="summary">
    <div class="pill">Mod keys: {mod_count}</div>
    <div class="pill">Old vanilla keys: {old_count}</div>
    <div class="pill">New vanilla keys: {new_count}</div>
    <div class="pill">Changed vanilla keys used by mod: {len(changed)}</div>
    <div class="pill">Missing in new vanilla: {len(missing_new)}</div>
    <div class="pill">Not found in old vanilla: {len(missing_old)}</div>
  </div>
</header>
<main>
  {''.join(changed_blocks) if changed_blocks else '<div class="empty">No changed vanilla keys were found among the keys used by your mod.</div>'}
  {missing_new_html}
  {missing_old_html}
  {duplicates_html}
</main>
</body>
</html>
"""
    report_path.write_text(html_doc, encoding="utf-8")
    return report_path


def compare_folders(mod_folder, old_folder, new_folder):
    mod_folder = Path(mod_folder)
    old_folder = Path(old_folder)
    new_folder = Path(new_folder)

    mod_data = read_loc_folder(mod_folder)
    old_data = read_loc_folder(old_folder)
    new_data = read_loc_folder(new_folder)

    changed = []
    missing_old = []
    missing_new = []

    for key in sorted(mod_data.keys()):
        mod_entry = mod_data[key]
        old_entry = old_data.get(key)
        new_entry = new_data.get(key)

        if old_entry is None:
            missing_old.append({"key": key, "mod": mod_entry})
            continue

        if new_entry is None:
            missing_new.append({"key": key, "mod": mod_entry, "old": old_entry})
            continue

        if old_entry["value"] != new_entry["value"]:
            changed.append({
                "key": key,
                "mod": mod_entry,
                "old": old_entry,
                "new": new_entry,
            })

    mod_duplicates = {
        key: len(entry.get("duplicates", []))
        for key, entry in mod_data.items()
        if entry.get("duplicates")
    }

    return {
        "changed": changed,
        "missing_old": missing_old,
        "missing_new": missing_new,
        "mod_duplicates": mod_duplicates,
        "mod_count": len(mod_data),
        "old_count": len(old_data),
        "new_count": len(new_data),
    }


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("880x470")
        self.minsize(760, 420)

        self.mod_var = tk.StringVar()
        self.old_var = tk.StringVar()
        self.new_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select three folders and run the check.")

        self._build_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)

        title = ttk.Label(root, text=APP_NAME, font=("Segoe UI", 17, "bold"))
        title.pack(anchor="w", pady=(0, 14))

        self._folder_row(root, "Your mod localization folder", self.mod_var)
        self._folder_row(root, "Old vanilla localization folder", self.old_var)
        self._folder_row(root, "New vanilla localization folder", self.new_var)

        note = ttk.Label(
            root,
            text=(
                "The program takes all localization keys from your mod folder and compares "
                "the values of those same keys between old vanilla and new vanilla. "
                "Detected changes are written to an HTML report."
            ),
            wraplength=820,
            foreground="#555555"
        )
        note.pack(anchor="w", pady=(10, 16))

        btns = ttk.Frame(root)
        btns.pack(fill="x", pady=(4, 12))

        check_btn = ttk.Button(btns, text="Check and open report", command=self.run_check)
        check_btn.pack(side="left")

        quit_btn = ttk.Button(btns, text="Close", command=self.destroy)
        quit_btn.pack(side="left", padx=(10, 0))

        sep = ttk.Separator(root)
        sep.pack(fill="x", pady=12)

        status_label = ttk.Label(root, textvariable=self.status_var, wraplength=820)
        status_label.pack(anchor="w")

    def _folder_row(self, parent, label, var):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=7)

        lab = ttk.Label(frame, text=label, width=34)
        lab.pack(side="left")

        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 8))

        btn = ttk.Button(frame, text="Browse", command=lambda: self.choose_folder(var))
        btn.pack(side="left")

    def choose_folder(self, var):
        folder = filedialog.askdirectory()
        if folder:
            var.set(folder)

    def run_check(self):
        mod_folder = self.mod_var.get().strip()
        old_folder = self.old_var.get().strip()
        new_folder = self.new_var.get().strip()

        for label, folder in [
            ("mod folder", mod_folder),
            ("old vanilla folder", old_folder),
            ("new vanilla folder", new_folder),
        ]:
            if not folder:
                messagebox.showerror("Folder not selected", f"The {label} was not selected.")
                return
            if not Path(folder).exists():
                messagebox.showerror("Folder not found", f"The {label} was not found:\n{folder}")
                return

        try:
            self.status_var.set("Reading yml files and comparing keys...")
            self.update_idletasks()

            result = compare_folders(mod_folder, old_folder, new_folder)
            report_path = make_report(
                Path(mod_folder),
                Path(old_folder),
                Path(new_folder),
                result["changed"],
                result["missing_old"],
                result["missing_new"],
                result["mod_duplicates"],
                result["old_count"],
                result["new_count"],
                result["mod_count"],
            )

            self.status_var.set(
                f"Done. Changed keys: {len(result['changed'])}. "
                f"Report: {report_path}"
            )
            webbrowser.open(report_path.as_uri())

        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status_var.set(f"Error: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
