# NEXUS – Commerce Intelligence

A local development starter for an online + physical retail analytics platform.

## Requirements
- Windows 10/11
- Python 3.13
- MongoDB Community Server running locally
- MongoDB Compass (optional visual database client)
- VS Code

## Setup (Windows PowerShell)
Open this folder in VS Code, then open Terminal > New Terminal.

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python scripts\check_connection.py
python scripts\init_db.py
python scripts\seed_demo_data.py
python app.py
```

If PowerShell blocks activation, run this once in the same terminal:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

Open http://127.0.0.1:5000

## Database
Database: `ecommerce_intelligence`

Collections: customers, products, orders, payments, inventory_movements,
customer_visits, suppliers, dataset_imports.

## Important data notes
- Demo records are tagged `source: synthetic_demo` and use INR.
- Never combine INR and GBP amounts in one total.
- The UCI Online Retail dataset is historical UK online-retail data. It does not contain physical-store entry/visit records, stock-on-hand, supplier data, or product cost. Those fields must not be invented for real records.
- Do not use the demo seeder as a real billing workflow. The later sales module will validate stock and write sale + inventory movement together.

## Project roadmap
1. Local environment and MongoDB collections
2. Professional dashboard
3. Customer and product management
4. Sales and billing
5. Inventory and supplier intelligence
6. Analytics and AI forecasting
