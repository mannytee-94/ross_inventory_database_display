# Ross Inventory Entry

A dependency-free local web app for data entry into the `ross_inventories` MySQL database. It uses your installed `mysql` client, so no database password is stored in the app.

## Start it

From this folder, set the connection variables (adjust the user/password if necessary), then start the server:

```zsh
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_DATABASE=ross_inventories
export MYSQL_USER=root
# export MYSQL_PASSWORD='your-password'
python3 app.py
```

Open http://localhost:8080 in your browser. Press `Control-C` in the terminal to stop it.

## Included forms

- New inventory record (with live store and employee selections)
- New client
- New store (optionally attached to a client)
- New employee
- View saved clients, stores, employees, inventories, and user-account details
- Edit any existing client, store, employee, or inventory record from the saved-data view

User-account creation is deliberately excluded because the schema requires securely generated password hashes; this app never handles passwords.
# ross_inventory_database_display
