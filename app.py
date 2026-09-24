#!/usr/bin/env python3
"""Small local web app for entering Ross inventory data into MySQL."""
import json
import os
import subprocess
from datetime import date
from decimal import Decimal, InvalidOperation
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
PUBLIC = BASE / "public"
DB_NAME = os.getenv("MYSQL_DATABASE", "ross_inventories")


def mysql(sql, write=False):
    """Run a local mysql-client query. Credentials come only from environment."""
    env = os.environ.copy()
    if os.getenv("MYSQL_PASSWORD"):
        env["MYSQL_PWD"] = os.environ["MYSQL_PASSWORD"]
    command = ["mysql", "--batch", "--skip-column-names", "--raw", "--default-character-set=utf8mb4",
               "--protocol", "TCP", "--host", os.getenv("MYSQL_HOST", "127.0.0.1"), "--port", os.getenv("MYSQL_PORT", "3306"),
               "--user", os.getenv("MYSQL_USER", "root"), "--database", DB_NAME, "--execute", sql]
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "MySQL command failed")
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
    raw = data.get(name)
    if raw in (None, ""):
        if required_field:
            raise ValueError(f"{name} is required.")
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number.")


def money(data, name, required_field=False):
    raw = data.get(name)
    if raw in (None, ""):
        if required_field:
            raise ValueError(f"{name} is required.")
        return None
    try:
        return Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} must be a valid amount.")


def rows(sql, fields):
    output = mysql(sql)
    return [dict(zip(fields, line.split("\t"))) for line in output.splitlines() if line]


class App(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def send_json(self, code, payload):
        body = json.dumps(payload, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path).path
        if route.startswith("/api/edit/"):
            parts = route.split("/")
            if len(parts) != 5 or parts[3] not in {"client", "store", "employee", "inventory"}:
                return self.send_json(404, {"error": "Unknown record."})
            try:
                record_id = int(parts[4])
                queries = {
                    "client": ("SELECT ClientName, ContactName, Phone, Email, BillingAddress, Status FROM client WHERE ClientId = ", ["clientName", "contactName", "phone", "email", "billingAddress", "status"]),
                    "store": ("SELECT ClientId, StoreName, Address, City, State, Zip FROM store WHERE StoreId = ", ["clientId", "storeName", "address", "city", "state", "zip"]),
                    "employee": ("SELECT FirstName, LastName, Email, Phone FROM employee WHERE EmployeeId = ", ["firstName", "lastName", "email", "phone"]),
                    "inventory": ("SELECT StoreId, PartsManager, InventoryDate, PieceCount, TotalValue, VarianceCount, WriteInCount, InventoryCost, InventoryLeadId, HoursWorked, CrewSize, Status, Notes, Type, ComputerSystem FROM inventory WHERE InventoryId = ", ["storeId", "partsManager", "inventoryDate", "pieceCount", "totalValue", "varianceCount", "writeInCount", "inventoryCost", "inventoryLeadId", "hoursWorked", "crewSize", "status", "notes", "type", "computerSystem"]),
                }
                sql, fields = queries[parts[3]]
                result = rows(sql + str(record_id), fields)
                if not result:
                    return self.send_json(404, {"error": "Record not found."})
                return self.send_json(200, result[0])
            except ValueError as error:
                return self.send_json(400, {"error": str(error)})
        if route not in {"/api/options", "/api/records"}:
            return super().do_GET()
        try:
            if route == "/api/records":
                # PasswordHash is intentionally never selected or sent to the browser.
                return self.send_json(200, {
                    "clients": rows("SELECT ClientId, ClientName, ContactName, Phone, Email, BillingAddress, Status FROM client ORDER BY ClientName", ["ID", "Client", "Contact", "Phone", "Email", "Billing address", "Status"]),
                    "stores": rows("SELECT s.StoreId, s.StoreName, c.ClientName, s.Address, s.City, s.State, s.Zip FROM store s LEFT JOIN client c ON c.ClientId = s.ClientId ORDER BY s.StoreName", ["ID", "Store", "Client", "Address", "City", "State", "ZIP"]),
                    "employees": rows("SELECT EmployeeId, FirstName, LastName, Email, Phone, IF(Active = b'1', 'Yes', 'No') FROM employee ORDER BY LastName, FirstName", ["ID", "First name", "Last name", "Email", "Phone", "Active"]),
                    "inventories": rows("SELECT i.InventoryId, s.StoreName, i.PartsManager, i.InventoryDate, i.PieceCount, i.TotalValue, i.VarianceCount, i.WriteInCount, i.InventoryCost, CONCAT(e.FirstName, ' ', e.LastName), i.HoursWorked, i.CrewSize, i.Status, i.Type, i.ComputerSystem, i.Notes FROM inventory i JOIN store s ON s.StoreId = i.StoreId LEFT JOIN employee e ON e.EmployeeId = i.InventoryLeadId ORDER BY i.InventoryDate DESC, i.InventoryId DESC", ["ID", "Store", "Parts manager", "Date", "Pieces", "Total value", "Variance", "Write-ins", "Cost", "Inventory lead", "Hours", "Crew", "Status", "Type", "System", "Notes"]),
                    "users": rows("SELECT UserId, Username, FirstName, LastName, Email, IF(Active = b'1', 'Yes', 'No') FROM user ORDER BY Username", ["ID", "Username", "First name", "Last name", "Email", "Active"]),
                })
            self.send_json(200, {
                "clients": rows("SELECT ClientId, ClientName FROM client WHERE Status = 'Active' ORDER BY ClientName", ["id", "name"]),
                "stores": rows("SELECT StoreId, StoreName, ClientId FROM store ORDER BY StoreName", ["id", "name", "clientId"]),
                "employees": rows("SELECT EmployeeId, CONCAT(FirstName, ' ', LastName) FROM employee WHERE Active = b'1' ORDER BY FirstName, LastName", ["id", "name"]),
            })
        except ValueError as error:
            self.send_json(500, {"error": str(error)})

    def do_POST(self):
        route = urlparse(self.path).path
        if route not in {"/api/client", "/api/store", "/api/employee", "/api/inventory"}:
            return self.send_json(404, {"error": "Unknown endpoint."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
            if route == "/api/client":
                mysql("INSERT INTO client (ClientName, ContactName, Phone, Email, BillingAddress, Status) VALUES (" + ", ".join(esc(data.get(x)) for x in ("clientName", "contactName", "phone", "email", "billingAddress", "status")) + ")", True)
            elif route == "/api/store":
                client_id = integer(data, "clientId")
                mysql("INSERT INTO store (ClientId, StoreName, Address, City, State, Zip) VALUES (" + ", ".join([str(client_id) if client_id else "NULL"] + [esc(data.get(x)) for x in ("storeName", "address", "city", "state", "zip")]) + ")", True)
            elif route == "/api/employee":
                mysql("INSERT INTO employee (FirstName, LastName, Email, Phone, Active) VALUES (" + ", ".join([esc(required(data, "firstName")), esc(required(data, "lastName")), esc(data.get("email")), esc(data.get("phone")), "b'1'"]) + ")", True)
            else:
                inventory_date = required(data, "inventoryDate")
                date.fromisoformat(inventory_date)
                values = [
                    integer(data, "storeId", True), esc(data.get("partsManager")), esc(inventory_date), integer(data, "pieceCount", True),
                    money(data, "totalValue"), integer(data, "varianceCount"), integer(data, "writeInCount"), money(data, "inventoryCost", True),
                    integer(data, "inventoryLeadId"), money(data, "hoursWorked"), integer(data, "crewSize"), esc(data.get("status") or "Completed"),
                    esc(data.get("notes")), esc(data.get("type") or "Inventory"), esc(data.get("computerSystem")),
                ]
                columns = "StoreId, PartsManager, InventoryDate, PieceCount, TotalValue, VarianceCount, WriteInCount, InventoryCost, InventoryLeadId, HoursWorked, CrewSize, Status, Notes, Type, ComputerSystem"
                mysql(f"INSERT INTO inventory ({columns}) VALUES (" + ", ".join(str(x) if x is not None else "NULL" for x in values) + ")", True)
            self.send_json(201, {"message": "Saved successfully."})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})

    def do_PUT(self):
        parts = urlparse(self.path).path.split("/")
        if len(parts) != 4 or parts[1] != "api" or parts[2] not in {"client", "store", "employee", "inventory"}:
            return self.send_json(404, {"error": "Unknown endpoint."})
        try:
            record_id = int(parts[3])
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
            if parts[2] == "client":
                assignments = [f"{column} = {esc(data.get(field))}" for column, field in (("ClientName", "clientName"), ("ContactName", "contactName"), ("Phone", "phone"), ("Email", "email"), ("BillingAddress", "billingAddress"), ("Status", "status"))]
                mysql("UPDATE client SET " + ", ".join(assignments) + f" WHERE ClientId = {record_id}", True)
            elif parts[2] == "store":
                client_id = integer(data, "clientId")
                assignments = [f"ClientId = {client_id if client_id else 'NULL'}"] + [f"{column} = {esc(data.get(field))}" for column, field in (("StoreName", "storeName"), ("Address", "address"), ("City", "city"), ("State", "state"), ("Zip", "zip"))]
                mysql("UPDATE store SET " + ", ".join(assignments) + f" WHERE StoreId = {record_id}", True)
            elif parts[2] == "employee":
                assignments = [f"{column} = {esc(required(data, field)) if field in ('firstName', 'lastName') else esc(data.get(field))}" for column, field in (("FirstName", "firstName"), ("LastName", "lastName"), ("Email", "email"), ("Phone", "phone"))]
                mysql("UPDATE employee SET " + ", ".join(assignments) + f" WHERE EmployeeId = {record_id}", True)
            else:
                inventory_date = required(data, "inventoryDate")
                date.fromisoformat(inventory_date)
                values = [integer(data, "storeId", True), esc(data.get("partsManager")), esc(inventory_date), integer(data, "pieceCount", True), money(data, "totalValue"), integer(data, "varianceCount"), integer(data, "writeInCount"), money(data, "inventoryCost", True), integer(data, "inventoryLeadId"), money(data, "hoursWorked"), integer(data, "crewSize"), esc(data.get("status") or "Completed"), esc(data.get("notes")), esc(data.get("type") or "Inventory"), esc(data.get("computerSystem"))]
                columns = "StoreId, PartsManager, InventoryDate, PieceCount, TotalValue, VarianceCount, WriteInCount, InventoryCost, InventoryLeadId, HoursWorked, CrewSize, Status, Notes, Type, ComputerSystem".split(", ")
                mysql("UPDATE inventory SET " + ", ".join(f"{column} = {str(value) if value is not None else 'NULL'}" for column, value in zip(columns, values)) + f" WHERE InventoryId = {record_id}", True)
            self.send_json(200, {"message": "Changes saved successfully."})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8081"))
    print(f"Ross Inventory Entry running at http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), App).serve_forever()
