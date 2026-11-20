"""
AeroBook: generate initial passwords for ALL staff accounts.

This version shows progress while hashing and does not hold a database
transaction open during the CPU-intensive password hashing step.

Install:
    py -m pip install mysql-connector-python

Run from the folder containing this file:
    py aerobook_generate_staff_passwords.py

It updates only STAFF rows whose password_hash is NULL.
Existing password hashes are never overwritten.
"""

import csv
import getpass
import hashlib
import secrets
import string
import sys
import time
from pathlib import Path

import mysql.connector

DB_NAME = "aerobook_db"
ITERATIONS = 600_000
OUTPUT_FILE = Path("aerobook_staff_initial_credentials.csv")
PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%*-_"


def make_password(length=18):
    chars = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%*-_"),
    ]
    chars.extend(secrets.choice(PASSWORD_ALPHABET) for _ in range(length - 4))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def make_password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def main():
    print("AeroBook - initial staff password setup", flush=True)
    print("This may take a few minutes. Progress will be displayed.", flush=True)

    host = input("MySQL host [localhost]: ").strip() or "localhost"
    port_text = input("MySQL port [3306]: ").strip() or "3306"
    db_user = input("MySQL username: ").strip()
    db_password = getpass.getpass("MySQL password: ")

    try:
        connection = mysql.connector.connect(
            host=host,
            port=int(port_text),
            user=db_user,
            password=db_password,
            database=DB_NAME,
            autocommit=False,
        )
    except Exception as exc:
        print(f"\nCould not connect to MySQL: {exc}")
        return

    cursor = connection.cursor(dictionary=True)
    credentials = []
    try:
        # Read accounts needing passwords. No transaction/row locks are held
        # while the CPU-intensive hashes are generated.
        cursor.execute("""
            SELECT staff_id, first_name, last_name, email
            FROM STAFF
            WHERE password_hash IS NULL
            ORDER BY staff_id
        """)
        staff_rows = cursor.fetchall()
        # End the read transaction before doing the CPU-intensive hashing.
        connection.commit()

        if not staff_rows:
            print("\nNo staff accounts need initial passwords.")
            return

        missing_email = [
            row for row in staff_rows
            if not row["email"] or not row["email"].strip()
        ]
        if missing_email:
            ids = ", ".join(str(row["staff_id"]) for row in missing_email)
            print("\nStopped safely. These staff accounts have no email: " + ids)
            print("Add their email addresses first, then run this script again.")
            return

        total = len(staff_rows)
        print(f"\nFound {total} staff accounts needing passwords.", flush=True)
        print("Generating secure password hashes; please let it finish...", flush=True)
        started = time.time()

        prepared = []
        for index, staff in enumerate(staff_rows, start=1):
            password = make_password()
            password_hash = make_password_hash(password)
            prepared.append((password_hash, staff["staff_id"]))
            credentials.append({
                "staff_id": staff["staff_id"],
                "first_name": staff["first_name"],
                "last_name": staff["last_name"],
                "email": staff["email"],
                "initial_password": password,
            })

            if index % 10 == 0 or index == total:
                elapsed = time.time() - started
                print(
                    f"Hashed {index}/{total} staff accounts "
                    f"({elapsed:.1f} seconds elapsed)",
                    flush=True,
                )

        # Prepare the credentials file before changing the database.
        temp_file = OUTPUT_FILE.with_suffix(".csv.tmp")
        with temp_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "staff_id", "first_name", "last_name",
                    "email", "initial_password",
                ],
            )
            writer.writeheader()
            writer.writerows(credentials)

        try:
            temp_file.chmod(0o600)
        except OSError:
            pass

        # Apply all hashes in one short transaction. The WHERE clause ensures
        # that an existing hash is never replaced.
        # The connection is now idle; the first UPDATE starts a new transaction.
        update_cursor = connection.cursor()
        try:
            for password_hash, staff_id in prepared:
                update_cursor.execute(
                    """
                    UPDATE STAFF
                    SET password_hash = %s
                    WHERE staff_id = %s
                      AND password_hash IS NULL
                    """,
                    (password_hash, staff_id),
                )
                if update_cursor.rowcount != 1:
                    raise RuntimeError(
                        f"Staff ID {staff_id} was changed during setup. "
                        "No changes from this run were committed."
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            temp_file.unlink(missing_ok=True)
            raise
        finally:
            update_cursor.close()

        temp_file.replace(OUTPUT_FILE)
        print(f"\nSUCCESS: passwords created for {total} staff accounts.")
        print(f"Credentials file: {OUTPUT_FILE.resolve()}")
        print("Keep this CSV private. Give each staff member only their own credentials.")
        print("Require staff to change their initial password after first login.")

    except KeyboardInterrupt:
        connection.rollback()
        print("\n\nInterrupted. No database changes from this run were committed.")
        print("You can safely run the script again.")
    except Exception as exc:
        connection.rollback()
        print(f"\nSetup failed; database changes from this run were rolled back: {exc}")
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
