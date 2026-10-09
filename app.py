#!/usr/bin/env python3
"""Flask API and single-page frontend for Ross inventory data entry."""
import os
import re
import subprocess
from datetime import date, time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
PUBLIC = BASE / "public"
DB_NAME = os.getenv("MYSQL_DATABASE", "ross_inventories")
app = Flask(__name__, static_folder=str(PUBLIC), static_url_path="")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", os.urandom(32))
PHONE_PATTERN = re.compile(
    r"(?:\+?1[ .-]?)?(?:\([0-9]{3}\)|[0-9]{3})[ .-]?[0-9]{3}[ .-]?[0-9]{4}"
)
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def mysql(sql):
    """Run a MySQL/MariaDB client query using environment credentials."""
    env = os.environ.copy()
    if os.getenv("MYSQL_PASSWORD"):
        env["MYSQL_PWD"] = os.environ["MYSQL_PASSWORD"]
    command = [
        "mysql",
        "--batch",
        "--skip-column-names",
        "--raw",
        "--default-character-set=utf8mb4",
        "--protocol",
        "TCP",
        "--host",
        os.getenv("MYSQL_HOST", "127.0.0.1"),
        "--port",
        os.getenv("MYSQL_PORT", "3306"),
        "--user",
        os.getenv("MYSQL_USER", "root"),
        "--database",
        DB_NAME,
        "--execute",
        sql,
    ]
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


def phone(data, name="phone"):
    """Return an optional North American phone number in a commonly used format."""
    value = data.get(name)
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    if not PHONE_PATTERN.fullmatch(value):
        raise ValueError(
            "Phone must be a 10-digit number, such as 555-123-4567 or (555) 123-4567."
        )
    return value


def email_address(data, name="email"):
    """Return an optional email address after basic format validation."""
    value = data.get(name)
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    if not EMAIL_PATTERN.fullmatch(value):
        raise ValueError("Email must be a valid address, such as name@example.com.")
    return value


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


def inventory_status(data):
    value = data.get("status") or "Completed"
    if value not in {"Scheduled", "Completed"}:
        raise ValueError("Inventory status must be Scheduled or Completed.")
    return value


def estimated_start_time(data):
    """Validate and return an optional inventory start time."""
    value = data.get("estimatedStartTime")
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    try:
        time.fromisoformat(value)
    except ValueError:
        raise ValueError("Estimated start time must be a valid time.")
    return value


def rows(sql, fields):
    return [dict(zip(fields, line.split("\t"))) for line in mysql(sql).splitlines() if line]


def error(message, status=400):
    return jsonify(error=str(message)), status


@app.before_request
def require_login():
    """Require an authenticated session for every app and data route."""
    public_endpoints = {"login", "login_submit", "static"}
    if request.endpoint in public_endpoints or session.get("username"):
        return None
    if request.path.startswith("/api/"):
        return error("Please sign in to continue.", 401)
    return redirect(url_for("login"))


FIELDS = {
    "client": (
        ("ClientName", "clientName"),
        ("ContactName", "contactName"),
        ("Phone", "phone"),
        ("Email", "email"),
        ("BillingAddress", "billingAddress"),
        ("Status", "status"),
    ),
    "store": (
        ("ClientId", "clientId"),
        ("StoreName", "storeName"),
        ("Address", "address"),
        ("City", "city"),
        ("State", "state"),
        ("Zip", "zip"),
    ),
    "employee": (
        ("FirstName", "firstName"),
        ("LastName", "lastName"),
        ("Email", "email"),
        ("Phone", "phone"),
    ),
    "inventory": tuple(
        zip(
            "StoreId,PartsManager,ControllerName,EstimatedStartTime,InventoryDate,PieceCount,TotalValue,TotalValueItem,VarianceCount,VarianceDollarAmount,WriteInCount,Discount,InventoryCost,InventoryLeadId,HoursWorkedActual,EstimatedDuration,CrewSize,Status,Notes,Type,ComputerSystem,CountsShowingOnSheets,PageBreak,TravelTime,Email".split(
                ","
            ),
            "storeId,partsManager,controllerName,estimatedStartTime,inventoryDate,pieceCount,totalValue,totalValueItem,varianceCount,varianceDollarAmount,writeInCount,discount,inventoryCost,inventoryLeadId,hoursWorkedActual,estimatedDuration,crewSize,status,notes,type,computerSystem,countsShowingOnSheets,pageBreak,travelTime,email".split(
                ","
            ),
        )
    ),
}
PRIMARY_KEYS = {
    "client": "ClientId",
    "store": "StoreId",
    "employee": "EmployeeId",
    "inventory": "InventoryId",
}


def values_for(record_type, data):
    if record_type == "client":
        return [
            esc(required(data, "clientName")),
            esc(data.get("contactName")),
            esc(phone(data)),
            esc(email_address(data)),
            esc(data.get("billingAddress")),
            esc(data.get("status")),
        ]
    if record_type == "store":
        return [integer(data, "clientId")] + [
            esc(data.get(field)) for _, field in FIELDS[record_type][1:]
        ]
    if record_type == "employee":
        return [
            esc(required(data, "firstName")),
            esc(required(data, "lastName")),
            esc(email_address(data)),
            esc(phone(data)),
        ]
    if record_type == "inventory":
        inventory_date = required(data, "inventoryDate")
        date.fromisoformat(inventory_date)
        return [
            integer(data, "storeId", True),
            esc(data.get("partsManager")),
            esc(data.get("controllerName")),
            esc(estimated_start_time(data)),
            esc(inventory_date),
            integer(data, "pieceCount", True),
            money(data, "totalValue"),
            money(data, "totalValueItem"),
            integer(data, "varianceCount"),
            money(data, "varianceDollarAmount"),
            integer(data, "writeInCount"),
            integer(data, "discount") or 0,
            money(data, "inventoryCost", True),
            integer(data, "inventoryLeadId"),
            money(data, "hoursWorkedActual"),
            money(data, "estimatedDuration"),
            integer(data, "crewSize"),
            esc(inventory_status(data)),
            esc(data.get("notes")),
            esc(data.get("type") or "Inventory"),
            esc(data.get("computerSystem")),
            yes_no(data, "countsShowingOnSheets"),
            integer(data, "pageBreak"),
            money(data, "travelTime"),
            esc(email_address(data)),
        ]
    raise ValueError("Unknown endpoint.")


def save(record_type, data, record_id=None):
    if record_type not in FIELDS:
        raise ValueError("Unknown endpoint.")
    fields, values = FIELDS[record_type], values_for(record_type, data)
    sql_values = [str(value) if value is not None else "NULL" for value in values]
    if record_id is None:
        mysql(
            f"INSERT INTO {record_type} ("
            + ", ".join(column for column, _ in fields)
            + ") VALUES ("
            + ", ".join(sql_values)
            + ")"
        )
    else:
        mysql(
            f"UPDATE {record_type} SET "
            + ", ".join(f"{column} = {value}" for (column, _), value in zip(fields, sql_values))
            + f" WHERE {PRIMARY_KEYS[record_type]} = {record_id}"
        )


SCHEDULE_FIELDS = (
    ("StoreId", "storeId"),
    ("PartsManager", "partsManager"),
    ("ControllerName", "controllerName"),
    ("Email", "email"),
    ("EstimatedStartTime", "estimatedStartTime"),
    ("InventoryDate", "inventoryDate"),
    ("EstimatedDuration", "estimatedDuration"),
    ("ComputerSystem", "computerSystem"),
    ("Notes", "notes"),
    ("Status", "status"),
)


def schedule_values(data):
    inventory_date = required(data, "inventoryDate")
    date.fromisoformat(inventory_date)
    return [
        integer(data, "storeId", True),
        esc(data.get("partsManager")),
        esc(data.get("controllerName")),
        esc(email_address(data)),
        esc(estimated_start_time(data)),
        esc(inventory_date),
        money(data, "estimatedDuration"),
        esc(data.get("computerSystem")),
        esc(data.get("notes")),
        esc("Scheduled"),
    ]


def complete_assignments(data):
    fields = (
        ("PieceCount", integer(data, "pieceCount", True)),
        ("TotalValue", money(data, "totalValue")),
        ("TotalValueItem", money(data, "totalValueItem")),
        ("VarianceCount", integer(data, "varianceCount")),
        ("VarianceDollarAmount", money(data, "varianceDollarAmount")),
        ("WriteInCount", integer(data, "writeInCount")),
        ("Discount", integer(data, "discount") or 0),
        ("InventoryCost", money(data, "inventoryCost", True)),
        ("InventoryLeadId", integer(data, "inventoryLeadId")),
        ("HoursWorkedActual", money(data, "hoursWorkedActual")),
        ("CrewSize", integer(data, "crewSize")),
        ("Type", esc(data.get("type") or "Inventory")),
        ("CountsShowingOnSheets", yes_no(data, "countsShowingOnSheets")),
        ("PageBreak", integer(data, "pageBreak")),
        ("TravelTime", money(data, "travelTime")),
        ("Notes", esc(data.get("notes"))),
        ("Status", esc("Completed")),
    )
    return ", ".join(
        f"{column} = {str(value) if value is not None else 'NULL'}" for column, value in fields
    )


@app.get("/")
def index():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/login")
def login():
    if session.get("username"):
        return redirect(url_for("index"))
    return send_from_directory(PUBLIC, "login.html")


@app.post("/api/login")
def login_submit():
    try:
        data = request.get_json(silent=True) or {}
        username = required(data, "username")
        password = required(data, "password")
        user = rows(
            "SELECT Username, PasswordHash FROM `user` WHERE Username = "
            + esc(username)
            + " AND Active = b'1'",
            ["username", "passwordHash"],
        )
        if not user or not check_password_hash(user[0]["passwordHash"], password):
            return error("Invalid username or password.", 401)
        session.clear()
        session["username"] = user[0]["username"]
        return jsonify(message="Signed in successfully.")
    except ValueError as exc:
        return error(exc)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(message="Signed out successfully.")


@app.get("/api/options")
def options():
    try:
        return jsonify(
            clients=rows(
                "SELECT ClientId, ClientName FROM client WHERE Status = 'Active' ORDER BY ClientName",
                ["id", "name"],
            ),
            stores=rows(
                "SELECT StoreId, StoreName, ClientId FROM store ORDER BY StoreName",
                ["id", "name", "clientId"],
            ),
            employees=rows(
                "SELECT EmployeeId, CONCAT(FirstName, ' ', LastName) FROM employee WHERE Active = b'1' ORDER BY FirstName, LastName",
                ["id", "name"],
            ),
        )
    except ValueError as exc:
        return error(exc, 500)


@app.get("/api/scheduled-inventories")
def scheduled_inventories():
    try:
        return jsonify(
            rows(
                "SELECT i.InventoryId, CONCAT(s.StoreName, ' — ', DATE_FORMAT(i.InventoryDate, '%Y-%m-%d')) FROM inventory i JOIN store s ON s.StoreId = i.StoreId WHERE i.Status = 'Scheduled' ORDER BY i.InventoryDate, s.StoreName",
                ["id", "name"],
            )
        )
    except ValueError as exc:
        return error(exc, 500)


@app.post("/api/schedule-inventory")
def schedule_inventory():
    try:
        values = schedule_values(request.get_json(silent=True) or {})
        mysql(
            "INSERT INTO inventory ("
            + ", ".join(column for column, _ in SCHEDULE_FIELDS)
            + ") VALUES ("
            + ", ".join(str(value) if value is not None else "NULL" for value in values)
            + ")"
        )
        return jsonify(message="Inventory scheduled successfully."), 201
    except ValueError as exc:
        return error(exc)


@app.put("/api/schedule-inventory/<int:inventory_id>")
def update_scheduled_inventory(inventory_id):
    """Update the calendar fields for an inventory that is still scheduled."""
    try:
        data = request.get_json(silent=True) or {}
        inventory_date = required(data, "inventoryDate")
        date.fromisoformat(inventory_date)
        start_time = estimated_start_time(data)
        duration = money(data, "estimatedDuration")
        existing = rows(
            f"SELECT Status FROM inventory WHERE InventoryId = {inventory_id}", ["status"]
        )
        if not existing:
            return error("Scheduled inventory not found.", 404)
        if existing[0]["status"] != "Scheduled":
            return error("Only scheduled inventories can be changed from the calendar.")
        mysql(
            "UPDATE inventory SET "
            + f"InventoryDate = {esc(inventory_date)}, "
            + f"EstimatedStartTime = {esc(start_time)}, "
            + f"EstimatedDuration = {str(duration) if duration is not None else 'NULL'} "
            + f"WHERE InventoryId = {inventory_id}"
        )
        return jsonify(message="Scheduled inventory updated successfully.")
    except ValueError as exc:
        return error(exc)


@app.put("/api/complete-inventory/<int:inventory_id>")
def complete_inventory(inventory_id):
    try:
        mysql(
            f"UPDATE inventory SET {complete_assignments(request.get_json(silent=True) or {})} WHERE InventoryId = {inventory_id}"
        )
        return jsonify(message="Inventory completed successfully.")
    except ValueError as exc:
        return error(exc)


@app.get("/api/records")
def records():
    try:
        return jsonify(
            clients=rows(
                "SELECT ClientId, ClientName, ContactName, Phone, Email, BillingAddress, Status FROM client ORDER BY ClientName",
                ["ID", "Group", "Contact", "Phone", "Email", "Billing address", "Status"],
            ),
            stores=rows(
                "SELECT s.StoreId, s.StoreName, c.ClientName, s.Address, s.City, s.State, s.Zip FROM store s LEFT JOIN client c ON c.ClientId = s.ClientId ORDER BY s.StoreName",
                ["ID", "Store", "Group", "Address", "City", "State", "ZIP"],
            ),
            employees=rows(
                "SELECT EmployeeId, FirstName, LastName, Email, Phone, IF(Active = b'1', 'Yes', 'No') FROM employee ORDER BY LastName, FirstName",
                ["ID", "First name", "Last name", "Email", "Phone", "Active"],
            ),
            inventories=rows(
                "SELECT i.InventoryId, s.StoreName, i.PartsManager, i.ControllerName, i.InventoryDate, i.EstimatedStartTime, i.PieceCount, i.TotalValue, i.TotalValueItem, i.VarianceCount, i.VarianceDollarAmount, i.WriteInCount, i.Discount, i.InventoryCost, CONCAT(e.FirstName, ' ', e.LastName), i.HoursWorkedActual, i.EstimatedDuration, i.CrewSize, i.Status, i.Type, i.ComputerSystem, i.Notes, IF(i.CountsShowingOnSheets = 1, 'Yes', 'No'), i.PageBreak, i.TravelTime, i.Email FROM inventory i JOIN store s ON s.StoreId = i.StoreId LEFT JOIN employee e ON e.EmployeeId = i.InventoryLeadId ORDER BY i.InventoryDate DESC, i.InventoryId DESC",
                [
                    "ID",
                    "Store",
                    "Parts manager",
                    "Controller name",
                    "Date",
                    "Estimated start time",
                    "Part number count",
                    "Total value (parts)",
                    "Total value",
                    "Variance count",
                    "Variance dollar amount",
                    "Write-ins",
                    "Discount",
                    "Cost",
                    "Inventory lead",
                    "Hours worked actual",
                    "Estimated duration",
                    "Crew",
                    "Status",
                    "Type",
                    "System",
                    "Notes",
                    "Counts showing on sheets",
                    "Page break",
                    "Travel time",
                    "Email",
                ],
            ),
            users=rows(
                "SELECT UserId, Username, FirstName, LastName, Email, IF(Active = b'1', 'Yes', 'No') FROM user ORDER BY Username",
                ["ID", "Username", "First name", "Last name", "Email", "Active"],
            ),
        )
    except ValueError as exc:
        return error(exc, 500)


@app.get("/api/calendar")
def calendar_events():
    """Return compact inventory events for the calendar page."""
    try:
        return jsonify(
            rows(
                "SELECT i.InventoryId, i.InventoryDate, s.StoreName, i.Status, i.EstimatedStartTime, i.EstimatedDuration, i.PieceCount, i.TotalValue, i.Discount, COALESCE(CONCAT(e.FirstName, ' ', e.LastName), '') FROM inventory i JOIN store s ON s.StoreId = i.StoreId LEFT JOIN employee e ON e.EmployeeId = i.InventoryLeadId ORDER BY i.InventoryDate, i.EstimatedStartTime, s.StoreName",
                ["id", "date", "store", "status", "estimatedStartTime", "estimatedDuration", "pieceCount", "totalValue", "discount", "lead"],
            )
        )
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
        data = rows(
            f"SELECT YEAR(InventoryDate), MONTH(InventoryDate), SUM(COALESCE({column}, 0)) FROM inventory WHERE StoreId = {store_id} GROUP BY YEAR(InventoryDate), MONTH(InventoryDate) ORDER BY YEAR(InventoryDate), MONTH(InventoryDate)",
            ["year", "month", "value"],
        )
        return jsonify(metric=metric_key, label=label, data=data)
    except (TypeError, ValueError) as exc:
        return error(exc)


@app.get("/api/edit/<record_type>/<int:record_id>")
def edit_data(record_type, record_id):
    if record_type == "user":
        try:
            result = rows(
                "SELECT u.Username, u.FirstName, u.LastName, u.Email, COALESCE(e.Phone, '') "
                "FROM `user` u LEFT JOIN employee e ON e.UserId = u.UserId "
                f"WHERE u.UserId = {record_id}",
                ["username", "firstName", "lastName", "email", "phone"],
            )
            return jsonify(result[0]) if result else error("Record not found.", 404)
        except ValueError as exc:
            return error(exc)
    if record_type not in FIELDS:
        return error("Unknown record.", 404)
    try:
        columns, form_fields = zip(*FIELDS[record_type])
        result = rows(
            f"SELECT {', '.join(columns)} FROM {record_type} WHERE {PRIMARY_KEYS[record_type]} = {record_id}",
            form_fields,
        )
        return jsonify(result[0]) if result else error("Record not found.", 404)
    except ValueError as exc:
        return error(exc)


@app.post("/api/user")
def create_user():
    """Create a login account and its required linked employee record."""
    try:
        data = request.get_json(silent=True) or {}
        username = required(data, "username")
        first_name = required(data, "firstName")
        last_name = required(data, "lastName")
        email = email_address(data)
        phone_number = phone(data)
        password = required(data, "password")
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters.")
        if password != data.get("confirmPassword"):
            raise ValueError("Passwords do not match.")
        user_values = ", ".join(
            [
                esc(username),
                esc(generate_password_hash(password)),
                esc(first_name),
                esc(last_name),
                esc(email),
                "b'1'",
            ]
        )
        employee_values = ", ".join(
            [
                "LAST_INSERT_ID()",
                esc(first_name),
                esc(last_name),
                esc(email),
                esc(phone_number),
                "b'1'",
            ]
        )
        mysql(
            "START TRANSACTION; "
            "INSERT INTO `user` (Username, PasswordHash, FirstName, LastName, Email, Active) VALUES ("
            + user_values
            + "); "
            "INSERT INTO employee (UserId, FirstName, LastName, Email, Phone, Active) VALUES ("
            + employee_values
            + "); COMMIT"
        )
        return jsonify(message="User and linked employee created successfully."), 201
    except ValueError as exc:
        return error(exc)


@app.put("/api/user/<int:user_id>")
def update_user(user_id):
    """Update a login account and keep its linked employee profile in sync."""
    try:
        data = request.get_json(silent=True) or {}
        first_name = required(data, "firstName")
        last_name = required(data, "lastName")
        email = email_address(data)
        phone_number = phone(data)
        assignments = [
            f"Username = {esc(required(data, 'username'))}",
            f"FirstName = {esc(first_name)}",
            f"LastName = {esc(last_name)}",
            f"Email = {esc(email)}",
        ]
        password = data.get("password") or ""
        confirmation = data.get("confirmPassword") or ""
        if password or confirmation:
            if len(password) < 12:
                raise ValueError("Password must be at least 12 characters.")
            if password != confirmation:
                raise ValueError("Passwords do not match.")
            assignments.append(f"PasswordHash = {esc(generate_password_hash(password))}")
        mysql(
            "START TRANSACTION; UPDATE `user` SET "
            + ", ".join(assignments)
            + f" WHERE UserId = {user_id}; "
            + "UPDATE employee SET "
            + f"FirstName = {esc(first_name)}, LastName = {esc(last_name)}, Email = {esc(email)}, Phone = {esc(phone_number)} "
            + f"WHERE UserId = {user_id}; "
            + "INSERT INTO employee (UserId, FirstName, LastName, Email, Phone, Active) "
            + f"SELECT {user_id}, {esc(first_name)}, {esc(last_name)}, {esc(email)}, {esc(phone_number)}, b'1' "
            + f"WHERE NOT EXISTS (SELECT 1 FROM employee WHERE UserId = {user_id}); COMMIT"
        )
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
