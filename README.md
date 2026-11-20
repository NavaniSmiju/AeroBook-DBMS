# AeroBook – Airline Reservation and Flight Management System

## Project Overview

AeroBook is a database-driven Airline Reservation and Flight Management System developed as part of our Database Management Systems (DBMS) project.

The project brings together flight management, passenger reservations, staff scheduling, onboard services and other airline activities through a centralized relational database.

Built using MySQL and Python, with a Streamlit-based interface, AeroBook provides separate functionalities for passengers, staff and administrators, making airline operations more organized and accessible.

## Technologies Used

| Technology | Purpose |
|---|---|
| MySQL | Relational database management |
| Python 3.11 | Backend development and application logic |
| Streamlit | Interactive web application interface |
| Pandas | Data handling and presentation |
| mysql-connector-python | Python–MySQL connectivity |
| HTML & CSS | Interface styling |

## Features

### Passenger Module
- User registration and login.
- Search and book available flights.
- View booking details and reservation history.
- Browse onboard food menus.
- Earn loyalty points after reaching the destination.
- Redeem loyalty points for rewards such as free Wi-Fi and additional baggage.
- Access selected movies, shows and music through the in-flight entertainment system.
- Watch selected content together through synchronized viewing sessions.

### Staff Module
- Secure staff login.
- View assigned flight schedules.
- Access relevant staff scheduling information.

### Admin Module
- View and edit flight details.
- Cancel flights and bookings.
- Assign staff members to flight schedules.
- Manage employee schedules and staff assignments.

## Database Design

AeroBook uses MySQL as its relational database management system and consists of 21 interconnected tables.

The database is organized into the following functional areas:

- **Flight Management:** Flights, airports, aircraft, flight schedules and fuel records.
- **Staff Management:** Staff details, home bases, repositioning, employee schedules and flight assignments.
- **Passenger and Booking Management:** User accounts, passenger information and reservations.
- **Food Management:** Food items and their association with flights.
- **Loyalty Management:** Rewards and points transactions.
- **In-Flight Entertainment:** Entertainment screens, content and synchronized watch sessions.

Primary keys uniquely identify records, while foreign keys connect related tables and help maintain referential integrity.

### Entity Relationship Diagram

The ER diagram illustrates the database structure, entities and their relationships.

![AeroBook ER Diagram](https://drive.google.com/file/d/1t0JIjBWb9ycliTrXggq6Cd6h3OzH0tLI/view?usp=sharing)

## Project Structure

The repository should contain the application files and supporting resources needed to run the project.

```text
AeroBook/
│
├── assets/                         # Images and application resources
├── app.py                          # Main Streamlit application
├── db.py                           # MySQL database connectivity
├── requirements.txt                # Python dependencies
├── database/                       # SQL setup scripts
│
├── aerobook_crew_roster.py         # Crew roster functionality
├── aerobook_generate_staff_passwords.py
├── build_reduced_schedule.py
├── build_reduced_schedule_two_per_route.py
├── generate_roster.py
├── generate_roster_balanced.py
├── generate_roster_option_b.py
├── generate_reduced_roster*.py     # Supporting roster-generation scripts
│
├── README.md                       # Project documentation
└── .gitignore                      # Files excluded from version control
```

Only scripts required for the project or useful for understanding its supporting functionality need to be included in the published repository. The `database/` folder should contain the SQL setup scripts used to create and populate the database.

## How to Run

### Prerequisites

- Python 3.11
- MySQL Server
- Visual Studio Code (recommended)

Python 3.11 is the version used for the project's tested environment.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd AeroBook
```

### 2. Create and Activate a Virtual Environment

On Windows:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up the MySQL Database

1. Start your MySQL server.
2. Create the AeroBook database, if the SQL setup script does not create it.
3. Run the SQL setup script or scripts included in the repository to create the tables and insert the required data.
4. Configure the database connection using environment variables as described below.

For example, if the setup file is named `database/aerobook.sql`, it can be imported from a terminal using:

```bash
mysql -u root -p < database/aerobook.sql
```

Replace the example filename with the actual SQL setup filename in the repository.

### 5. Configure MySQL Credentials

Database credentials should not be hardcoded in `db.py` or committed to GitHub.

The application should read the connection details from environment variables. For example, in `db.py`:

```python
import os
import mysql.connector

connection = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME", "aerobook")
)
```

In the same PowerShell terminal where you will run the application, set your local values:

```powershell
$env:DB_HOST="localhost"
$env:DB_USER="your_mysql_username"
$env:DB_PASSWORD="your_mysql_password"
$env:DB_NAME="aerobook"
```

Use your own local MySQL credentials.

### 6. Run the Application

From the project directory, execute:

```bash
streamlit run app.py
```

The application will launch in your default web browser.

## Team Members

This project was collaboratively developed by:

- Khushi Tyagi
- Navani Smiju
- Parvathi Vineed
- Tanishq Goel

## Project Objective

Through AeroBook, we aim to demonstrate the practical application of relational database concepts in developing an integrated airline management system. The project brings together database design, data relationships, backend programming and user interface development in one application.

---

**Developed as part of our Database Management Systems academic project.**
