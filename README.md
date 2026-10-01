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

- New inventory record (with live store and employee selections)
- New client
- New store (optionally attached to a client)
- New employee
- Create user accounts with server-side password hashing
- Edit usernames and profile details, with an optional password reset
- View saved clients, stores, employees, inventories, and user-account details
- Edit any existing client, store, employee, or inventory record from the saved-data view

User-account creation is deliberately excluded because the schema requires securely generated password hashes; this app never handles passwords.
# ross_inventory_database_display
