#!/usr/bin/env python3
"""Flask API and single-page frontend for Ross inventory data entry."""
import os
import subprocess
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import generate_password_hash

BASE = Path(__file__).resolve().parent
PUBLIC = BASE / "public"
DB_NAME = os.getenv("MYSQL_DATABASE", "ross_inventories")
app = Flask(__name__, static_folder=str(PUBLIC), static_url_path="")


def mysql(sql):
    """Run a MySQL/MariaDB client query using environment credentials."""
    env = os.environ.copy()
    if os.getenv("MYSQL_PASSWORD"):
        env["MYSQL_PWD"] = os.environ["MYSQL_PASSWORD"]
    command = ["mysql", "--batch", "--skip-column-names", "--raw", "--default-character-set=utf8mb4", "--protocol", "TCP", "--host", os.getenv("MYSQL_HOST", "127.0.0.1"), "--port", os.getenv("MYSQL_PORT", "3306"), "--user", os.getenv("MYSQL_USER", "root"), "--database", DB_NAME, "--execute", sql]
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Database command failed")
    return result.stdout


def esc(value):
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\x00", "") + "'"


def required(data, name):
    value = data.get(name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"{name} is required.")
    return str(value).strip()


def integer(data, name, required_field=False):
    value = data.get(name)
    if value in (None, ""):
        if required_field:
            raise ValueError(f"{name} is required.")
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number.")


def money(data, name, required_field=False):
    value = data.get(name)
    if value in (None, ""):
        if required_field:
            raise ValueError(f"{name} is required.")
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} must be a valid amount.")


def yes_no(data, name):
    value = str(data.get(name, "0")).lower()
    if value in {"1", "yes", "true", "on"}:
        return 1
    if value in {"0", "no", "false", "off", ""}:
        return 0
    raise ValueError(f"{name} must be Yes or No.")


def rows(sql, fields):
    return [dict(zip(fields, line.split("\t"))) for line in mysql(sql).splitlines() if line]


def error(message, status=400):
    return jsonify(error=str(message)), status


FIELDS = {
    "client": (("ClientName", "clientName"), ("ContactName", "contactName"), ("Phone", "phone"), ("Email", "email"), ("BillingAddress", "billingAddress"), ("Status", "status")),
    "store": (("ClientId", "clientId"), ("StoreName", "storeName"), ("Address", "address"), ("City", "city"), ("State", "state"), ("Zip", "zip")),
    "employee": (("FirstName", "firstName"), ("LastName", "lastName"), ("Email", "email"), ("Phone", "phone")),
    "inventory": tuple(zip("StoreId,PartsManager,ControllerName,InventoryDate,PieceCount,TotalValue,TotalValueItem,VarianceCount,VarianceDollarAmount,WriteInCount,Discount,InventoryCost,InventoryLeadId,HoursWorkedActual,HoursWorkedPlanned,CrewSize,Status,Notes,Type,ComputerSystem,CountsShowingOnSheets,PageBreak,TravelTime,Email".split(","), "storeId,partsManager,controllerName,inventoryDate,pieceCount,totalValue,totalValueItem,varianceCount,varianceDollarAmount,writeInCount,discount,inventoryCost,inventoryLeadId,hoursWorkedActual,hoursWorkedPlanned,crewSize,status,notes,type,computerSystem,countsShowingOnSheets,pageBreak,travelTime,email".split(","))),
}
PRIMARY_KEYS = {"client": "ClientId", "store": "StoreId", "employee": "EmployeeId", "inventory": "InventoryId"}


def values_for(record_type, data):
    if record_type == "client":
        return [esc(required(data, "clientName"))] + [esc(data.get(field)) for _, field in FIELDS[record_type][1:]]
    if record_type == "store":
        return [integer(data, "clientId")] + [esc(data.get(field)) for _, field in FIELDS[record_type][1:]]
    if record_type == "employee":
        return [esc(required(data, "firstName")), esc(required(data, "lastName")), esc(data.get("email")), esc(data.get("phone"))]
    if record_type == "inventory":
        inventory_date = required(data, "inventoryDate")
        date.fromisoformat(inventory_date)
        return [integer(data, "storeId", True), esc(data.get("partsManager")), esc(data.get("controllerName")), esc(inventory_date), integer(data, "pieceCount", True), money(data, "totalValue"), money(data, "totalValueItem"), integer(data, "varianceCount"), money(data, "varianceDollarAmount"), integer(data, "writeInCount"), integer(data, "discount") or 0, money(data, "inventoryCost", True), integer(data, "inventoryLeadId"), money(data, "hoursWorkedActual"), money(data, "hoursWorkedPlanned"), integer(data, "crewSize"), esc(data.get("status") or "Completed"), esc(data.get("notes")), esc(data.get("type") or "Inventory"), esc(data.get("computerSystem")), yes_no(data, "countsShowingOnSheets"), integer(data, "pageBreak"), money(data, "travelTime"), esc(data.get("email"))]
    raise ValueError("Unknown endpoint.")


def save(record_type, data, record_id=None):
    if record_type not in FIELDS:
        raise ValueError("Unknown endpoint.")
    fields, values = FIELDS[record_type], values_for(record_type, data)
    sql_values = [str(value) if value is not None else "NULL" for value in values]
    if record_id is None:
        mysql(f"INSERT INTO {record_type} (" + ", ".join(column for column, _ in fields) + ") VALUES (" + ", ".join(sql_values) + ")")
    else:
        mysql(f"UPDATE {record_type} SET " + ", ".join(f"{column} = {value}" for (column, _), value in zip(fields, sql_values)) + f" WHERE {PRIMARY_KEYS[record_type]} = {record_id}")


@app.get("/")
def index():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/api/options")
def options():
    try:
        return jsonify(clients=rows("SELECT ClientId, ClientName FROM client WHERE Status = 'Active' ORDER BY ClientName", ["id", "name"]), stores=rows("SELECT StoreId, StoreName, ClientId FROM store ORDER BY StoreName", ["id", "name", "clientId"]), employees=rows("SELECT EmployeeId, CONCAT(FirstName, ' ', LastName) FROM employee WHERE Active = b'1' ORDER BY FirstName, LastName", ["id", "name"]))
    except ValueError as exc:
        return error(exc, 500)


@app.get("/api/records")
def records():
    try:
        return jsonify(
            clients=rows("SELECT ClientId, ClientName, ContactName, Phone, Email, BillingAddress, Status FROM client ORDER BY ClientName", ["ID", "Group", "Contact", "Phone", "Email", "Billing address", "Status"]),
            stores=rows("SELECT s.StoreId, s.StoreName, c.ClientName, s.Address, s.City, s.State, s.Zip FROM store s LEFT JOIN client c ON c.ClientId = s.ClientId ORDER BY s.StoreName", ["ID", "Store", "Group", "Address", "City", "State", "ZIP"]),
            employees=rows("SELECT EmployeeId, FirstName, LastName, Email, Phone, IF(Active = b'1', 'Yes', 'No') FROM employee ORDER BY LastName, FirstName", ["ID", "First name", "Last name", "Email", "Phone", "Active"]),
            inventories=rows("SELECT i.InventoryId, s.StoreName, i.PartsManager, i.ControllerName, i.InventoryDate, i.PieceCount, i.TotalValue, i.TotalValueItem, i.VarianceCount, i.VarianceDollarAmount, i.WriteInCount, i.Discount, i.InventoryCost, CONCAT(e.FirstName, ' ', e.LastName), i.HoursWorkedActual, i.HoursWorkedPlanned, i.CrewSize, i.Status, i.Type, i.ComputerSystem, i.Notes, IF(i.CountsShowingOnSheets = 1, 'Yes', 'No'), i.PageBreak, i.TravelTime, i.Email FROM inventory i JOIN store s ON s.StoreId = i.StoreId LEFT JOIN employee e ON e.EmployeeId = i.InventoryLeadId ORDER BY i.InventoryDate DESC, i.InventoryId DESC", ["ID", "Store", "Parts manager", "Controller name", "Date", "Part number count", "Total value (parts)", "Total value", "Variance count", "Variance dollar amount", "Write-ins", "Discount", "Cost", "Inventory lead", "Hours worked actual", "Hours worked planned", "Crew", "Status", "Type", "System", "Notes", "Counts showing on sheets", "Page break", "Travel time", "Email"]),
            users=rows("SELECT UserId, Username, FirstName, LastName, Email, IF(Active = b'1', 'Yes', 'No') FROM user ORDER BY Username", ["ID", "Username", "First name", "Last name", "Email", "Active"]))
    except ValueError as exc:
        return error(exc, 500)


@app.get("/api/calendar")
def calendar_events():
    """Return compact inventory events for the calendar page."""
    try:
        return jsonify(rows("SELECT i.InventoryId, i.InventoryDate, s.StoreName, i.Status, i.PieceCount, i.TotalValue, i.Discount, COALESCE(CONCAT(e.FirstName, ' ', e.LastName), '') FROM inventory i JOIN store s ON s.StoreId = i.StoreId LEFT JOIN employee e ON e.EmployeeId = i.InventoryLeadId ORDER BY i.InventoryDate, s.StoreName", ["id", "date", "store", "status", "pieceCount", "totalValue", "discount", "lead"]))
    except ValueError as exc:
        return error(exc, 500)


@app.get("/api/store-chart")
def store_chart():
    """Return monthly totals grouped by year for a selected store and metric."""
    metrics = {
        "totalValue": ("Total value", "TotalValue"),
        "pieceCount": ("Piece count", "PieceCount"),
        "inventoryCost": ("Inventory cost", "InventoryCost"),
        "varianceCount": ("Variance count", "VarianceCount"),
        "discount": ("Discount", "Discount"),
    }
    try:
        store_id = int(request.args.get("storeId", ""))
        metric_key = request.args.get("metric", "totalValue")
        if metric_key not in metrics:
            raise ValueError("Unknown chart metric.")
        label, column = metrics[metric_key]
        data = rows(f"SELECT YEAR(InventoryDate), MONTH(InventoryDate), SUM(COALESCE({column}, 0)) FROM inventory WHERE StoreId = {store_id} GROUP BY YEAR(InventoryDate), MONTH(InventoryDate) ORDER BY YEAR(InventoryDate), MONTH(InventoryDate)", ["year", "month", "value"])
        return jsonify(metric=metric_key, label=label, data=data)
    except (TypeError, ValueError) as exc:
        return error(exc)


@app.get("/api/edit/<record_type>/<int:record_id>")
def edit_data(record_type, record_id):
    if record_type == "user":
        try:
            result = rows(f"SELECT Username, FirstName, LastName, Email FROM `user` WHERE UserId = {record_id}", ["username", "firstName", "lastName", "email"])
            return jsonify(result[0]) if result else error("Record not found.", 404)
        except ValueError as exc:
            return error(exc)
    if record_type not in FIELDS:
        return error("Unknown record.", 404)
    try:
        columns, form_fields = zip(*FIELDS[record_type])
        result = rows(f"SELECT {', '.join(columns)} FROM {record_type} WHERE {PRIMARY_KEYS[record_type]} = {record_id}", form_fields)
        return jsonify(result[0]) if result else error("Record not found.", 404)
    except ValueError as exc:
        return error(exc)


@app.post("/api/user")
def create_user():
    """Create an application user without ever returning the password hash."""
    try:
        data = request.get_json(silent=True) or {}
        username = required(data, "username")
        password = required(data, "password")
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters.")
        if password != data.get("confirmPassword"):
            raise ValueError("Passwords do not match.")
        mysql("INSERT INTO `user` (Username, PasswordHash, FirstName, LastName, Email, Active) VALUES (" + ", ".join([esc(username), esc(generate_password_hash(password)), esc(data.get("firstName")), esc(data.get("lastName")), esc(data.get("email")), "b'1'"]) + ")")
        return jsonify(message="User created successfully."), 201
    except ValueError as exc:
        return error(exc)


@app.put("/api/user/<int:user_id>")
def update_user(user_id):
    """Update profile data and optionally replace the password hash."""
    try:
        data = request.get_json(silent=True) or {}
        assignments = [f"Username = {esc(required(data, 'username'))}", f"FirstName = {esc(data.get('firstName'))}", f"LastName = {esc(data.get('lastName'))}", f"Email = {esc(data.get('email'))}"]
        password = data.get("password") or ""
        confirmation = data.get("confirmPassword") or ""
        if password or confirmation:
            if len(password) < 12:
                raise ValueError("Password must be at least 12 characters.")
            if password != confirmation:
                raise ValueError("Passwords do not match.")
            assignments.append(f"PasswordHash = {esc(generate_password_hash(password))}")
        mysql("UPDATE `user` SET " + ", ".join(assignments) + f" WHERE UserId = {user_id}")
        return jsonify(message="User changes saved successfully.")
    except ValueError as exc:
        return error(exc)


@app.post("/api/<record_type>")
def create_record(record_type):
    try:
        save(record_type, request.get_json(silent=True) or {})
        return jsonify(message="Saved successfully."), 201
    except ValueError as exc:
        return error(exc)


@app.put("/api/<record_type>/<int:record_id>")
def update_record(record_type, record_id):
    try:
        save(record_type, request.get_json(silent=True) or {}, record_id)
        return jsonify(message="Changes saved successfully.")
    except ValueError as exc:
        return error(exc)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8081")))
