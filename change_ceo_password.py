import mysql.connector
import hashlib
import secrets

PASSWORD = "abcd@2502"
ITERATIONS = 600000

salt = secrets.token_hex(16)
digest = hashlib.pbkdf2_hmac(
    "sha256",
    PASSWORD.encode(),
    salt.encode(),
    ITERATIONS
).hex()

password_hash = f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"

connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="**********",
    database="aerobook_db"
)

cursor = connection.cursor()

cursor.execute("""
    UPDATE STAFF
    SET password_hash = %s
    WHERE staff_id = 41
      AND LOWER(first_name) = 'navani'
      AND LOWER(last_name) = 'smiju'
      AND staff_role = 'Admin'
""", (password_hash,))

if cursor.rowcount != 1:
    connection.rollback()
    print("Update failed: Admin account was not uniquely matched.")
else:
    connection.commit()
    print("Admin password updated successfully.")

cursor.close()
connection.close()
