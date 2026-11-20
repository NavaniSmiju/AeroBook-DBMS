
import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="*******",
        database="aerobook_db"
    )


def get_food_items():
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT Food_ID, Food_Name, Food_Description,
                   Food_Category, Dietary_Type,
                   Allergen_Information, Price, Availability_Status
            FROM Food
            ORDER BY Food_Category, Food_Name
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def get_airports():
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT airport_id, airport_code, airport_name, city, country
            FROM AIRPORT
            ORDER BY city
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def search_flights(source_id, destination_id, travel_date):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                f.flight_id,
                f.flight_number,
                f.flight_type,
                f.base_fare,
                f.baggage_allowance,
                f.meal_service,
                f.entertainment_available,
                f.wifi_available,
                src.airport_code AS source_code,
                src.city AS source_city,
                dest.airport_code AS destination_code,
                dest.city AS destination_city,
                ac.aircraft_model,
                ac.capacity,
                fs.schedule_date,
                fs.departure_time,
                fs.arrival_datetime,
                fs.departure_terminal,
                fs.arrival_terminal,
                fs.gate_number,
                fs.schedule_status
            FROM FLIGHT f
            JOIN AIRPORT src
                ON f.source_airport_id = src.airport_id
            JOIN AIRPORT dest
                ON f.destination_airport_id = dest.airport_id
            JOIN AIRCRAFT ac
                ON f.aircraft_id = ac.aircraft_id
            JOIN FLIGHT_SCHEDULE fs
                ON f.flight_id = fs.flight_id
            WHERE f.source_airport_id = %s
              AND f.destination_airport_id = %s
              AND fs.schedule_date = %s
            ORDER BY fs.departure_time
        """, (source_id, destination_id, travel_date))
        return cursor.fetchall()
    finally:
        conn.close()


def get_flight_food(flight_id, schedule_date, departure_time):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                fo.Food_ID,
                fo.Food_Name,
                fo.Food_Description,
                fo.Food_Category,
                fo.Dietary_Type,
                fo.Allergen_Information,
                fo.Price,
                fo.Availability_Status
            FROM FLIGHT_FOOD ff
            JOIN FOOD fo
                ON ff.food_id = fo.Food_ID
            WHERE ff.flight_id = %s
              AND ff.schedule_date = %s
              AND ff.departure_time = %s
            ORDER BY fo.Food_Category, fo.Food_Name
        """, (flight_id, schedule_date, departure_time))
        return cursor.fetchall()
    finally:
        conn.close()
def get_passenger_dashboard(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT points_balance
            FROM users
            WHERE user_id = %s
        """, (user_id,))
        user_data = cursor.fetchone()

        cursor.execute("""
            SELECT
                COUNT(*) AS total_bookings,
                SUM(
                    CASE
                        WHEN schedule_date >= CURDATE()
                        AND booking_status <> 'Cancelled'
                        THEN 1 ELSE 0
                    END
                ) AS upcoming_trips
            FROM booking
            WHERE user_id = %s
        """, (user_id,))
        booking_stats = cursor.fetchone()

        cursor.execute("""
            SELECT booking_id, flight_id, schedule_date,
                   departure_time, booking_status,
                   payment_status, total_fare
            FROM booking
            WHERE user_id = %s
            ORDER BY booking_date DESC
            LIMIT 5
        """, (user_id,))
        recent_bookings = cursor.fetchall()

        return {
            "points": user_data["points_balance"] if user_data else 0,
            "total_bookings": booking_stats["total_bookings"] or 0,
            "upcoming_trips": booking_stats["upcoming_trips"] or 0,
            "recent_bookings": recent_bookings
        }

    finally:
        cursor.close()
        conn.close()




def get_passenger_rewards(passenger_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT points_balance
            FROM passenger
            WHERE passenger_id = %s
        """, (passenger_id,))
        passenger = cursor.fetchone()

        cursor.execute("""
            SELECT reward_id, reward_name, reward_type,
                   points_required, reward_description,
                   availability_status
            FROM reward
            WHERE availability_status = 'Available'
            ORDER BY points_required
        """)
        rewards = cursor.fetchall()

        cursor.execute("""
            SELECT transaction_type, points_change,
                   transaction_date, transaction_status
            FROM points_transaction
            WHERE passenger_id = %s
            ORDER BY transaction_date DESC
            LIMIT 20
        """, (passenger_id,))
        transactions = cursor.fetchall()

        return {
            "points": passenger["points_balance"] if passenger else 0,
            "rewards": rewards,
            "transactions": transactions
        }

    finally:
        cursor.close()
        conn.close()




def create_booking(user_id, flight_id, schedule_date, departure_time,
                   total_fare, passengers):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        conn.start_transaction()

        # Lock the flight schedule while assigning seats.
        cursor.execute("""
            SELECT aircraft_id
            FROM flight
            WHERE flight_id = %s
        """, (flight_id,))

        flight = cursor.fetchone()

        if not flight:
            raise Exception("Flight not found.")

        aircraft_id = flight[0]

        cursor.execute("""
            SELECT aircraft_model, capacity
            FROM aircraft
            WHERE aircraft_id = %s
        """, (aircraft_id,))

        aircraft = cursor.fetchone()

        if not aircraft:
            raise Exception("Aircraft not found.")

        aircraft_model = aircraft[0]
        capacity = aircraft[1]

        # Get the seat layout for this aircraft.
        if "A350" in aircraft_model:
            seat_letters = "ABCDEFGHJK"
        elif "A320" in aircraft_model or "A321" in aircraft_model:
            seat_letters = "ABCDEF"
        else:
            raise Exception("Seat layout not configured for this aircraft.")

        valid_seats = {
            f"{row}{letter}"
            for row in range(1, (capacity + len(seat_letters) - 1)
                             // len(seat_letters) + 1)
            for letter in seat_letters
        }

        # Lock this particular schedule to prevent simultaneous
        # bookings from assigning the same seat.
        cursor.execute("""
            SELECT flight_id
            FROM flight_schedule
            WHERE flight_id = %s
              AND schedule_date = %s
              AND departure_time = %s
            FOR UPDATE
        """, (flight_id, schedule_date, departure_time))

        if not cursor.fetchone():
            raise Exception("Flight schedule not found.")

        # Check seats already assigned to this flight schedule.
        cursor.execute("""
            SELECT bp.seat_number
            FROM booking_passenger bp
            JOIN booking b
                ON bp.booking_id = b.booking_id
            WHERE b.flight_id = %s
              AND b.schedule_date = %s
              AND b.departure_time = %s
              AND b.booking_status <> 'Cancelled'
              AND bp.seat_number IS NOT NULL
        """, (flight_id, schedule_date, departure_time))

        occupied_seats = {row[0] for row in cursor.fetchall()}

        # Validate selected seats.
        selected_seats = []

        for passenger in passengers:
            seat = passenger.get("seat_number")

            if not seat or seat not in valid_seats:
                raise Exception(
                    f"Invalid seat selection: {seat}"
                )

            if seat in occupied_seats or seat in selected_seats:
                raise Exception(
                    f"Seat {seat} is already occupied. Please choose another."
                )

            selected_seats.append(seat)

        # Create the main booking.
        cursor.execute("""
            INSERT INTO booking (
                user_id, flight_id, schedule_date,
                departure_time, total_fare,
                booking_status, payment_status
            )
            VALUES (%s, %s, %s, %s, %s, 'Confirmed', 'Pending')
        """, (
            user_id, flight_id, schedule_date,
            departure_time, total_fare
        ))

        booking_id = cursor.lastrowid

        # Create passenger records and save their seat numbers.
        for passenger in passengers:
            cursor.execute("""
                INSERT INTO passenger (
                    user_id, first_name, middle_name, last_name,
                    date_of_birth, nationality, passport_number,
                    email, phone_number
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                passenger["first_name"],
                passenger.get("middle_name") or None,
                passenger["last_name"],
                passenger.get("date_of_birth"),
                passenger.get("nationality") or None,
                passenger.get("passport_number") or None,
                passenger.get("email") or None,
                passenger.get("phone_number") or None
            ))

            passenger_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO booking_passenger (
                    booking_id, passenger_id, seat_number
                )
                VALUES (%s, %s, %s)
            """, (
                booking_id,
                passenger_id,
                passenger["seat_number"]
            ))

        conn.commit()
        return booking_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()




def award_completed_flight_points():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT
                b.booking_id,
                b.total_fare,
                bp.passenger_id
            FROM booking b
            JOIN booking_passenger bp
                ON b.booking_id = bp.booking_id
            JOIN flight_schedule fs
                ON b.flight_id = fs.flight_id
                AND b.schedule_date = fs.schedule_date
                AND b.departure_time = fs.departure_time
            WHERE b.booking_status = 'Confirmed'
              AND b.payment_status = 'Paid'
              AND fs.arrival_datetime <= NOW()
        """)

        eligible_bookings = cursor.fetchall()

        for booking in eligible_bookings:
            cursor.execute("""
                SELECT transaction_id
                FROM points_transaction
                WHERE booking_id = %s
                  AND passenger_id = %s
                  AND transaction_type = 'Flight Earned'
                  AND transaction_status = 'Completed'
            """, (
                booking["booking_id"],
                booking["passenger_id"]
            ))

            existing = cursor.fetchone()

            if existing:
                continue

            points = int(booking["total_fare"] // 100)

            if points <= 0:
                continue

            cursor.execute("""
                UPDATE passenger
                SET points_balance = points_balance + %s
                WHERE passenger_id = %s
            """, (points, booking["passenger_id"]))

            cursor.execute("""
                INSERT INTO points_transaction (
                    passenger_id,
                    booking_id,
                    transaction_type,
                    points_change,
                    transaction_status
                )
                VALUES (%s, %s, 'Flight Earned', %s, 'Completed')
            """, (
                booking["passenger_id"],
                booking["booking_id"],
                points
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def redeem_reward(passenger_id, reward_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        conn.start_transaction()

        cursor.execute("""
            SELECT points_balance
            FROM passenger
            WHERE passenger_id = %s
            FOR UPDATE
        """, (passenger_id,))

        passenger = cursor.fetchone()

        if not passenger:
            raise ValueError("Passenger loyalty profile not found.")

        cursor.execute("""
            SELECT reward_name, points_required
            FROM reward
            WHERE reward_id = %s
              AND availability_status = 'Available'
        """, (reward_id,))

        reward = cursor.fetchone()

        if not reward:
            raise ValueError("This reward is no longer available.")

        required_points = reward["points_required"]

        if passenger["points_balance"] < required_points:
            raise ValueError("You do not have enough points.")

        cursor.execute("""
            UPDATE passenger
            SET points_balance = points_balance - %s
            WHERE passenger_id = %s
        """, (required_points, passenger_id))

        cursor.execute("""
            INSERT INTO points_transaction (
                passenger_id,
                reward_id,
                transaction_type,
                points_change,
                transaction_status
            )
            VALUES (%s, %s, 'Redemption', %s, 'Completed')
        """, (
            passenger_id,
            reward_id,
            -required_points
        ))

        conn.commit()
        return reward["reward_name"]

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()



def award_completed_flight_points():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        conn.start_transaction()

        cursor.execute("""
            SELECT
                b.booking_id,
                b.total_fare,
                bp.passenger_id,
                fs.arrival_datetime,
                (
                    SELECT COUNT(*)
                    FROM booking_passenger bp2
                    WHERE bp2.booking_id = b.booking_id
                ) AS passenger_count
            FROM booking b
            JOIN booking_passenger bp
                ON bp.booking_id = b.booking_id
            JOIN flight_schedule fs
                ON fs.flight_id = b.flight_id
                AND fs.schedule_date = b.schedule_date
                AND fs.departure_time = b.departure_time
            WHERE b.payment_status = 'Paid'
              AND fs.arrival_datetime <= NOW()
              AND b.booking_status <> 'Cancelled'
        """)

        completed_bookings = cursor.fetchall()
        awarded_count = 0

        for booking in completed_bookings:
            cursor.execute("""
                SELECT transaction_id
                FROM points_transaction
                WHERE booking_id = %s
                  AND passenger_id = %s
                  AND transaction_type = 'Earned'
                LIMIT 1
            """, (
                booking["booking_id"],
                booking["passenger_id"]
            ))

            if cursor.fetchone():
                continue

            passenger_count = booking["passenger_count"] or 1
            passenger_fare = (
                float(booking["total_fare"]) / passenger_count
            )
            points = int(passenger_fare // 100) * 10

            if points <= 0:
                continue

            cursor.execute("""
                UPDATE passenger
                SET points_balance = points_balance + %s
                WHERE passenger_id = %s
            """, (points, booking["passenger_id"]))

            cursor.execute("""
                INSERT INTO points_transaction (
                    passenger_id,
                    booking_id,
                    transaction_type,
                    points_change,
                    transaction_status
                )
                VALUES (%s, %s, 'Earned', %s, 'Completed')
            """, (
                booking["passenger_id"],
                booking["booking_id"],
                points
            ))

            awarded_count += 1

        cursor.execute("""
            UPDATE users u
            JOIN passenger p
                ON LOWER(u.email) = LOWER(p.email)
            SET u.points_balance = p.points_balance
        """)

        conn.commit()
        return awarded_count

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()



def redeem_reward(passenger_id, reward_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        conn.start_transaction()

        cursor.execute("""
            SELECT points_balance
            FROM passenger
            WHERE passenger_id = %s
            FOR UPDATE
        """, (passenger_id,))

        passenger = cursor.fetchone()

        if not passenger:
            raise ValueError("Passenger loyalty profile not found.")

        cursor.execute("""
            SELECT points_required, reward_name
            FROM reward
            WHERE reward_id = %s
              AND availability_status = 'Available'
            FOR UPDATE
        """, (reward_id,))

        reward = cursor.fetchone()

        if not reward:
            raise ValueError("This reward is not available.")

        required_points = reward["points_required"]

        if passenger["points_balance"] < required_points:
            raise ValueError("You do not have enough points.")

        cursor.execute("""
            UPDATE passenger
            SET points_balance = points_balance - %s
            WHERE passenger_id = %s
        """, (required_points, passenger_id))

        cursor.execute("""
            INSERT INTO points_transaction (
                passenger_id,
                reward_id,
                transaction_type,
                points_change,
                transaction_status
            )
            VALUES (%s, %s, 'Redeemed', %s, 'Completed')
        """, (passenger_id, reward_id, -required_points))

        cursor.execute("""
            UPDATE users u
            JOIN passenger p
                ON LOWER(u.email) = LOWER(p.email)
            SET u.points_balance = p.points_balance
            WHERE p.passenger_id = %s
        """, (passenger_id,))

        conn.commit()
        return reward["reward_name"]

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()



def get_available_seats(flight_id, schedule_date, departure_time):
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("""
            SELECT a.aircraft_model, a.capacity
            FROM flight f
            JOIN aircraft a
                ON f.aircraft_id = a.aircraft_id
            WHERE f.flight_id = %s
        """, (flight_id,))

        aircraft = cursor.fetchone()

        if not aircraft:
            return []

        aircraft_model, capacity = aircraft

        if "A350" in aircraft_model:
            seat_letters = "ABCDEFGHJK"
        elif "A320" in aircraft_model or "A321" in aircraft_model:
            seat_letters = "ABCDEF"
        else:
            return []

        all_seats = [
            f"{row}{letter}"
            for row in range(1, capacity // len(seat_letters) + 1)
            for letter in seat_letters
        ]

        cursor.execute("""
            SELECT bp.seat_number
            FROM booking_passenger bp
            JOIN booking b
                ON bp.booking_id = b.booking_id
            WHERE b.flight_id = %s
              AND b.schedule_date = %s
              AND b.departure_time = %s
              AND b.booking_status <> 'Cancelled'
              AND bp.seat_number IS NOT NULL
        """, (flight_id, schedule_date, departure_time))

        occupied_seats = {row[0] for row in cursor.fetchall()}

        return [
            seat for seat in all_seats
            if seat not in occupied_seats
        ]

    finally:
        cursor.close()
        conn.close()





def get_passenger_bookings(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT
                b.booking_id,
                b.flight_id,
                f.flight_number,
                b.schedule_date,
                b.departure_time,
                b.booking_date,
                b.booking_status,
                b.payment_status,
                b.total_fare,
                GROUP_CONCAT(
                    DISTINCT bp.seat_number
                    ORDER BY bp.passenger_id
                    SEPARATOR ', '
                ) AS seat_number
            FROM booking b
            LEFT JOIN flight f
                ON b.flight_id = f.flight_id
            LEFT JOIN booking_passenger bp
                ON b.booking_id = bp.booking_id
            WHERE b.user_id = %s
            GROUP BY
                b.booking_id,
                b.flight_id,
                f.flight_number,
                b.schedule_date,
                b.departure_time,
                b.booking_date,
                b.booking_status,
                b.payment_status,
                b.total_fare
            ORDER BY b.booking_date DESC
        """, (user_id,))

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()
def get_watch_together_options(user_id):
    """Find other confirmed passengers with operational screens on the same flight."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT DISTINCT
                fs1.schedule_id,
                f.flight_number,
                s1.screen_id AS own_screen_id,
                s1.seat_number AS own_seat,
                s2.screen_id AS target_screen_id,
                s2.seat_number AS target_seat,
                b2.user_id AS target_user_id
            FROM booking b1
            JOIN flight f ON f.flight_id = b1.flight_id
            JOIN flight_schedule fs1
                ON fs1.flight_id = b1.flight_id
                AND fs1.schedule_date = b1.schedule_date
                AND fs1.departure_time = b1.departure_time
            JOIN booking_passenger bp1
                ON bp1.booking_id = b1.booking_id
            JOIN ife_screen s1
                ON s1.aircraft_id = f.aircraft_id
                AND s1.seat_number = bp1.seat_number
                AND s1.device_status = 'Operational'
            JOIN booking b2
                ON b2.flight_id = b1.flight_id
                AND b2.schedule_date = b1.schedule_date
                AND b2.departure_time = b1.departure_time
                AND b2.booking_status = 'Confirmed'
                AND b2.user_id <> b1.user_id
            JOIN flight_schedule fs2
                ON fs2.schedule_id = fs1.schedule_id
            JOIN booking_passenger bp2
                ON bp2.booking_id = b2.booking_id
            JOIN ife_screen s2
                ON s2.aircraft_id = f.aircraft_id
                AND s2.seat_number = bp2.seat_number
                AND s2.device_status = 'Operational'
            WHERE b1.user_id = %s
              AND b1.booking_status = 'Confirmed'
              AND s1.screen_id <> s2.screen_id
            ORDER BY s2.seat_number
        """, (user_id,))

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def send_watch_together_invitations(
    user_id, content_id, schedule_id, own_screen_id, target_screen_ids
):
    """Create one group session and invite multiple passengers."""
    if not target_screen_ids:
        raise ValueError("Select at least one passenger.")

    target_screen_ids = list(dict.fromkeys(target_screen_ids))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT content_id
            FROM entertainment_content
            WHERE content_id = %s
              AND availability_status = 'Available'
        """, (content_id,))

        if not cursor.fetchone():
            raise ValueError("This entertainment content is unavailable.")

        cursor.execute("""
            SELECT DISTINCT
                b1.user_id,
                b1.flight_id,
                b1.schedule_date,
                b1.departure_time,
                f.aircraft_id,
                s1.screen_id
            FROM booking b1
            JOIN flight f ON f.flight_id = b1.flight_id
            JOIN flight_schedule fs
                ON fs.flight_id = b1.flight_id
                AND fs.schedule_date = b1.schedule_date
                AND fs.departure_time = b1.departure_time
            JOIN booking_passenger bp1
                ON bp1.booking_id = b1.booking_id
            JOIN ife_screen s1
                ON s1.aircraft_id = f.aircraft_id
                AND s1.seat_number = bp1.seat_number
            WHERE b1.user_id = %s
              AND b1.booking_status = 'Confirmed'
              AND fs.schedule_id = %s
              AND s1.screen_id = %s
              AND s1.device_status = 'Operational'
        """, (user_id, schedule_id, own_screen_id))

        host = cursor.fetchone()

        if not host:
            raise ValueError("Your confirmed booking or operational screen could not be verified.")

        invited_users = []

        for target_screen_id in target_screen_ids:
            cursor.execute("""
                SELECT DISTINCT b2.user_id
                FROM booking b2
                JOIN flight_schedule fs
                    ON fs.flight_id = b2.flight_id
                    AND fs.schedule_date = b2.schedule_date
                    AND fs.departure_time = b2.departure_time
                JOIN flight f
                    ON f.flight_id = b2.flight_id
                JOIN booking_passenger bp2
                    ON bp2.booking_id = b2.booking_id
                JOIN ife_screen s2
                    ON s2.aircraft_id = f.aircraft_id
                    AND s2.seat_number = bp2.seat_number
                WHERE fs.schedule_id = %s
                  AND b2.booking_status = 'Confirmed'
                  AND b2.user_id <> %s
                  AND s2.screen_id = %s
                  AND s2.device_status = 'Operational'
            """, (schedule_id, user_id, target_screen_id))

            target = cursor.fetchone()

            if not target:
                raise ValueError(
                    f"Passenger screen {target_screen_id} is not eligible for this flight."
                )

            invited_users.append((target_screen_id, target["user_id"]))

        # The existing watch_session table requires two screen IDs.
        # Store the first invitee there and all members in the member table.
        first_screen_id = invited_users[0][0]

        cursor.execute("""
            INSERT INTO watch_session (
                content_id,
                screen_id_1,
                screen_id_2,
                session_status,
                playback_position,
                schedule_id
            )
            VALUES (%s, %s, %s, 'Pending', 0, %s)
        """, (content_id, own_screen_id, first_screen_id, schedule_id))

        session_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO watch_session_member (
                session_id, screen_id, user_id,
                member_role, invitation_status, joined_at
            )
            VALUES (%s, %s, %s, 'Host', 'Accepted', NOW())
        """, (session_id, own_screen_id, user_id))

        for screen_id, invited_user_id in invited_users:
            cursor.execute("""
                INSERT INTO watch_session_member (
                    session_id, screen_id, user_id,
                    member_role, invitation_status
                )
                VALUES (%s, %s, %s, 'Guest', 'Pending')
            """, (session_id, screen_id, invited_user_id))

        conn.commit()
        return session_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def send_watch_together_invitation(
    user_id, content_id, schedule_id, own_screen_id, target_screen_id
):
    """Compatibility function for a single invitation."""
    return send_watch_together_invitations(
        user_id, content_id, schedule_id, own_screen_id, [target_screen_id]
    )


def get_pending_watch_invitations(user_id):
    """Get all pending group invitations for this passenger."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT
                m.member_id,
                m.session_id,
                m.screen_id,
                ws.content_id,
                ec.title,
                ws.schedule_id,
                ws.playback_position,
                s1.seat_number AS inviter_seat,
                s2.seat_number AS invited_seat
            FROM watch_session_member m
            JOIN watch_session ws
                ON ws.session_id = m.session_id
            JOIN entertainment_content ec
                ON ec.content_id = ws.content_id
            JOIN ife_screen s1
                ON s1.screen_id = ws.screen_id_1
            JOIN ife_screen s2
                ON s2.screen_id = m.screen_id
            WHERE m.user_id = %s
              AND m.member_role = 'Guest'
              AND m.invitation_status = 'Pending'
              AND ws.session_status = 'Pending'
            ORDER BY m.session_id DESC
        """, (user_id,))

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def respond_to_watch_invitation(user_id, member_id, response):
    """Accept or reject an individual invitation."""
    response = response.strip().capitalize()

    if response not in ("Accepted", "Rejected"):
        raise ValueError("Response must be Accepted or Rejected.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT session_id
            FROM watch_session_member
            WHERE member_id = %s
              AND user_id = %s
              AND member_role = 'Guest'
              AND invitation_status = 'Pending'
        """, (member_id, user_id))

        invitation = cursor.fetchone()

        if not invitation:
            raise ValueError("This invitation is no longer available.")

        session_id = invitation["session_id"]

        cursor.execute("""
            UPDATE watch_session_member
            SET invitation_status = %s,
                joined_at = CASE
                    WHEN %s = 'Accepted' THEN NOW()
                    ELSE NULL
                END
            WHERE member_id = %s
              AND user_id = %s
        """, (response, response, member_id, user_id))

        cursor.execute("""
            SELECT
                SUM(invitation_status = 'Accepted') AS accepted_count,
                SUM(invitation_status = 'Pending') AS pending_count
            FROM watch_session_member
            WHERE session_id = %s
        """, (session_id,))

        counts = cursor.fetchone()

        if counts["accepted_count"] > 1:
            cursor.execute("""
                UPDATE watch_session
                SET session_status = 'Accepted'
                WHERE session_id = %s
            """, (session_id,))

        elif counts["pending_count"] == 0:
            cursor.execute("""
                UPDATE watch_session
                SET session_status = 'Rejected'
                WHERE session_id = %s
            """, (session_id,))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def leave_watch_together_session(user_id, session_id):
    """Allow a passenger to leave without removing other group members."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE watch_session_member
            SET invitation_status = 'Left',
                left_at = NOW()
            WHERE session_id = %s
              AND user_id = %s
              AND invitation_status = 'Accepted'
        """, (session_id, user_id))

        if cursor.rowcount == 0:
            raise ValueError("You are not an active member of this session.")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()
    
