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
export FLASK_SECRET_KEY='replace-with-a-long-random-secret'
python3 app.py
```

Open http://localhost:8081 in your browser. Press `Control-C` in the terminal to stop it.

## Login protection

The app requires a username and password from the `user` table before showing inventory data. Password hashes are verified server-side and never sent to the browser. Set a persistent, random `FLASK_SECRET_KEY` before deployment so login sessions survive application restarts.

## Synology DS1825+ Container Manager setup

You need only **one new container**: this Flask app. Keep using the MariaDB package already installed on the Synology. Apache, Nginx, and a MariaDB container are not required.

1. Copy this entire `ross-inventory-entry` folder to a Synology shared folder, for example `/volume1/docker/ross-inventory-entry`.
2. In that folder, copy `.env.synology.example` to `.env.synology` and set the database password plus a long random `FLASK_SECRET_KEY`.
   - Set `MYSQL_HOST` to the Synology's LAN IP or DNS name, such as `192.168.1.50`. Do **not** use `127.0.0.1`: from inside the container, that address points back to the container itself.
   - Set `MYSQL_PORT` to the port configured for the installed MariaDB package. Confirm it in the package settings; common installations use `3306` or `3307`.
3. Create a MariaDB login for the app. Run the following once as a MariaDB administrator, replacing the password:

   ```sql
   CREATE USER 'ross_inventory_app'@'%' IDENTIFIED BY 'choose-a-long-database-password';
   GRANT SELECT, INSERT, UPDATE ON ross_inventories.* TO 'ross_inventory_app'@'%';
   FLUSH PRIVILEGES;
   ```

   This account has only the permissions the web app needs. Keep MariaDB's external network access disabled unless you specifically need it.
4. In DSM, open **Container Manager** → **Project** → **Create**. Choose the copied folder and select `docker-compose.yml`. Create/start the project. Container Manager builds the included `Dockerfile` and starts `ross-inventory-entry` automatically.
5. Open `http://<your-synology-ip>:8081` from your network, for example `http://192.168.1.50:8081`.

The project publishes only port `8081`. If you want HTTPS or a friendly name later, add a DSM reverse-proxy rule that forwards a hostname to `http://127.0.0.1:8081`.

### If the app cannot reach MariaDB

The MariaDB package must listen for TCP connections on the NAS LAN interface so the container can reach the `MYSQL_HOST` address. If the app reports a database connection error, verify the MariaDB port, its bind/listen setting, and any DSM firewall rule. Limit MariaDB access to the NAS itself and your trusted LAN; it does not need to be exposed to the internet.

### Optional SSH command

If you prefer SSH over the DSM interface, run this from the project folder after creating `.env.synology`:

```sh
docker compose up -d --build
```

### Database migrations

Apply the migration files supplied in `migrations/` once to the existing `ross_inventories` database before using the fields they add. Run migrations with a MariaDB administrator account; the restricted application account above intentionally cannot alter tables.

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

Apply `migrations/008_add_inventory_actual_times.sql` once to add `ActualStartTime` and `ActualEndTime` to inventory records.
# ross_inventory_database_display
