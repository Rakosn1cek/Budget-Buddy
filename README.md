# Budget Buddy TUI

Budget Buddy is a terminal based budgeting TUI tool optimised for Linux. It provides a comprehensive suite of features to track income, expenses and savings goals directly from your command line.

## Core Features

The application organises your finances through a clean and interactive dashboard. You can add transactions with specific categories and descriptions, and view your history using a paginated card layout. 
The tool distinguishes between income and expenses to provide a clear net balance for the current month.

Recurring payments are handled through a template system. You can define regular bills with their due days, and the application will automatically log these payments on the correct date or allow you to apply them manually.

The savings tracker helps you stay focused on your long term financial objectives. By setting a target and logging transfers to your savings, the dashboard provides a visual progress bar of your achievements.

## Reporting and Analysis

You can view granular breakdowns of your spending through weekly and monthly summaries. These reports categorise your transactions and calculate total income versus total expenditure. 
For future planning, the upcoming calendar view highlights scheduled transactions and large upcoming expenses.

The application also includes a monthly wrap up feature. At the end of each month, it archives your data into a formatted Markdown file for long term record keeping before resetting the ledger for the new period.

## Technical Details

Data is stored locally using SQLite databases located in `~/.local/share/budget-buddy` following XDG standards. 
The application uses WAL mode to ensure high performance on modern storage systems.

Integration with the broader Linux environment includes native desktop notifications for automated tasks and optional support for `gcalcli` to sync with Google Calendar.

## Getting Started
`git clone https://github.com/yourusername/Budget-Buddy.git  /path/to/Budget-Buddy`
`cd path/to/Budget-Buddy`
`chmod +x budget-buddy.py`

To run the application, ensure you have `Python 3` and the `rich` library installed. Execute the script directly to enter the interactive menu:

`python3 budget-buddy.py`

You can also retrieve a quick status line for use in terminal status bars by running:

`python3 budget-buddy.py --stats`

Create an Alias for easy call out.
alias bb="python3 /path/to/Budget-Buddy/budget-buddy.py"
