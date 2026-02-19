#!/usr/bin/env python3
import sqlite3
import datetime
import math
import os
import subprocess
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.align import Align

# --- Configuration and Initialization (Arch Linux Optimized) ---

# Follows XDG standards for Arch: ~/.local/share/budget-buddy
DATA_DIR = os.path.join(os.path.expanduser('~'), '.local/share/budget-buddy')
ARCHIVE_DIR = os.path.join(DATA_DIR, 'archives')

DATABASE_EXPENSES = os.path.join(DATA_DIR, 'expenses.db')
DATABASE_SETTINGS = os.path.join(DATA_DIR, 'settings.db')
UI_WIDTH = 220  # Adjust this number to your preference
CONSOLE = Console()

PROTECTED_CATEGORIES = [
    "Uncategorized", "Salary", "Savings Transfer", "Rent", 
    "Groceries", "Subscriptions", "Online Shopping", "Household"
]

def get_dashboard_line():
    # We call a uniquely named function to avoid conflicts
    d = get_stats_for_dash()
    
    # Simple ANSI colors
    R, G, Y, B, CL = "\033[91m", "\033[92m", "\033[93m", "\033[1m", "\033[0m"
    
    net_col = G if d[2] >= 0 else R # Using index numbers to be 100% safe
    
    return (f"Today: {R}{B}£{d[3]:.0f}{CL} | "
            f"Month: {R}{B}£{d[1]:.0f}{CL} | "
            f"Bills: {Y}{B}£{d[4]:.0f}{CL} | "
            f"Net: {net_col}{B}£{d[2]:.0f}{CL}")

def get_stats_for_dash():
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        # 0: Income
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='income' AND date LIKE ?", (f"{month_prefix}%",))
        m_inc = cursor.fetchone()[0] or 0.0
        # 1: Expenses
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND date LIKE ?", (f"{month_prefix}%",))
        m_exp = cursor.fetchone()[0] or 0.0
        # 3: Today
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND date = ?", (today_str,))
        today = cursor.fetchone()[0] or 0.0
        # 4: Recurring
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND date LIKE ? AND description LIKE 'Recurring payment:%'", (f"{month_prefix}%",))
        recur = cursor.fetchone()[0] or 0.0
        
    return (m_inc, m_exp, (m_inc - m_exp), today, recur)
                                    
def display_dashboard(message=""):
    """Renders the main TUI dashboard for Arch Linux."""
    os.system('clear')
    
    now = datetime.datetime.now()
    header_date = now.strftime("%A, %d %b %Y | %H:%M")
    
    header_content = Text(f"BUDGET BUDDY TUI | {header_date}", style="bold white on purple")
    
    CONSOLE.print(Align.center(Panel(header_content, title_align="left", border_style="purple", width=UI_WIDTH, expand=False)))
    
    # Fetch the data from your existing summary function
    stats = get_financial_summary()
        
        # Manually unpack the tuple into the names the TUI expects.
        # We use a try/except so it doesn't crash if the format changes again.
    try:
        total_income = stats[0]
        total_expenses = stats[1]
        net_balance = stats[2]
    except (IndexError, TypeError):
        # Fallback values if the tuple is missing data
        total_income = total_expenses = net_balance = 0.0
    
    # 1. Overview Panel
    balance_style = "bold green" if net_balance >= 0 else "bold red"
    overview_text = Text()
    overview_text.append("Current Month Income:   ", style="green")
    overview_text.append(f"+£{total_income:,.2f}\n", style="bold green")
    overview_text.append("Current Month Expenses: ", style="red")
    overview_text.append(f"£{total_expenses:,.2f}\n", style="bold red")
    overview_text.append("MONTHLY NET:            ", style="cyan")
    overview_text.append(f"£{net_balance:,.2f}", style=balance_style)
    
    overview_panel = Panel(overview_text, title="FINANCIAL OVERVIEW", border_style="cyan", width=87)

    # 2. Savings Goal Panel
    goal_target, current_saved = get_savings_goal()
    if goal_target > 0:
        progress_val = min((current_saved / goal_target) * 100, 100)
        progress_bar = Progress(
            TextColumn(f"Saved: £{current_saved:,.0f} / £{goal_target:,.0f}"),
            BarColumn(bar_width=20, style="yellow", complete_style="bold green"),
            TextColumn(f"{progress_val:.0f}%", style="bold yellow"),
            console=CONSOLE,
            transient=True
        )
        task_id = progress_bar.add_task("Saving...", total=goal_target, completed=current_saved)
        savings_panel = Panel(Group(progress_bar.make_tasks_table(progress_bar.tasks)), title="SAVINGS GOAL", border_style="yellow", width=87)
    else:
        savings_panel = Panel("[yellow]No savings goal set. Use Option 8![/yellow]", title="SAVINGS GOAL", border_style="yellow", width=87)

    # 3. Menu Panel
    menu_table = Table.grid(padding=(0, 1))
    menu_options = [
        ("1. Add Transaction", "bold green"), ("2. View History", "bold cyan"), 
        ("3. Filter Category", "bold magenta"), ("4. Weekly Summary", "yellow"),
        ("5. Monthly Summary", "yellow"), ("6. Upcoming Calendar", "bright_blue"),
        ("7. Delete Transaction", "bold red"), ("8. Set Savings Goal", "yellow"),
        ("9. Add to Savings", "green"), ("10. Manage Templates", "orange1"),
        ("11. Apply Recurring", "green"), ("12. Exit", "bold white"),
        ("13. Manage Categories", "bold yellow"), ("14. Monthly Wrap-up", "bold blue")
    ]
    for opt, style in menu_options:
        parts = opt.split(". ", 1)
        menu_table.add_row(f"[bold white]{parts[0]}.[/bold white]", Text(parts[1], style=style))
    menu_panel = Panel(menu_table, title="MENU", border_style="magenta", width=87)

    # 4. Recent Transactions Panel
    recent_txs = get_last_n_transactions(5)
    recent_tx_table = Table(show_header=True, header_style="bold green", box=None, padding=(0, 1))
    recent_tx_table.add_column("ID", style="dim", width=4)
    recent_tx_table.add_column("Date", width=8)
    recent_tx_table.add_column("Description", max_width=20) 
    recent_tx_table.add_column("Amount", justify="right", width=12)

    for tid, amount, category, description, date_str, t_type in recent_txs:
        display_name = description or category
        if description and "Recurring payment:" in description:
            display_name = f"🔄 {description.replace('Recurring payment: ', '')}"
        elif description == "Transfer to Savings Goal":
            display_name = " Savings"
        
        try:
            display_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%m-%d")
        except:
            display_date = date_str

        style = "bold green" if t_type == 'income' else "bold red"
        prefix = "+" if t_type == 'income' else "-"
        recent_tx_table.add_row(str(tid), display_date, display_name, Text(f"{prefix}£{amount:,.0f}", style=style))

    recent_tx_panel = Panel(recent_tx_table, title="LAST 5 TRANSACTIONS", border_style="green", width=87)

    # --- FINAL RENDERING ---
    CONSOLE.print(overview_panel)
    CONSOLE.print(savings_panel)
    CONSOLE.print(menu_panel)
    CONSOLE.print(recent_tx_panel)

    if message:
        CONSOLE.print(Panel(Text.from_markup(message), title="NOTIFICATION", border_style="yellow", width=87))

    return input("\nSelect an option (1-14): ")

def get_last_n_transactions(n=5):
    """Fetches the most recent N transactions for the dashboard."""
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        # Fetch all columns needed for the dashboard display
        cursor.execute("""
            SELECT id, amount, category, description, date, type 
            FROM transactions 
            ORDER BY date DESC, id DESC 
            LIMIT ?
        """, (n,))
        return cursor.fetchall()

def get_financial_summary():
    """Calculates granular totals for the dashboard and TUI."""
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='income' AND date LIKE ?", (f"{month_prefix}%",))
        m_inc = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND date LIKE ?", (f"{month_prefix}%",))
        m_exp = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND date = ?", (today_str,))
        today_spent = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND date LIKE ? AND description LIKE 'Recurring payment:%'", (f"{month_prefix}%",))
        recurring_total = cursor.fetchone()[0] or 0.0
        
    # We return a dictionary. This is foolproof.
    return {
        "m_inc": m_inc,
        "m_exp": m_exp,
        "net": m_inc - m_exp,
        "today": today_spent,
        "recurring": recurring_total
    }
        
def show_temporary_view(title, content):
    """Clears screen and displays content with a standard Linux feel."""
    os.system('clear')
    CONSOLE.print(Panel(f"[bold magenta]{title}[/bold magenta]", border_style="magenta"))
    CONSOLE.print(content)
    CONSOLE.input("\n[bold green]Press Enter to return to menu...[/bold green]")
def initialize_db():
    """Initializes databases with WAL mode for better performance on Linux SSDs."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
        
    # Initialize Expenses
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        # WAL mode improves concurrent read/write performance
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                type TEXT NOT NULL
            )
        """)

    # Initialize Settings
    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recurring_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, 
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                due_day INTEGER DEFAULT 1
            )
        """)
        conn.execute("CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)")
        
        # Table for app metadata (like last_check date)
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        
        for cat in PROTECTED_CATEGORIES:
            conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))

def db_check_and_migrate():
    """Generic migration handler to ensure schema stays up to date."""
    # Adding 'type' column to old Termux databases if necessary
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        try:
            conn.execute("SELECT type FROM transactions LIMIT 1")
        except sqlite3.OperationalError:
            CONSOLE.print("[yellow]Migrating: Adding 'type' column...[/yellow]")
            conn.execute("ALTER TABLE transactions ADD COLUMN type TEXT DEFAULT 'expense'")

# --- Transaction Logic (Optimized for Desktop) ---

def add_transaction():
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold magenta]Add New Transaction[/bold magenta]", border_style="magenta"))
    
    # Input Type
    while True:
        t_input = input("Type [I]ncome or [E]xpense: ").lower()
        if t_input in ('i', 'income'): 
            transaction_type = 'income'
            break
        elif t_input in ('e', 'expense'): 
            transaction_type = 'expense'
            break
        CONSOLE.print("[bold red]Invalid. Enter 'I' or 'E'.[/bold red]")

    # Input Amount
    while True:
        try:
            amount = float(input("Enter amount (£): "))
            if amount <= 0: raise ValueError
            break
        except ValueError: 
            CONSOLE.print("[bold red]Please enter a positive number.[/bold red]")

    # Category Selection
    categories = get_categories_with_ids()
    cat_table = Table(title="Categories", header_style="bold cyan", box=None)
    cat_table.add_column("ID", style="yellow")
    cat_table.add_column("Name", style="cyan")
    for cid, name in categories:
        cat_table.add_row(str(cid), name)
    
    CONSOLE.print(cat_table)
    
    while True:
        cat_choice = input("Enter Category ID or Name (C to cancel): ").strip()
        if cat_choice.upper() == 'C': return "[yellow]Cancelled.[/yellow]"
        
        category = get_category_name_by_id(cat_choice)
        if not category: # If not an ID, check if it's a new name
            if input(f"Create new category '{cat_choice}'? (y/n): ").lower() == 'y':
                add_category_to_db(cat_choice)
                category = cat_choice
                break
            continue
        break

    description = input("Description: ").strip()
    
    # Date Handling
    default_date = datetime.datetime.now()
    date_input = input(f"Date (DD-MM-YYYY, default: {default_date.strftime('%d-%m-%Y')}): ").strip()
    dt_obj = validate_date(date_input) or default_date
    
    db_date = dt_obj.strftime("%Y-%m-%d")
    disp_date = dt_obj.strftime("%d %b %Y")

    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        conn.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                    (amount, category, description, db_date, transaction_type))
    
    return f"[bold green]Saved: {transaction_type.upper()} £{amount:,.2f} on {disp_date}.[/bold green]"

def fetch_category_names():
    """Fetches list of all category names from the settings database."""
    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name ASC")
        return [row[0] for row in cursor.fetchall()]

def get_categories_with_ids():
    """Assigns a sequential display ID to category names for the TUI."""
    category_names = fetch_category_names()
    return [(i, name) for i, name in enumerate(category_names, 1)]

def get_category_name_by_id(cat_input):
    """Maps a user's ID input or partial name back to a valid category."""
    categories = get_categories_with_ids()
    
    # Try to match by ID number
    try:
        cat_id = int(cat_input)
        for i, name in categories:
            if i == cat_id:
                return name
    except ValueError:
        # If not a number, check for an exact name match (case insensitive)
        for _, name in categories:
            if name.lower() == cat_input.lower():
                return name
    return None

def validate_date(date_str):
    """Validates DD-MM-YYYY format and returns a datetime object."""
    if not date_str: 
        return None
    try:
        return datetime.datetime.strptime(date_str, "%d-%m-%Y")
    except ValueError:
        return None

def get_recurring_templates():
    """Fetches all recurring payment templates."""
    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, amount, category, description, due_day FROM recurring_templates ORDER BY category ASC, due_day ASC")
        return cursor.fetchall()

def manage_recurring_templates():
    """TUI for adding/editing/deleting recurring payment templates."""
    templates = get_recurring_templates()
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold orange1]Manage Recurring Templates[/bold orange1]", border_style="orange1"))
    
    if not templates:
        CONSOLE.print("[yellow]No templates found.[/yellow]")
    else:
        grouped = {}
        for tid, name, amt, cat, desc, day in templates:
            grouped.setdefault(cat, []).append({'id': tid, 'name': name, 'amount': amt, 'day': day})
            
        cards = []
        for cat, items in grouped.items():
            table = Table(show_header=True, header_style="bold dim", box=None)
            table.add_column("ID", style="cyan", width=4)
            table.add_column("Day", style="yellow", width=4)
            table.add_column("Name", style="bold white")
            table.add_column("Amount", justify="right", style="red")
            
            for item in items:
                table.add_row(str(item['id']), str(item['day']), item['name'], f"£{item['amount']:,.2f}")
            
            cards.append(Panel(table, title=f"[bold orange1]{cat}[/bold orange1]", border_style="orange1"))
        
        CONSOLE.print(Group(*cards))
        
    CONSOLE.print("\n[1] Add New | [2] Delete | [3] Edit | [C] Cancel")
    # Using CONSOLE.input here fixes the raw tag problem
    ch = CONSOLE.input("[bold white]Choice: [/bold white]").upper().strip()
    
    if ch == '1': return add_recurring_template()
    if ch == '2': return delete_recurring_template()
    if ch == '3': return edit_recurring_template() # New Option
    return "Cancelled."
    
def add_recurring_template():
    """Adds a new template to the settings database."""
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold green]Add Recurring Template[/bold green]"))
    name = input("Template Name: ").strip()
    if not name: return "[red]Cancelled (name required).[/red]"
    
    try:
        amt = float(input("Amount (£): "))
        day = int(input("Due Day (1-31): "))
    except ValueError:
        return "[red]Invalid input. Amount must be a number, Day must be 1-31.[/red]"
        
    cat = input("Category: ").strip() or "Uncategorized"
    desc = input("Description: ").strip()
    
    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        conn.execute("INSERT INTO recurring_templates (name, amount, category, description, due_day) VALUES (?, ?, ?, ?, ?)",
                    (name, amt, cat, desc, day))
    return f"[green]Added template: {name}[/green]"

def delete_recurring_template():
    """Deletes a template by ID."""
    tid = input("Enter Template ID to delete (C to cancel): ").strip()
    if tid.upper() == 'C': return "Cancelled."
    
    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        cur = conn.execute("DELETE FROM recurring_templates WHERE id = ?", (tid,))
        if cur.rowcount > 0:
            return f"[green]Deleted template ID {tid}[/green]"
    return "[red]ID not found.[/red]"

def edit_recurring_template():
    """Edits an existing template with 'Enter to keep' logic."""
    tid = CONSOLE.input("\n[bold cyan]Enter Template ID to edit (C to cancel): [/bold cyan]").strip()
    if tid.upper() == 'C' or not tid: return "Cancelled."

    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        conn.row_factory = sqlite3.Row # Allows us to access by name
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM recurring_templates WHERE id = ?", (tid,))
        template = cursor.fetchone()
        
        if not template:
            return "[red]Template ID not found.[/red]"

        CONSOLE.print(f"\n[italic]Editing: {template['name']}. Press Enter to keep current values.[/italic]\n")
        
        # We prompt for all fields found in your schema
        new_name = CONSOLE.input(f"Name [[white]{template['name']}[/white]]: ") or template['name']
        new_amt = CONSOLE.input(f"Amount [[white]{template['amount']}[/white]]: ") or template['amount']
        new_day = CONSOLE.input(f"Due Day [[white]{template['due_day']}[/white]]: ") or template['due_day']
        new_cat = CONSOLE.input(f"Category [[white]{template['category']}[/white]]: ") or template['category']
        new_desc = CONSOLE.input(f"Description [[white]{template['description']}[/white]]: ") or template['description']

        conn.execute("""
            UPDATE recurring_templates 
            SET name = ?, amount = ?, category = ?, description = ?, due_day = ? 
            WHERE id = ?
        """, (new_name, float(new_amt), new_cat, new_desc, int(new_day), tid))
        
    return f"[green]Updated template: {new_name}[/green]"
    
def apply_recurring_template():
    """Manually triggers a template to record a transaction today."""
    templates = get_recurring_templates()
    if not templates: 
        return "[red]No templates found.[/red]"
    
    # Map for easy selection
    t_map = {str(t[0]): t for t in templates}
    
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold green]Apply Recurring Payment Manually[/bold green]"))
    
    # --- ADDED DISPLAY LOGIC ---
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Name", min_width=20)
    table.add_column("Amount", justify="right")
    table.add_column("Category")

    for t in templates:
        # Adjust indices if your get_recurring_templates() returns columns differently
        # Original code uses: _, name, amt, cat, desc, _ = t_map[tid]
        table.add_row(str(t[0]), t[1], f"£{t[2]:,.2f}", t[3])
    
    CONSOLE.print(table)
    # ---------------------------
    
    tid = input("\nEnter Template ID to apply (C to cancel): ").strip()
    if tid.upper() == 'C': 
        return "Operation Cancelled."
    if tid not in t_map: 
        return "[red]Invalid ID. Please select a number from the list above.[/red]"
    
    # Unpack your map (Order must match your DB schema)
    _, name, amt, cat, desc, _ = t_map[tid]
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        conn.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                    (amt, cat, f"Recurring payment: {name}", today, 'expense'))
    
    return f"[green]Applied '{name}' (£{amt:,.2f}) to today's ledger.[/green]"
                
def get_scheduled_transactions():
    """Combines local templates and major expenses for the calendar."""
    now = datetime.datetime.now().date()
    ym = now.strftime("%Y-%m")
    templates = get_recurring_templates()
    
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        # Check what has already been paid this month
        cursor.execute(f"SELECT description FROM transactions WHERE date LIKE '{ym}-%'")
        recorded = [r[0] for r in cursor.fetchall()]
        
        # Get one-off major expenses (> £50) for the future
        cursor.execute("SELECT amount, description, date FROM transactions WHERE amount > 50 AND date >= ?", (now.strftime('%Y-%m-%d'),))
        major = cursor.fetchall()
    
    scheduled = []
    for _, name, amt, _, _, day in templates:
        try: d = datetime.date(now.year, now.month, day)
        except: d = datetime.date(now.year, now.month, 28)
        
        is_paid = f"Recurring payment: {name}" in recorded
        scheduled.append({'date': d.strftime("%Y-%m-%d"), 'amount': amt, 'desc': name, 'type': 'recurring', 'done': is_paid})

    for amt, desc, d_str in major:
        scheduled.append({'date': d_str, 'amount': amt, 'desc': desc, 'type': 'one-off', 'done': True})
        
    return scheduled

def upcoming_calendar():
    """Renders a 7-day calendar view with gcalcli integration."""
    now = datetime.datetime.now().date()
    start = now - datetime.timedelta(days=now.weekday()) # Start on Monday
    events = get_scheduled_transactions()
    
    # Try to fetch Google Calendar events if gcalcli is configured
    gcal_data = fetch_google_calendar_events() # Function from Section 3
    
    table = Table(title=f"Weekly Outlook (Starting {start.strftime('%d %b')})", show_header=True, padding=1, box=None)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for d in days:
        table.add_column(d, justify="center", style="bold cyan")
    
    row_cells = []
    for i in range(7):
        curr = start + datetime.timedelta(days=i)
        d_str = curr.strftime("%Y-%m-%d")
        
        cell = Text(curr.strftime("%d"), style="bold white")
        if curr == now: cell.style = "bold yellow on blue"
        elif curr < now: cell.style = "dim"
        
        for e in events:
            if e['date'] == d_str:
                icon = "✓" if e.get('done') else "!"
                color = "green" if e.get('done') else "red"
                cell.append(Text(f"\n{icon}£{e['amount']:.0f}", style=color))
        
        row_cells.append(cell)
        
    table.add_row(*row_cells)
    
    legend = Text.from_markup("\n[green]✓[/green] Paid | [red]![/red] Due/Large | [yellow]Blue[/yellow] Today")
    
    # If gcalcli returned data, show it below the table
    if "gcalcli" not in str(gcal_data) and gcal_data:
        gcal_panel = Panel(Text(str(gcal_data), style="dim"), title="Google Calendar Agenda", border_style="blue")
        show_temporary_view("Calendar", Group(table, legend, gcal_panel))
    else:
        show_temporary_view("Calendar", Group(table, legend))

def add_category_to_db(name):
    """Inserts a new category into the settings database."""
    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        try:
            conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            return f"[green]Added category: {name}[/green]"
        except sqlite3.IntegrityError:
            return f"[yellow]Category '{name}' already exists.[/yellow]"

def delete_category():
    """Deletes a category and reassigns its transactions."""
    cats = get_categories_with_ids()
    # Filter out protected ones
    deletable = [c for c in cats if c[1] not in PROTECTED_CATEGORIES]
    
    if not deletable:
        return "[yellow]No custom categories to delete.[/yellow]"

    table = Table(title="Delete Category", header_style="bold red")
    table.add_column("ID"); table.add_column("Name")
    for cid, name in deletable:
        table.add_row(str(cid), name)
    
    CONSOLE.print(table)
    choice = input("Enter ID to delete (C to cancel): ").strip()
    if choice.upper() == 'C': return "Cancelled."
    
    target_name = get_category_name_by_id(choice)
    if not target_name or target_name in PROTECTED_CATEGORIES:
        return "[red]Invalid selection or protected category.[/red]"

    # Reassign and Delete
    with sqlite3.connect(DATABASE_EXPENSES) as conn_e:
        conn_e.execute("UPDATE transactions SET category = 'Uncategorized' WHERE category = ?", (target_name,))
    
    with sqlite3.connect(DATABASE_SETTINGS) as conn_s:
        conn_s.execute("DELETE FROM categories WHERE name = ?", (target_name,))
        
    return f"[bold green]Category '{target_name}' removed. Transactions reassigned.[/bold green]"

def manage_categories_full():
    """Main menu for category management."""
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold yellow]Category Management[/bold yellow]", border_style="yellow"))
    
    cats = get_categories_with_ids()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID"); table.add_column("Name")
    for cid, name in cats:
        table.add_row(str(cid), name)
    
    CONSOLE.print(table)
    CONSOLE.print("\n[1] Add New | [2] Delete | [C] Cancel")
    ch = input("Choice: ").strip()
    
    if ch == '1':
        new_name = input("New category name: ").strip()
        return add_category_to_db(new_name) if new_name else "Cancelled."
    elif ch == '2':
        return delete_category()
    return "Cancelled."

def get_paginated_transactions(page=1, page_size=10):
    """Fetches transactions for a specific page."""
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_count = cursor.fetchone()[0]
        offset = (page - 1) * page_size
        
        cursor.execute("""
            SELECT id, amount, category, description, date, type 
            FROM transactions ORDER BY date DESC, id DESC LIMIT ? OFFSET ?
        """, (page_size, offset))
        transactions = cursor.fetchall()
        
    total_pages = math.ceil(total_count / page_size) if page_size > 0 else 1
    return transactions, total_count, total_pages

def render_transaction_cards(transactions):
    """Helper to turn database rows into Rich Panels (Cards)."""
    cards = []
    for tid, amount, cat, desc, d_db, t_type in transactions:
        # Date formatting for display
        try:
            d_disp = datetime.datetime.strptime(d_db, "%Y-%m-%d").strftime("%d %b %Y")
        except:
            d_disp = d_db

        style = "bold green" if t_type == 'income' else "bold red"
        symbol = "+" if t_type == 'income' else "-"
        
        # Internal layout for the card
        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="dim", width=12) # Label
        grid.add_column(style="bold white")     # Value
        
        grid.add_row("ID:", str(tid))
        grid.add_row("Date:", d_disp)
        grid.add_row("Category:", cat)
        grid.add_row("Desc:", desc or "—")
        
        cards.append(
            Panel(
                grid,
                title=Text(f"{symbol}£{amount:,.2f}", style=style),
                title_align="right",
                border_style=style
            )
        )
    return Group(*cards)

def view_transactions_paginated():
    """Main controller for Option 2: Browse history with cards."""
    page = 1
    page_size = 5 # Reduced to 5 per page for better vertical fit on most terminals
    
    while True:
        os.system('clear')
        txs, total_count, total_pages = get_paginated_transactions(page, page_size)
        
        CONSOLE.print(Panel(
            f"[bold magenta]Transaction History[/bold magenta]", 
            subtitle=f"Page {page}/{total_pages} | {total_count} Total Items",
            border_style="magenta"
        ))

        if not txs:
            CONSOLE.print("[yellow]No transactions found.[/yellow]")
        else:
            CONSOLE.print(render_transaction_cards(txs))

        # Navigation Bar
        nav = []
        if page > 1: nav.append("[P]revious")
        if page < total_pages: nav.append("[N]ext")
        nav.append("[C]lose")
        
        CONSOLE.print("\n" + " | ".join(nav), style="bold yellow")
        choice = input("Navigate: ").upper().strip()

        if choice == 'C': return "History closed."
        elif choice == 'P' and page > 1: page -= 1
        elif choice == 'N' and page < total_pages: page += 1

def filter_by_category():
    """Option 3: Search for specific categories."""
    os.system('clear')
    CONSOLE.print(Panel("[bold magenta]Filter by Category[/bold magenta]", border_style="magenta"))
    query = input("Enter category name (partial match): ").strip()
    if not query: return "Cancelled."

    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, amount, category, description, date, type 
            FROM transactions WHERE category LIKE ? ORDER BY date DESC
        """, (f"%{query}%",))
        results = cursor.fetchall()

    if not results:
        show_temporary_view(f"Filter: {query}", Text("[yellow]No results.[/yellow]"))
    else:
        show_temporary_view(f"Filter: {query} ({len(results)} found)", render_transaction_cards(results))
    return f"Search for '{query}' finished."

def get_transaction_data(start_date, end_date):
    """Aggregates income and expenses by category for a specific date range."""
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT amount, category, type FROM transactions 
            WHERE date BETWEEN ? AND ?
        """, (start_date, end_date))
        rows = cursor.fetchall()
    
    summary = {}
    for amt, cat, typ in rows:
        cat = cat.strip()
        if cat not in summary:
            summary[cat] = {'expense': 0.0, 'income': 0.0}
        if typ == 'income':
            summary[cat]['income'] += amt
        else:
            summary[cat]['expense'] += amt
    return summary

def weekly_summary():
    """Calculates and displays a breakdown of the current week (Mon-Sun)."""
    now = datetime.datetime.now()
    # Calculate Monday of the current week
    start_dt = now - datetime.timedelta(days=now.weekday())
    end_dt = start_dt + datetime.timedelta(days=6)
    
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")
    
    data = get_transaction_data(start_str, end_str)
    
    if not data:
        show_temporary_view(f"Weekly Summary ({start_str} to {end_str})", Text("[yellow]No data found for this week.[/yellow]"))
        return

    table = Table(title=f"Weekly Breakdown: {start_dt.strftime('%d %b')} - {end_dt.strftime('%d %b')}", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Income", justify="right", style="green")
    table.add_column("Expense", justify="right", style="red")
    table.add_column("Net", justify="right")

    t_inc = t_exp = 0
    for cat, val in data.items():
        i, e = val['income'], val['expense']
        t_inc += i; t_exp += e
        net = i - e
        table.add_row(cat, f"£{i:,.2f}", f"£{e:,.2f}", Text(f"£{net:,.2f}", style="bold green" if net >= 0 else "bold red"))

    footer = Group(
        table,
        Text("\n" + "─" * 40, style="dim"),
        Text.from_markup(f"[bold green]Total Income:   £{t_inc:,.2f}[/bold green]"),
        Text.from_markup(f"[bold red]Total Expense:  £{t_exp:,.2f}[/bold red]"),
        Text.from_markup(f"[bold cyan]Weekly Net:     £{t_inc - t_exp:,.2f}[/bold cyan]")
    )
    show_temporary_view("Weekly Summary", footer)

def monthly_summary():
    """Calculates and displays a breakdown for the current month."""
    now = datetime.datetime.now()
    start_str = now.strftime("%Y-%m-01")
    # Get last day of month
    if now.month == 12:
        end_dt = now.replace(year=now.year + 1, month=1, day=1) - datetime.timedelta(days=1)
    else:
        end_dt = now.replace(month=now.month + 1, day=1) - datetime.timedelta(days=1)
    end_str = end_dt.strftime("%Y-%m-%d")

    data = get_transaction_data(start_str, end_str)
    
    if not data:
        show_temporary_view(f"Monthly: {now.strftime('%B %Y')}", Text("[yellow]No data found for this month.[/yellow]"))
        return

    table = Table(title=f"Monthly Breakdown: {now.strftime('%B %Y')}", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Income", justify="right", style="green")
    table.add_column("Expense", justify="right", style="red")
    table.add_column("Net", justify="right")

    t_inc = t_exp = 0
    for cat, val in data.items():
        i, e = val['income'], val['expense']
        t_inc += i; t_exp += e
        net = i - e
        table.add_row(cat, f"£{i:,.2f}", f"£{e:,.2f}", Text(f"£{net:,.2f}", style="bold green" if net >= 0 else "bold red"))

    footer = Group(
        table,
        Text("\n" + "═" * 40, style="dim"),
        Text.from_markup(f"[bold green]Total Income:   £{t_inc:,.2f}[/bold green]"),
        Text.from_markup(f"[bold red]Total Expense:  £{t_exp:,.2f}[/bold red]"),
        Text.from_markup(f"[bold cyan]Monthly Net:    £{t_inc - t_exp:,.2f}[/bold cyan]")
    )
    show_temporary_view("Monthly Summary", footer)

def delete_transaction():
    """Fetches the latest 50 transactions and allows deletion by ID."""
    # 1. Fetch latest 50 for selection context
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, amount, category, description, date, type 
            FROM transactions ORDER BY date DESC, id DESC LIMIT 50
        """)
        transactions = cursor.fetchall()
    
    if not transactions:
        return "[yellow]No transactions found to delete.[/yellow]"

    # 2. Render cards for visual confirmation
    os.system('clear')
    CONSOLE.print(Panel("[bold red]Delete Transaction[/bold red]", border_style="red"))
    CONSOLE.print(render_transaction_cards(transactions))
    
    # 3. Handle deletion
    while True:
        tid = input("\nEnter ID to delete (C to cancel): ").strip().upper()
        if tid == 'C':
            return "Deletion cancelled."
        
        try:
            tid_int = int(tid)
            break
        except ValueError:
            CONSOLE.print("[bold red]Invalid input. Please enter a numeric ID.[/bold red]")

    # 4. Perform Deletion
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (tid_int,))
        if cursor.rowcount > 0:
            return f"[bold green]Successfully deleted transaction ID {tid_int}.[/bold green]"
        else:
            return f"[bold red]ID {tid_int} not found in database.[/bold red]"

def set_savings_goal():
    """Option 8: Configures the target and current progress in settings.db."""
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold yellow]Set Savings Goal[/bold yellow]", border_style="yellow"))
    
    while True:
        try:
            target = float(input("Enter Goal Target Amount (£): "))
            current = float(input("Enter Already Saved Amount (£): "))
            if target <= 0 or current < 0:
                CONSOLE.print("[red]Target must be positive, and saved amount cannot be negative.[/red]")
                continue
            break
        except ValueError:
            CONSOLE.print("[red]Invalid input. Please enter numbers only.[/red]")
            
    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('goal_target', str(target)))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('current_saved', str(current)))
    
    return f"[green]Savings goal set: £{current:,.2f} / £{target:,.2f}[/green]"

def add_to_savings():
    """Option 9: Adds money to the goal and logs a transaction in expenses.db."""
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold green]Add to Savings[/bold green]", border_style="green"))
    
    goal_target, current_saved = get_savings_goal()
    if goal_target == 0:
        return "[red]Please set a savings goal first (Option 8).[/red]"
    
    CONSOLE.print(f"[cyan]Progress: £{current_saved:,.2f} of £{goal_target:,.2f}[/cyan]")
    
    while True:
        try:
            amount = float(input("\nAmount to add to savings (£): "))
            if amount <= 0:
                CONSOLE.print("[red]Amount must be positive.[/red]")
                continue
            break
        except ValueError:
            CONSOLE.print("[red]Invalid number.[/red]")

    new_total = current_saved + amount
    
    # 1. Update the savings progress in settings.db
    with sqlite3.connect(DATABASE_SETTINGS) as conn_s:
        conn_s.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('current_saved', str(new_total)))
    
    # 2. Record this as a transaction in expenses.db so your net balance is accurate
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DATABASE_EXPENSES) as conn_e:
        conn_e.execute("""
            INSERT INTO transactions (amount, category, description, date, type) 
            VALUES (?, ?, ?, ?, ?)
        """, (amount, 'Savings Transfer', 'Transfer to Savings Goal', today, 'expense'))
    
    return f"[bold green]Saved £{amount:,.2f}! New total: £{new_total:,.2f}[/bold green]"

def add_to_savings():
    """Option 9: Adds money to the goal and logs a transaction in expenses.db."""
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold green]Add to Savings[/bold green]", border_style="green"))
    
    # 1. Check if a goal actually exists
    goal_target, current_saved = get_savings_goal()
    if goal_target == 0:
        return "[red]Please set a savings goal first (Option 8).[/red]"
    
    CONSOLE.print(f"[cyan]Current Progress: £{current_saved:,.2f} / £{goal_target:,.2f}[/cyan]")
    
    while True:
        try:
            amount = float(input("\nAmount to add to savings (£): "))
            if amount <= 0:
                CONSOLE.print("[red]Amount must be positive.[/red]")
                continue
            break
        except ValueError:
            CONSOLE.print("[red]Invalid number.[/red]")

    new_total = current_saved + amount
    
    # 2. Update the savings progress in settings.db
    with sqlite3.connect(DATABASE_SETTINGS) as conn_s:
        conn_s.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('current_saved', str(new_total)))
    
    # 3. Record this as a transaction in expenses.db
    # This ensures your 'Net Balance' on the dashboard stays accurate!
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DATABASE_EXPENSES) as conn_e:
        conn_e.execute("""
            INSERT INTO transactions (amount, category, description, date, type) 
            VALUES (?, ?, ?, ?, ?)
        """, (amount, 'Savings Transfer', 'Transfer to Savings Goal', today, 'expense'))
    
    return f"[bold green]Saved £{amount:,.2f}! New total: £{new_total:,.2f}[/bold green]"

def get_savings_goal():
    """Fetches target and current saved amounts from settings.db."""
    with sqlite3.connect(DATABASE_SETTINGS) as conn:
        cursor = conn.cursor()
        goal_target = cursor.execute("SELECT value FROM settings WHERE key='goal_target'").fetchone()
        current_saved = cursor.execute("SELECT value FROM settings WHERE key='current_saved'").fetchone()
        
        target = float(goal_target[0]) if goal_target else 0.0
        current = float(current_saved[0]) if current_saved else 0.0
        return target, current
                                                    
# --- NEW: Monthly Wrap-up Logic ---

def perform_monthly_wrapup():
    """Archives the previous month's data to a Markdown file."""
    now = datetime.datetime.now()
    # Calculate target month (previous month)
    first_of_this_month = now.replace(day=1)
    target_date = first_of_this_month - datetime.timedelta(days=1)
    month_label = target_date.strftime("%B %Y")
    file_tag = target_date.strftime("%Y-%m")
    
    archive_path = os.path.join(ARCHIVE_DIR, f"Summary_{file_tag}.md")
    
    # Query logic for specific month
    start_date = target_date.replace(day=1).strftime("%Y-%m-%d")
    end_date = target_date.strftime("%Y-%m-%d")
    
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='income' AND date BETWEEN ? AND ?", (start_date, end_date))
        inc = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND date BETWEEN ? AND ?", (start_date, end_date))
        exp = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT date, category, description, amount, type FROM transactions WHERE date BETWEEN ? AND ? ORDER BY date ASC", (start_date, end_date))
        logs = cursor.fetchall()

    net = inc - exp
    
    # Create the Archive File
    with open(archive_path, "w") as f:
        f.write(f"# Budget Summary: {month_label}\n\n")
        f.write(f"| Metric | Value |\n| :--- | :--- |\n")
        f.write(f"| **Total Income** | £{inc:,.2f} |\n")
        f.write(f"| **Total Expenses** | £{exp:,.2f} |\n")
        f.write(f"| **Net Balance** | £{net:,.2f} |\n\n")
        f.write("## Transaction Log\n\n")
        f.write("| Date | Category | Description | Amount |\n| :--- | :--- | :--- | :--- |\n")
        for d, c, ds, am, tp in logs:
            prefix = "+" if tp == 'income' else "-"
            f.write(f"| {d} | {c} | {ds or '-'} | {prefix}£{am:,.2f} |\n")

    return f"[bold green]Monthly Wrap-up complete! Archived to: {archive_path}[/bold green]"

# --- Enhanced Summary Views ---

def get_financial_summary():
    """Returns totals using current month as default for dashboard."""
    now = datetime.datetime.now()
    month_prefix = now.strftime("%Y-%m")
    
    with sqlite3.connect(DATABASE_EXPENSES) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='income' AND date LIKE ?", (f"{month_prefix}%",))
        inc = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense' AND date LIKE ?", (f"{month_prefix}%",))
        exp = cursor.fetchone()[0] or 0.0
    
    return inc, exp, (inc - exp)

# --- RECURRING & EXTERNAL INTEGRATION ---

def send_desktop_notification(title, message):
    """Sends a native Arch Linux desktop notification."""
    try:
        subprocess.run(["notify-send", "-a", "Budget Buddy", title, message], check=False)
    except FileNotFoundError:
        pass # notify-send not installed

def check_and_apply_recurring_payments():
    """Automatically logs bills due today and alerts the user."""
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    ym_prefix = now.strftime("%Y-%m")
    
    # 1. Check if we already ran this today to avoid double-charging
    with sqlite3.connect(DATABASE_SETTINGS) as conn_s:
        last = conn_s.execute("SELECT value FROM meta WHERE key='last_check'").fetchone()
        if last and last[0] == today_str:
            return None
        conn_s.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_check', ?)", (today_str,))

    # 2. Find templates due today
    templates = get_recurring_templates()
    applied = []
    
    with sqlite3.connect(DATABASE_EXPENSES) as conn_e:
        for _, name, amt, cat, _, day in templates:
            if day == now.day:
                desc = f"Recurring payment: {name}"
                # Ensure it hasn't been paid yet this month
                count = conn_e.execute(
                    "SELECT COUNT(*) FROM transactions WHERE description=? AND date LIKE ?", 
                    (desc, f"{ym_prefix}%")
                ).fetchone()[0]
                
                if count == 0:
                    conn_e.execute(
                        "INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                        (amt, cat, desc, today_str, 'expense')
                    )
                    applied.append(f"{name} (£{amt:.2f})")

    if applied:
        msg = f"Paid: {', '.join(applied)}"
        send_desktop_notification("Recurring Payments Applied", msg)
        return f"[bold green]Auto-paid today: {', '.join(applied)}[/bold green]"
    return None

def fetch_google_calendar_events():
    """
    Optimized for Arch: Uses gcalcli to fetch upcoming bills.
    Note: Requires 'gcalcli' to be installed and configured.
    """
    # Example command to get events for the next 7 days containing 'Bill' or 'Pay'
    # We use subprocess to keep the main script light and responsive.
    try:
        # This is a template; you can customize the search string
        cmd = ["gcalcli", "agenda", "today", "tomorrow", "--tsv"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
    except FileNotFoundError:
        return "[yellow]gcalcli not found. Install from AUR to sync Google Calendar.[/yellow]"

# --- THE FINAL MAIN LOOP ---

def main():
    initialize_db()
    db_check_and_migrate()
    
    # Run auto-payments on startup
    startup_msg = check_and_apply_recurring_payments() or "Welcome back!"
    
    while True:
        choice = display_dashboard(message=startup_msg)
        startup_msg = "" # Clear message after first display
        
        if choice == '1': startup_msg = add_transaction()
        elif choice == '2': startup_msg = view_transactions_paginated()
        elif choice == '3': startup_msg = filter_by_category()
        elif choice == '4': weekly_summary()
        elif choice == '5': monthly_summary()
        elif choice == '6': upcoming_calendar()
        elif choice == '7': startup_msg = delete_transaction()
        elif choice == '8': startup_msg = set_savings_goal()
        elif choice == '9': startup_msg = add_to_savings()
        elif choice == '10': startup_msg = manage_recurring_templates()
        elif choice == '11': startup_msg = apply_recurring_template()
        elif choice == '12': break # Exit
        elif choice == '13': startup_msg = manage_categories_full()
        elif choice == '14': startup_msg = perform_monthly_wrapup() # THE NEW OPTION
        else: startup_msg = "[red]Invalid selection.[/red]"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        print(get_dashboard_line())
        sys.exit(0)
    else:
        try:
            main()
        finally:
            # Only runs when you close the interactive TUI
            with sqlite3.connect(DATABASE_SETTINGS) as conn:
                conn.execute("VACUUM")
            with sqlite3.connect(DATABASE_EXPENSES) as conn:
                conn.execute("VACUUM")
