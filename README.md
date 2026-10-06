# Ross Inventory Entry

A Flask web app and JSON API for data entry into the `ross_inventories` MySQL/MariaDB database. Database credentials are read only from environment variables.

## Start it

From this folder, install Flask once, set the connection variables, then start the server:

```zsh
python3 -m pip install -r requirements.txt
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_DATABASE=ross_inventories
export MYSQL_USER=root
# export MYSQL_PASSWORD='your-password'
python3 app.py
```

Open http://localhost:8081 in your browser. Press `Control-C` in the terminal to stop it.

## Container deployment

The included `Dockerfile` builds the Flask app and its MySQL/MariaDB client. In Synology Container Manager, publish container port `8081` and set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, and `MYSQL_PASSWORD` as environment variables. Point DSM's reverse proxy at port `8081`.

## Included forms

- Schedule an inventory with its store, contacts, date, planned hours, system, and notes
- Complete a scheduled inventory with its counts, values, costs, actual hours, and other completion details
- New group (stored in the existing `client` database table)
- New store (optionally attached to a client)
- New employee
- Create user accounts with server-side password hashing
- Edit usernames and profile details, with an optional password reset
- Browse all inventories on a month-by-month calendar
- View saved clients, stores, employees, inventories, and user-account details
- Edit any existing client, store, employee, or inventory record from the saved-data view

User passwords are securely hashed before storage and are never displayed by the app.

## Database migration

Before using the Discount field, apply `migrations/001_add_inventory_discount.sql` once to the `ross_inventories` database. It adds a non-null integer `Discount` column with a default value of `0`, preserving all existing inventory rows.

Apply `migrations/002_add_inventory_variance_amount_and_controller.sql` once to add `ControllerName` and `VarianceDollarAmount` to inventory records.

Apply `migrations/003_add_inventory_total_value_item.sql` once to add the separate `TotalValueItem` amount to inventory records.

Apply `migrations/004_split_inventory_hours_worked.sql` once to rename existing `HoursWorked` values to `HoursWorkedActual` and add `HoursWorkedPlanned`.

Apply `migrations/007_rename_estimated_duration_and_add_start_time.sql` once to rename `HoursWorkedPlanned` to `EstimatedDuration` and add `EstimatedStartTime`.

Apply `migrations/005_add_inventory_sheet_counts_and_page_break.sql` once to add `CountsShowingOnSheets` and `PageBreak` to inventory records.

Apply `migrations/006_add_inventory_travel_time_and_email.sql` once to add `TravelTime` and `Email` to inventory records.
# ross_inventory_database_display
