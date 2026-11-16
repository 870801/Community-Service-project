# OmniStock — Inventory Management System

A beginner-friendly Flask website prototype for the approved B.Tech project.

## Features
- Dashboard with product, unit, order and low-stock counts
- Add products with unique SKUs
- Adjust stock and keep a movement history
- Create customer orders; stock is deducted automatically
- Low-stock alerts
- Basic ML anomaly detection using Scikit-learn Isolation Forest
- Category-wise inventory value report
- SQLite database created automatically

## Requirements
- Python 3.10 or newer
- VS Code
- Internet connection for the first installation of Python packages

## Run in VS Code (Windows PowerShell)

1. Extract the ZIP file.
2. Open VS Code.
3. Choose File → Open Folder and select `omnichannel_inventory_system`.
4. Open Terminal → New Terminal.
5. Create a virtual environment:

   `py -m venv venv`

6. Activate it:

   `.\venv\Scripts\Activate.ps1`

   If PowerShell blocks activation, run this once in that terminal:
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
   Then activate again.

7. Install packages:

   `python -m pip install -r requirements.txt`

8. Start the website:

   `python app.py`

9. Open this address in your browser:

   `http://127.0.0.1:5000`

## How to test
1. Open Inventory and add a product.
2. Use Adjust Stock to add or remove units. Use a negative number to reduce stock.
3. Open Orders and place an order. The system will deduct the ordered quantity.
4. Open Alerts to see products at or below their reorder level.
5. Open ML Detection to review unusual stock movements.
6. Open Reports to see category-wise stock value.

## Important project notes
- This is a local working prototype. It uses SQLite so it can run immediately without installing a database server.
- The ML page uses Isolation Forest when Scikit-learn is installed. With too few records it falls back to a simple large-change rule.
- The app does not yet connect to live Amazon/Flipkart APIs, AWS Lambda, Kafka, or a production PostgreSQL server. Those are integration phases for the expanded project.
- Demo data is inserted automatically only when the database is first created.
- To reset the demo database, stop the server and delete `inventory.db`. The app recreates it on the next start.
