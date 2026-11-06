# Friendship Bracelets 💜

A custom bracelet ordering and management system for a handmade friendship bracelet business.

**Friendship Bracelets** allows customers to explore bracelet designs, choose custom colors, place orders, and pay through Telebirr or bank transfer. Customers submit payment receipts for verification, and bracelet production begins after the payment is approved.

The project aims to simplify order management, payment verification, and order preparation while providing a convenient experience for customers.

## ✨ Planned Features

- **Custom Orders:** Allow customers to select bracelet colors and personalize their orders.
- **Order Management:** Track orders, quantities, prices, deposits, and order statuses.
- **Payment Verification:** Customers upload payment receipts for admin review.
- **Deposit Payments:** Support deposits before bracelet production begins.
- **Admin Dashboard:** Manage products, orders, payments, and pickup locations.
- **Pickup Locations:** Allow customers to choose a pickup location. Delivery is not currently planned.
- **Future Telegram Integration:** Explore connecting the system with the business's Telegram channel.

## 🛠️ Tech Stack

- **Backend:** Python, Django
- **Package Management:** uv
- **Database:** MySQL
- **Frontend:** React

## 💳 Payment & Order Process

1. Customers select a bracelet and customize their order.
2. Customers choose a pickup location.
3. Customers pay the required deposit through Telebirr or bank transfer.
4. Customers upload their payment receipt.
5. The administrator reviews and verifies the payment.
6. Once the payment is approved, bracelet production begins.
7. The customer collects the completed order at the selected pickup location.

## 🗄️ Database Design

The planned database includes customers, products, categories, product images, colors, orders, order items, payments, and pickup locations.

The schema is designed to support product customization, order tracking, deposit management, and payment verification.

## Project Structure

```text
friendship-bracelets/
├── apps/
│   ├── catalog/
│   ├── orders/
│   ├── payments/
│   └── pickups/
├── bracelet_config/
├── manage.py
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
└── Readme.md
```

### Django apps

App Responsibility

---

`catalog` Products, categories, colors, and product images
`orders` Customers, orders, order items, and customization
`payments` Payment records and receipt verification
`pickups` Pickup locations and availability

---

## 🔌 API Endpoints

Interactive docs (Swagger): http://127.0.0.1:8000/api/docs/

Method Endpoint Description

---

`GET` `/api/categories/` List categories
`GET` `/api/colors/` List colors
`GET` `/api/products/` List products
`GET` `/api/products/<slug>/` Product details
`GET` `/api/pickup-locations/` List active pickup locations
`POST` `/api/orders/` Create an order (see below)

### Create an order: `POST /api/orders/`

A customer sends their info and cart. The server validates everything,
calculates the money, and saves the customer, order, items, and colors in
one transaction (if anything fails, nothing is saved).

**Request**

```json
{
  "customer": {
    "full_name": "Hana T",
    "phone": "0911000000",
    "email": "",
    "telegram_username": ""
  },
  "pickup_location": 1,
  "customer_note": "optional",
  "items": [
    {
      "product": 3,
      "quantity": 2,
      "color_mode": "custom",
      "colors": [5, 7, 2],
      "name_text": "HANA",
      "notes": ""
    }
  ]
}
```

- `colors` is a list of color ids. Their order becomes position 1, 2, 3...
- `color_mode` is `custom` or `as_in_picture`.

**Response: `201 Created`**

```json
{
  "order_number": "BR-7K2QX9AB",
  "status": "pending_payment",
  "total_amount": "301.00",
  "deposit_percent": 50,
  "deposit_amount": "150.50"
}
```

**Validation (returns `400` with field errors)**

- `pickup_location` must exist and be active.
- `items` must not be empty.
- Each item's `product` must exist and be active, and `quantity` must be at least 1.
- `color_mode: custom`: the product must allow custom colors, `colors` must not
  be empty, and every color must belong to that product and be available.
- `color_mode: as_in_picture`: `colors` must be empty.
- `name_text` is only allowed if the product allows names, and must not be
  longer than the product's `max_name_length`.
- `customer.full_name` and `customer.phone` are required.

**The server decides the money (the client's values are never trusted)**

- `unit_price` and `product_name` are copied from the product.
- `total_amount` is the sum of `unit_price * quantity`.
- `deposit_percent` is 50, and `deposit_amount` is half of the total, rounded to 2 decimals.
- `order_number` is unique, in the format `BR-` plus 8 random uppercase letters/digits.
- `status` starts as `pending_payment`.
- Customers are matched by phone number (spaces removed), so the same phone
  never creates a second customer.

## Getting Started

### 1. Check your installations

```bash
git --version
python3 --version
uv --version
mysql --version
```

### 2. Clone the repository

Replace `<REPOSITORY_URL>` with the team's Git repository URL.

```bash
git clone <REPOSITORY_URL>
cd friendship-bracelets
```

### 3. Install dependencies

From the project root, run:

```bash
uv sync
```

`uv sync` creates/updates `.venv` and installs the dependencies recorded
in `pyproject.toml` and `uv.lock`. It serves a similar purpose to
`pip install -r requirements.txt`, while using this project's uv
lockfile for consistent versions.

Activate the virtual environment:

```bash
source .venv/bin/activate
```

### 4. Configure environment variables

Create your local `.env` file:

```bash
cp .env.example .env
```

Update `.env` with your own local values:

```dotenv
SECRET_KEY=replace-with-your-own-secret-key
DEBUG=True

DB_NAME=friendship_bracelets
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Use your own MySQL credentials. Never commit `.env` or share real
passwords.

### 5. Run the development server

```bash
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser. The home page currently
displays a simple Hello message to confirm the server is working.

## Git Workflow

Update your local `main` branch:

```bash
git checkout main
git pull origin main
```

Create a branch for your task:

```bash
git checkout -b feature/your-task-name
```

Examples: `feature/catalog-models`, `feature/order-api`,
`feature/payment-verification`.

After making changes:

```bash
git status
git add .
git commit -m "Describe your changes"
git push -u origin feature/your-task-name
```

Open a pull request for review before merging your work into `main`.

Commit `pyproject.toml`, `uv.lock`, the Django project and app files,
`.env.example`, `.gitignore`, and this README. Do not commit `.env` or
`.venv/`.

### 4. Create the database and user

Open MySQL as root:

- Ubuntu/Mac: `mysql -u root -p` (if access is denied, try `sudo mysql`)
- Windows: open "MySQL 8.0 Command Line Client" (or a query tab in MySQL Workbench)

Then run (change the password):

```sql
CREATE DATABASE friendship_bracelets CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'bracelets'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL PRIVILEGES ON friendship_bracelets.* TO 'bracelets'@'localhost';
FLUSH PRIVILEGES;
```

Type `exit` to leave MySQL. To check that the new user works:

```bash
mysql -u bracelets -p friendship_bracelets
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Then edit `.env`:

```
SECRET_KEY=replace-with-your-own-secret-key
DEBUG=True

DB_NAME=friendship_bracelets
DB_USER=bracelets
DB_PASSWORD=the-password-you-chose
DB_HOST=127.0.0.1
DB_PORT=3306
```

Never commit `.env` or share real passwords.

### 6. Create the tables

```bash
uv run python manage.py migrate
```

### 7. Run the development server

```bash
uv run python manage.py runserver
```

## 📱 Business & Contact

- **Telegram:** [@friendshipbracelets1](https://t.me/friendshipbracelets1)

---

_Built to make personalized friendship bracelets easier to order and manage._
