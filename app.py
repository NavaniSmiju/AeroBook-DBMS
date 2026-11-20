
import streamlit as st
import pandas as pd

from datetime import datetime, date, time

from db import (
    get_connection,
    get_food_items,
    get_airports,
    create_booking,
    search_flights,
    get_flight_food,
    get_passenger_dashboard,
    get_passenger_rewards,
    award_completed_flight_points,
    redeem_reward,
    get_available_seats,
    get_passenger_bookings,
    get_watch_together_options,
    send_watch_together_invitations,
    get_pending_watch_invitations,
    respond_to_watch_invitation,
    leave_watch_together_session,
)









# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="AeroBook | Flights & Food",
    page_icon="✈",
    layout="wide",
)


import hashlib
import hmac
import secrets

# =====================================================
# AEROBOOK LOGIN / REGISTRATION
# =====================================================

PBKDF2_ITERATIONS = 600000


def verify_password(password, stored_hash):
    """Verify the PBKDF2 hash used by AeroBook staff accounts."""
    if not stored_hash:
        return False

    try:
        algorithm, iterations, salt, expected_digest = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False

        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations)
        ).hex()

        return hmac.compare_digest(actual_digest, expected_digest)
    except (ValueError, TypeError):
        return False


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def authenticate(account_type, login_id, password):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if account_type == "Passenger":
            cursor.execute(
                """
                SELECT user_id, username, email, password_hash,
                       user_role, account_status
                FROM USERS
                WHERE LOWER(email) = LOWER(%s)
                   OR LOWER(username) = LOWER(%s)
                """,
                (login_id, login_id)
            )
            account = cursor.fetchone()

            if not account:
                return None, "Passenger account not found."

            if str(account["user_role"]).lower() != "passenger":
                return None, "This account is not a Passenger account."

            if str(account["account_status"]).lower() != "active":
                return None, "Your account is not active."

            if not verify_password(password, account["password_hash"]):
                return None, "Incorrect password."

            return {
                "id": account["user_id"],
                "name": account["username"],
                "email": account["email"],
                "type": "Passenger",
                "role": "Passenger"
            }, None

        cursor.execute(
            """
            SELECT staff_id, first_name, last_name, email,
                   password_hash, staff_role, staff_status
            FROM STAFF
            WHERE LOWER(email) = LOWER(%s)
            """,
            (login_id,)
        )
        account = cursor.fetchone()

        if not account:
            return None, "Staff account not found."

        if str(account["staff_role"]).lower() not in ("admin", "staff"):
            return None, "This account does not have Staff login access."

        if str(account["staff_status"]).lower() != "active":
            return None, "Your staff account is not active."

        if not verify_password(password, account["password_hash"]):
            return None, "Incorrect password."

        return {
            "id": account["staff_id"],
            "name": f'{account["first_name"]} {account["last_name"]}',
            "email": account["email"],
            "type": "Staff",
            "role": account["staff_role"]
        }, None

    finally:
        cursor.close()
        conn.close()


def create_passenger_account(username, email, phone, password):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT user_id
            FROM USERS
            WHERE LOWER(username) = LOWER(%s)
               OR LOWER(email) = LOWER(%s)
            """,
            (username, email)
        )

        if cursor.fetchone():
            return False, "That username or email is already registered."

        cursor.execute(
            """
            INSERT INTO USERS
                (username, email, password_hash, phone_number,
                 user_role, account_status, points_balance)
            VALUES (%s, %s, %s, %s, 'Passenger', 'Active', 0)
            """,
            (username, email, hash_password(password), phone or None)
        )
        conn.commit()
        return True, "Your Passenger account has been created. You can now log in."

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


# Keep login state across Streamlit reruns.
if "aerobook_user" not in st.session_state:
    st.session_state.aerobook_user = None


# Login page: one centered card, with the native Streamlit controls inside it.
if st.session_state.aerobook_user is None:
    from pathlib import Path
    import base64

    background_path = Path(__file__).parent / "assets" / "aerobook_login_bg.png"
    if background_path.exists():
        encoded_background = base64.b64encode(background_path.read_bytes()).decode("utf-8")
        background_rule = (
            "background-image: linear-gradient(rgba(7, 28, 55, .08), rgba(7, 28, 55, .12)), "
            "url(data:image/png;base64," + encoded_background + ");"
        )
    else:
        background_rule = "background: linear-gradient(135deg, #102d50, #477da7);"

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            {background_rule}
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stMain"] {{ background: transparent; }}
        [data-testid="stMainBlockContainer"] {{
            max-width: 100%;
            padding-top: 5vh;
            padding-bottom: 5vh;
        }}
        /* The keyed Streamlit container is the ONLY login card. */
        .st-key-login-card {{
            max-width: 510px;
            margin: 0 auto;
            padding: 26px 34px 24px 34px;
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(255,255,255,.75);
            border-radius: 22px;
            box-shadow: 0 18px 55px rgba(7, 25, 48, .24);
            backdrop-filter: blur(8px);
        }}
        .st-key-login-card h1,
        .st-key-login-card h2,
        .st-key-login-card h3,
        .st-key-login-card p,
        .st-key-login-card label,
        .st-key-login-card [data-testid="stMarkdownContainer"] {{
            color: #15365d;
        }}
        .st-key-login-card .aerobook-brand {{
            text-align: center;
            color: #12365f;
            font-size: 39px;
            line-height: 1.15;
            font-weight: 800;
            letter-spacing: -1.2px;
            margin: 0 0 8px 0;
        }}
        .st-key-login-card .aerobook-tagline {{
            text-align: center;
            color: #536b86;
            font-size: 14px;
            margin: 0 0 22px 0;
        }}
        .st-key-login-card .aerobook-welcome {{
            text-align: center;
            color: #102f54;
            font-size: 28px;
            font-weight: 800;
            margin: 0 0 2px 0;
        }}
        .st-key-login-card .aerobook-subtitle {{
            text-align: center;
            color: #5b6f87;
            font-size: 16px;
            margin: 0 0 18px 0;
        }}
        .st-key-login-card [data-testid="stRadio"] label,
        .st-key-login-card [data-testid="stTextInput"] label {{
            color: #183b62 !important;
            text-shadow: none !important;
        }}
        .st-key-login-card [data-testid="stTextInput"] input {{
            min-height: 46px;
            background: #fff;
            color: #183b62;
            border: 1px solid #d4dce6;
            border-radius: 10px;
        }}
        .st-key-login-card [data-testid="stForm"] {{
            background: transparent;
            border: 0;
            padding: 0;
        }}
        .st-key-login-card [data-testid="stFormSubmitButton"] button {{
            min-height: 46px;
            color: white;
            background: #103b6b;
            border: 1px solid #103b6b;
            border-radius: 10px;
            font-weight: 700;
        }}
        .st-key-login-card [data-testid="stFormSubmitButton"] button:hover {{
            background: #174d83;
            border-color: #174d83;
        }}
        .st-key-login-card [data-testid="stExpander"] {{
            background: rgba(255,255,255,.55);
            border: 1px solid #d5deea;
            border-radius: 12px;
        }}
        .st-key-login-card [data-testid="stExpander"] summary,
        .st-key-login-card [data-testid="stExpander"] label {{
            color: #183b62 !important;
            text-shadow: none !important;
        }}
        .st-key-login-card [data-testid="stCaptionContainer"] {{ text-align: center; }}
        @media (max-width: 640px) {{
            .st-key-login-card {{ margin: 0 8px; padding: 22px 20px; }}
            .st-key-login-card .aerobook-brand {{ font-size: 32px; }}
        }}

        /* Make Login button text clearly visible */
.stFormSubmitButton > button,
.stFormSubmitButton > button p {{
    color: #FFFFFF !important;
    background-color: #123D68 !important;
    font-weight: 700 !important;
    opacity: 1 !important;
    border: none !important;
}}

/* Login button hover */
.stFormSubmitButton > button:hover,
.stFormSubmitButton > button:hover p {{
    color: #FFFFFF !important;
    background-color: #0B2D50 !important;
}}

/* Keep text visible when focused */
.stFormSubmitButton > button:focus,
.stFormSubmitButton > button:focus p {{
    color: #FFFFFF !important;
}}
        </style>
        """,
        unsafe_allow_html=True,
    )

    _left, _center, _right = st.columns([1, 1.15, 1])
    with _center:
        with st.container(key="login-card"):
            st.markdown(
                '<div class="aerobook-brand">✈ AeroBook</div>'
                '<div class="aerobook-tagline">Flights&nbsp; · &nbsp;Onboard Food&nbsp; · &nbsp;Entertainment&nbsp; · &nbsp;Rewards</div>'
                '<div class="aerobook-welcome">Welcome Back</div>'
                '<div class="aerobook-subtitle">Log in to your AeroBook account</div>',
                unsafe_allow_html=True,
            )

            account_type = st.radio(
                "I am logging in as", ["Passenger", "Staff"], horizontal=True,
                key="aerobook_login_type",
            )

            with st.form("aerobook_login_form"):
                login_id = st.text_input(
                    "Email address" if account_type == "Staff" else "Email address or username",
                    placeholder="Enter your email address or username",
                )
                login_password = st.text_input(
                    "Password", type="password", placeholder="Enter your password"
                )
                submitted = st.form_submit_button("Login  →", use_container_width=True)

            if submitted:
                if not login_id.strip() or not login_password:
                    st.warning("Please enter your login ID and password.")
                else:
                    try:
                        user, error_message = authenticate(account_type, login_id.strip(), login_password)
                        if user:
                            st.session_state.aerobook_user = user
                            st.rerun()
                        else:
                            st.error(error_message)
                    except Exception as error:
                        st.error("Could not connect to the AeroBook database.")
                        st.code(str(error))

            if account_type == "Passenger":
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:12px;margin:18px 0 10px;color:#183b62;">'
                    '<span style="height:1px;background:#d9e0e8;flex:1"></span>'
                    '<strong style="white-space:nowrap;font-size:14px">New to AeroBook?</strong>'
                    '<span style="height:1px;background:#d9e0e8;flex:1"></span></div>',
                    unsafe_allow_html=True,
                )
                with st.expander("Create a Passenger Account", expanded=False):
                    with st.form("aerobook_registration_form"):
                        reg_username = st.text_input("Choose a username")
                        reg_email = st.text_input("Email address")
                        reg_phone = st.text_input("Phone number (optional)")
                        reg_password = st.text_input("Create password", type="password")
                        reg_confirm = st.text_input("Confirm password", type="password")
                        register = st.form_submit_button("Create Passenger Account", use_container_width=True)
                    if register:
                        if not reg_username.strip() or not reg_email.strip() or not reg_password:
                            st.warning("Username, email and password are required.")
                        elif reg_password != reg_confirm:
                            st.error("The passwords do not match.")
                        elif len(reg_password) < 8:
                            st.error("Use a password with at least 8 characters.")
                        else:
                            try:
                                created, message = create_passenger_account(
                                    reg_username.strip(), reg_email.strip(), reg_phone.strip(), reg_password
                                )
                                st.success(message) if created else st.error(message)
                            except Exception as error:
                                st.error("Could not create the account.")
                                st.code(str(error))

            st.caption("A smoother journey starts here · AeroBook")

    st.stop()




st.title("AeroBook")
st.caption("Find your flight and explore the onboard experience.")



# =====================================================
# PROFESSIONAL PASSENGER DASHBOARD
# =====================================================
current_user = st.session_state.get("aerobook_user")

if current_user is None:
    st.session_state.clear()
    st.rerun()
    
if current_user["type"] == "Passenger":

    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] {
        background: #f4f7fb;
    }

    [data-testid="stMain"] {
        background: #f4f7fb;
    }

    .dashboard-welcome {
        background: linear-gradient(120deg, #102f55, #23639a);
        padding: 32px;
        border-radius: 18px;
        color: white;
        margin-bottom: 25px;
    }

    .dashboard-welcome h1 {
        color: white;
        font-size: 32px;
        margin-bottom: 8px;
    }

    .dashboard-welcome p {
        color: #e2edf8;
        font-size: 16px;
        margin-bottom: 0;
    }

    .stat-card {
        background: white;
        border: 1px solid #e4eaf2;
        border-radius: 16px;
        padding: 23px;
        min-height: 125px;
        box-shadow: 0 3px 12px rgba(20, 50, 80, 0.05);
    }

    .stat-label {
        color: #64748b;
        font-size: 14px;
        margin-bottom: 12px;
    }

    .stat-value {
        color: #12365f;
        font-size: 30px;
        font-weight: 800;
    }

    .section-heading {
        color: #12365f;
        font-size: 23px;
        font-weight: 750;
        margin-top: 30px;
        margin-bottom: 15px;
    }

    
    </style>
    """, unsafe_allow_html=True)

    try:
        dashboard = get_passenger_dashboard(current_user["id"])

        # Welcome banner
        st.markdown(f"""
        <div class="dashboard-welcome">
            <h1>Welcome back, {current_user["name"]} ✈</h1>
            <p>Your next journey starts here. Explore flights,
            manage bookings and enjoy your AeroBook benefits.</p>
        </div>
        """, unsafe_allow_html=True)

        # Travel statistics
        st.markdown(
            '<div class="section-heading">Your Travel Overview</div>',
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">✈ Total Bookings</div>
                <div class="stat-value">{dashboard["total_bookings"]}</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">🧳 Upcoming Trips</div>
                <div class="stat-value">{dashboard["upcoming_trips"]}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">★ Available Points</div>
                <div class="stat-value">{dashboard["points"]}</div>
            </div>
            """, unsafe_allow_html=True)

        # Quick actions
        st.markdown(
            '<div class="section-heading">Explore AeroBook</div>',
            unsafe_allow_html=True
        )

        def go_to_page(page_name):
             st.session_state.page_navigation = page_name

        action1, action2, action3 = st.columns(3)

        with action1:
             st.button(
        "✈ Search Flights",
        use_container_width=True,
        on_click=go_to_page,
        args=("Book a Flight",)
    )
        with action2:
            st.button(
        "🍽 Explore Food",
        use_container_width=True,
        on_click=go_to_page,
        args=("Food Menu",)
    )

        with action3:
            st.button(
        "★ View Rewards",
        use_container_width=True,
        on_click=go_to_page,
        args=("Rewards",)
    )

        # Recent bookings
        st.markdown(
            '<div class="section-heading">Recent Bookings</div>',
            unsafe_allow_html=True
        )

        if dashboard["recent_bookings"]:
            st.dataframe(
                dashboard["recent_bookings"],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info(
                "You haven't made any bookings yet. "
                "Search for a flight to plan your first journey!"
            )

    except Exception as error:
        st.error("Unable to load your passenger dashboard.")
        st.code(str(error))

    st.divider()


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def format_time(value):
    """Convert MySQL TIME values (including timedelta) into AM/PM format."""

    if value is None:
        return "Not available"

    if isinstance(value, datetime):
        return value.strftime("%I:%M %p")

    if isinstance(value, time):
        return value.strftime("%I:%M %p")

    # mysql-connector-python may return a MySQL TIME column as timedelta.
    if hasattr(value, "total_seconds"):
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        return datetime.strptime(
            f"{hours:02d}:{minutes:02d}", "%H:%M"
        ).strftime("%I:%M %p")

    try:
        return datetime.strptime(
            str(value), "%H:%M:%S"
        ).strftime("%I:%M %p")
    except ValueError:
        try:
            return datetime.strptime(
                str(value), "%H:%M"
            ).strftime("%I:%M %p")
        except ValueError:
            return str(value)


def format_datetime(value):
    """Format arrival datetime into a readable date and time."""

    if value is None:
        return "Not available"

    if isinstance(value, datetime):
        return value.strftime("%d %b %Y, %I:%M %p")

    try:
        return datetime.strptime(
            str(value), "%Y-%m-%d %H:%M:%S"
        ).strftime("%d %b %Y, %I:%M %p")
    except ValueError:
        return str(value)


def format_date(value):
    if isinstance(value, (datetime, date)):
        return value.strftime("%d %b %Y")
    return str(value)


def yes_no(value):
    if str(value).strip().lower() in ("yes", "1", "true"):
        return "Yes"
    return "No"



def get_passenger_bookings(user_id):
    """Retrieve bookings for the logged-in passenger."""

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                b.booking_id,
                f.flight_number,
                b.schedule_date,
                b.departure_time,
                b.booking_date,
                b.booking_status,
                b.payment_status,
                b.total_fare
            FROM booking b
            LEFT JOIN flight f
                ON b.flight_id = f.flight_id
            WHERE b.user_id = %s
            ORDER BY b.booking_date DESC
            """,
            (user_id,)
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()



# =====================================================
# SESSION STATE INITIALIZATION
# =====================================================

if "flight_results" not in st.session_state:
    st.session_state.flight_results = []

if "selected_menu" not in st.session_state:
    st.session_state.selected_menu = None

if "source_airport_id" not in st.session_state:
    st.session_state.source_airport_id = None

if "destination_airport_id" not in st.session_state:
    st.session_state.destination_airport_id = None

if "travel_date" not in st.session_state:
    st.session_state.travel_date = date.today()


# =====================================================
# MAIN TABS
# =====================================================

with st.sidebar:

    # Navigation at the top
    st.markdown("# ✈ AeroBook")
    st.caption("YOUR TRAVEL COMPANION")
    st.divider()

    st.markdown("### NAVIGATION")

    

    if current_user["type"] == "Passenger":
        navigation_options = [
            "Dashboard",
            "Book a Flight",
            "My Bookings",
            "Food Menu",
            "Rewards",
            "Entertainment"
        ]

    elif str(current_user["role"]).lower() == "admin":
        navigation_options = [
            "Staff Dashboard",
            "Employee Flight Schedules",
            "Assign Staff to Flights",
            "Flight Schedules",
            "Bookings",
            "Passenger Details",
            "Flight Management",
            "Booking Management"
        ]

    else:
        navigation_options = [
            "Staff Dashboard",
            "Flight Schedules",
            "Bookings",
            "Passenger Details"
        ]

    # Reset navigation if the account type or role changes.
    if st.session_state.get("page_navigation") not in navigation_options:
        st.session_state.page_navigation = navigation_options[0]

    page = st.radio(
        "Select a page",
        navigation_options,
        label_visibility="collapsed",
        key="page_navigation"
    )
    # Push account section below navigation
    st.markdown('<div style="height: 100px;"></div>',
                unsafe_allow_html=True)

    st.divider()

    # Account details - only one copy
with st.sidebar:
    with st.container():
        st.markdown("### AeroBook Account")
        st.write(f'**{current_user["name"]}**')
        st.caption(f'{current_user["type"]} · {current_user["role"]}')
        st.caption(current_user["email"])

        if st.button("Logout", key="sidebar_logout", use_container_width=True):
            st.session_state.aerobook_user = None
            st.rerun()


        st.markdown("""

<style>

/* AeroBook blue sidebar */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    background-color: #12345B !important;
}

/* Sidebar text */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div {
    color: #FFFFFF;
}

/* Account panel pinned to the bottom */
section[data-testid="stSidebar"] .st-key-account_panel {
    position: fixed;
    bottom: 35px;
    left: 1rem;
    width: 250px;
    padding: 15px;
    background-color: #12345B !important;
    border-top: 1px solid rgba(255,255,255,0.3);
    z-index: 999;
}

/* Logout button */
section[data-testid="stSidebar"] .st-key-account_panel button {
    background-color: #FFFFFF !important;
    color: #12345B !important;
    border-radius: 8px;
    font-weight: 600;
}

/* Make Logout button visible */
section[data-testid="stSidebar"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    color: #12345B !important;
    border: 1px solid #FFFFFF !important;
    font-weight: 700 !important;
}

section[data-testid="stSidebar"] button[kind="secondary"] p {
    color: #12345B !important;
}

section[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background-color: #DCEBFA !important;
    color: #12345B !important;
}

/* Keep headings readable */
.stApp h1,
.stApp h2,
.stApp h3 {
    color: #12345B;
}

/* Welcome banner heading */
.welcome-banner h1 {
    color: #FFFFFF !important;
}

/* Form labels */
.stApp label,
.stApp [data-testid="stWidgetLabel"] p {
    color: #12345B !important;
    font-weight: 600 !important;
}

/* Dropdown and date input */
.stApp [data-baseweb="select"] > div,
.stApp [data-testid="stDateInput"] input {
    background-color: #FFFFFF !important;
    color: #12345B !important;
    border: 1px solid #B8CBE0 !important;
    border-radius: 9px !important;
}

/* Search flights button */
.stApp button[kind="primary"] {
    background-color: #12345B !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 9px !important;
    font-weight: 700 !important;
}

.stApp button[kind="primary"]:hover {
    background-color: #1D4D7A !important;
    color: #FFFFFF !important;
}

</style>
""", unsafe_allow_html=True)
        

# =====================================================
# STAFF DASHBOARD
# =====================================================

if page == "Staff Dashboard":

    st.title("Staff Dashboard")
    st.write("Welcome to AeroBook Staff Operations.")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM flight_schedule")
        total_flights = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM booking")
        total_bookings = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM passenger")
        total_passengers = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Flight Schedules", total_flights)
        col2.metric("Total Bookings", total_bookings)
        col3.metric("Total Passengers", total_passengers)

        # Show only the logged-in staff member's own upcoming assignments.
        st.divider()
        st.subheader("My Flight Assignments")

        schedule_conn = get_connection()
        schedule_cursor = schedule_conn.cursor(dictionary=True)
        try:
            schedule_cursor.execute("""
                SELECT
                    f.flight_number AS `Flight`,
                    fs.schedule_date AS `Date`,
                    fs.departure_time AS `Departure`,
                    fs.arrival_datetime AS `Arrival`,
                    src.airport_code AS `From`,
                    src.city AS `Departure City`,
                    dest.airport_code AS `To`,
                    dest.city AS `Arrival City`,
                    ss.duty_role AS `Your Duty`,
                    fs.departure_terminal AS `Departure Terminal`,
                    fs.arrival_terminal AS `Arrival Terminal`,
                    fs.gate_number AS `Gate`,
                    fs.schedule_status AS `Status`
                FROM SCHEDULE_STAFF ss
                JOIN FLIGHT_SCHEDULE fs
                    ON ss.schedule_id = fs.schedule_id
                JOIN FLIGHT f
                    ON fs.flight_id = f.flight_id
                JOIN AIRPORT src
                    ON f.source_airport_id = src.airport_id
                JOIN AIRPORT dest
                    ON f.destination_airport_id = dest.airport_id
                WHERE ss.staff_id = %s
                ORDER BY fs.schedule_date, fs.departure_time
            """, (current_user["id"],))
            my_flights = schedule_cursor.fetchall()
        finally:
            schedule_cursor.close()
            schedule_conn.close()

        if my_flights:
            next_flight = my_flights[0]
            st.markdown("#### Your next flight")
            st.success(
                f'{next_flight["Flight"]}: '
                f'{next_flight["Departure City"]} ({next_flight["From"]}) → '
                f'{next_flight["Arrival City"]} ({next_flight["To"]})'
            )
            # Use two columns with wrapping text so full dates and times remain visible.
            detail_cols = st.columns(2)
            with detail_cols[0]:
                st.caption("Date")
                st.markdown(f"**{format_date(next_flight['Date'])}**")
                st.caption("Departure")
                st.markdown(f"**{format_time(next_flight['Departure'])}**")
            with detail_cols[1]:
                st.caption("Arrival")
                st.markdown(f"**{format_datetime(next_flight['Arrival'])}**")
                st.caption("Your duty")
                st.markdown(f"**{next_flight['Your Duty']}**")

            st.dataframe(
                [
                    {
                        "Flight": row["Flight"],
                        "Date": format_date(row["Date"]),
                        "From": f'{row["Departure City"]} ({row["From"]})',
                        "To": f'{row["Arrival City"]} ({row["To"]})',
                        "Departure": format_time(row["Departure"]),
                        "Arrival": format_datetime(row["Arrival"]),
                        "Duty": row["Your Duty"],
                        "Gate": row["Gate"] or "Not assigned",
                        "Status": row["Status"] or "Not specified"
                    }
                    for row in my_flights
                ],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("You do not have any flight assignments at the moment.")

        st.divider()
        st.subheader("Staff Quick Access")
        st.write("Use the sidebar to view flight schedules, bookings and passenger details.")

    except Exception as e:
        st.error(f"Unable to load dashboard data: {e}")


# =====================================================
# ADMIN: ALL EMPLOYEE FLIGHT SCHEDULES
# =====================================================

if page == "Employee Flight Schedules":
    st.title("Employee Flight Schedules")

    if str(current_user.get("role", "")).lower() != "admin":
        st.error("Access denied. Admin permission required.")
    else:
        st.write("View flight assignments for every AeroBook employee.")
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT
                    st.staff_id AS `Employee ID`,
                    CONCAT(st.first_name, ' ', st.last_name) AS `Employee Name`,
                    st.designation AS `Designation`,
                    f.flight_number AS `Flight Number`,
                    src.city AS `From`,
                    src.airport_code AS `From Code`,
                    dest.city AS `To`,
                    dest.airport_code AS `To Code`,
                    fs.schedule_date AS `Travel Date`,
                    fs.departure_time AS `Departure Time`,
                    fs.arrival_datetime AS `Arrival`,
                    ss.duty_role AS `Duty Role`,
                    fs.departure_terminal AS `Departure Terminal`,
                    fs.arrival_terminal AS `Arrival Terminal`,
                    fs.gate_number AS `Gate`,
                    fs.schedule_status AS `Status`
                FROM SCHEDULE_STAFF ss
                JOIN STAFF st ON st.staff_id = ss.staff_id
                JOIN FLIGHT_SCHEDULE fs ON fs.schedule_id = ss.schedule_id
                JOIN FLIGHT f ON f.flight_id = fs.flight_id
                JOIN AIRPORT src ON src.airport_id = f.source_airport_id
                JOIN AIRPORT dest ON dest.airport_id = f.destination_airport_id
                ORDER BY fs.schedule_date DESC, fs.departure_time,
                         st.first_name, st.last_name
            """)
            employee_rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if employee_rows:
                employee_names = sorted({r["Employee Name"] for r in employee_rows})
                flight_numbers = sorted({r["Flight Number"] for r in employee_rows})
                duty_roles = sorted({r["Duty Role"] for r in employee_rows if r["Duty Role"]})
                c1, c2, c3 = st.columns(3)
                employee_filter = c1.selectbox("Filter by employee", ["All"] + employee_names)
                flight_filter = c2.selectbox("Filter by flight", ["All"] + flight_numbers)
                duty_filter = c3.selectbox("Filter by duty role", ["All"] + duty_roles)
                use_date_filter = st.checkbox("Filter by a specific travel date")
                date_filter = st.date_input("Travel date", value=date.today()) if use_date_filter else None

                filtered_rows = employee_rows
                if employee_filter != "All":
                    filtered_rows = [r for r in filtered_rows if r["Employee Name"] == employee_filter]
                if flight_filter != "All":
                    filtered_rows = [r for r in filtered_rows if r["Flight Number"] == flight_filter]
                if duty_filter != "All":
                    filtered_rows = [r for r in filtered_rows if r["Duty Role"] == duty_filter]
                if date_filter:
                    filtered_rows = [r for r in filtered_rows if r["Travel Date"] == date_filter]

                st.caption(f"Showing {len(filtered_rows)} assignment(s) out of {len(employee_rows)} total.")

                # Format MySQL TIME values before passing rows to Streamlit.
                display_rows = [
                    {
                        **row,
                        "Departure Time": format_time(row["Departure Time"]),
                        "Arrival": format_datetime(row["Arrival"]),
                    }
                    for row in filtered_rows
                ]
                st.dataframe(display_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No employee flight assignments were found.")
        except Exception as e:
            st.error(f"Unable to load employee schedules: {e}")


# =====================================================
# ADMIN: ASSIGN STAFF TO FLIGHT SCHEDULES
# =====================================================

if page == "Assign Staff to Flights":
    st.title("Assign Staff to Flights")

    if str(current_user.get("role", "")).lower() != "admin":
        st.error("Access denied. Admin permission required.")
    else:
        st.write("Assign an employee to an existing flight schedule. Create a new flight schedule first under Flight Management.")
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT fs.schedule_id, f.flight_number, fs.schedule_date,
                       fs.departure_time, src.city AS source_city,
                       dest.city AS destination_city, fs.schedule_status
                FROM FLIGHT_SCHEDULE fs
                JOIN FLIGHT f ON f.flight_id = fs.flight_id
                JOIN AIRPORT src ON src.airport_id = f.source_airport_id
                JOIN AIRPORT dest ON dest.airport_id = f.destination_airport_id
                ORDER BY fs.schedule_date DESC, fs.departure_time
            """)
            schedule_rows = cursor.fetchall()
            cursor.execute("""
                SELECT staff_id, first_name, last_name, designation,
                       staff_role, staff_status
                FROM STAFF
                WHERE LOWER(COALESCE(staff_status, 'active')) NOT IN ('inactive', 'terminated')
                ORDER BY first_name, last_name
            """)
            staff_rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if not schedule_rows:
                st.info("No flight schedules exist yet. Create one under Flight Management first.")
            elif not staff_rows:
                st.info("No active employees are available to assign.")
            else:
                schedule_labels = {
                    row["schedule_id"]: (
                        f'{row["flight_number"]} | {row["schedule_date"]} '
                        f'{format_time(row["departure_time"])} | {row["source_city"]} → '
                        f'{row["destination_city"]} | {row["schedule_status"]}'
                    ) for row in schedule_rows
                }
                staff_labels = {
                    row["staff_id"]: (
                        f'{row["first_name"]} {row["last_name"]} '
                        f'(ID {row["staff_id"]} · {row["designation"] or row["staff_role"]})'
                    ) for row in staff_rows
                }

                with st.form("admin_assign_staff_form"):
                    chosen_schedule_id = st.selectbox(
                        "Select flight schedule", list(schedule_labels),
                        format_func=lambda x: schedule_labels[x]
                    )
                    chosen_staff_id = st.selectbox(
                        "Select employee", list(staff_labels),
                        format_func=lambda x: staff_labels[x]
                    )
                    chosen_duty_role = st.selectbox(
                        "Duty role", ["Captain", "First Officer", "Cabin Crew", "Other"]
                    )
                    assign_staff = st.form_submit_button("Assign Employee", type="primary")

                if assign_staff:
                    assign_conn = get_connection()
                    assign_cursor = assign_conn.cursor()
                    try:
                        assign_cursor.execute("""
                            SELECT 1 FROM SCHEDULE_STAFF
                            WHERE schedule_id = %s AND staff_id = %s
                        """, (chosen_schedule_id, chosen_staff_id))
                        if assign_cursor.fetchone():
                            st.warning("This employee is already assigned to that flight schedule.")
                        else:
                            assign_cursor.execute("""
                                INSERT INTO SCHEDULE_STAFF (schedule_id, staff_id, duty_role)
                                VALUES (%s, %s, %s)
                            """, (chosen_schedule_id, chosen_staff_id, chosen_duty_role))
                            assign_conn.commit()
                            st.success(f"{staff_labels[chosen_staff_id]} assigned successfully.")
                            st.rerun()
                    except Exception as e:
                        assign_conn.rollback()
                        st.error(f"Unable to assign employee: {e}")
                    finally:
                        assign_cursor.close()
                        assign_conn.close()

                st.divider()
                st.subheader("Current crew for selected schedule")
                view_schedule_id = st.selectbox(
                    "Choose a schedule to view its assigned crew",
                    list(schedule_labels),
                    format_func=lambda x: schedule_labels[x],
                    key="view_crew_schedule_id"
                )
                view_conn = get_connection()
                view_cursor = view_conn.cursor(dictionary=True)
                try:
                    view_cursor.execute("""
                        SELECT st.staff_id AS `Employee ID`,
                               CONCAT(st.first_name, ' ', st.last_name) AS `Employee Name`,
                               st.designation AS `Designation`,
                               ss.duty_role AS `Duty Role`
                        FROM SCHEDULE_STAFF ss
                        JOIN STAFF st ON st.staff_id = ss.staff_id
                        WHERE ss.schedule_id = %s
                        ORDER BY ss.duty_role, st.first_name
                    """, (view_schedule_id,))
                    assigned_rows = view_cursor.fetchall()
                    if assigned_rows:
                        st.dataframe(assigned_rows, use_container_width=True, hide_index=True)
                    else:
                        st.info("No employees are assigned to this schedule yet.")
                finally:
                    view_cursor.close()
                    view_conn.close()
        except Exception as e:
            st.error(f"Unable to load staff assignment tools: {e}")


# =====================================================
# STAFF FLIGHT SCHEDULES
# =====================================================

if page == "Flight Schedules":

    st.title("Flight Schedules")
    st.write("View all scheduled AeroBook flights.")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                f.flight_number AS `Flight Number`,
                src.city AS `From`,
                dest.city AS `To`,
                fs.schedule_date AS `Travel Date`,
                fs.departure_time AS `Departure Time`,
                fs.arrival_datetime AS `Arrival`,
                fs.departure_terminal AS `Departure Terminal`,
                fs.arrival_terminal AS `Arrival Terminal`,
                fs.gate_number AS `Gate`,
                fs.schedule_status AS `Status`
            FROM FLIGHT_SCHEDULE fs
            JOIN FLIGHT f
                ON fs.flight_id = f.flight_id
            JOIN AIRPORT src
                ON f.source_airport_id = src.airport_id
            JOIN AIRPORT dest
                ON f.destination_airport_id = dest.airport_id
            ORDER BY fs.schedule_date DESC, fs.departure_time
        """)

        schedules = cursor.fetchall()

        cursor.close()
        conn.close()

        if schedules:
            st.success(f"{len(schedules)} flight schedules found.")

            search = st.text_input(
                "Search by flight number or city"
            )

            if search:
                schedules = [
                    row for row in schedules
                    if search.lower() in str(row).lower()
                ]

            st.dataframe(
                schedules,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No flight schedules found.")

    except Exception as e:
        st.error(f"Unable to load flight schedules: {e}")


# =====================================================
# STAFF BOOKINGS
# =====================================================

if page == "Bookings":

    st.title("Booking Management")
    st.write("View passenger booking records.")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                b.booking_id AS `Booking ID`,
                GROUP_CONCAT(
                    DISTINCT CONCAT(p.first_name, ' ', p.last_name)
                    SEPARATOR ', '
                ) AS `Passenger Name`,
                f.flight_number AS `Flight Number`,
                b.schedule_date AS `Travel Date`,
                b.departure_time AS `Departure Time`,
                b.booking_status AS `Booking Status`,
                b.payment_status AS `Payment Status`,
                b.total_fare AS `Total Fare`
            FROM booking b
            LEFT JOIN flight f
                ON b.flight_id = f.flight_id
            LEFT JOIN booking_passenger bp
                ON b.booking_id = bp.booking_id
            LEFT JOIN passenger p
                ON bp.passenger_id = p.passenger_id
            GROUP BY
                b.booking_id,
                f.flight_number,
                b.schedule_date,
                b.departure_time,
                b.booking_status,
                b.payment_status,
                b.total_fare
            ORDER BY b.booking_date DESC
        """)

        bookings = cursor.fetchall()

        cursor.close()
        conn.close()

        if bookings:
            st.success(f"{len(bookings)} bookings found.")

            search = st.text_input(
                "Search by booking ID, passenger or flight number"
            )

            if search:
                bookings = [
                    row for row in bookings
                    if search.lower() in str(row).lower()
                ]

            st.dataframe(
                bookings,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No bookings found.")

    except Exception as e:
        st.error(f"Unable to load bookings: {e}")

# =====================================================
# STAFF PASSENGER DETAILS
# =====================================================

if page == "Passenger Details":

    st.title("Passenger Details")
    st.write("View registered passenger information.")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                p.passenger_id AS `Passenger ID`,
                p.first_name AS `First Name`,
                p.last_name AS `Last Name`,
                p.email AS `Email`,
                p.phone_number AS `Phone Number`,
                p.nationality AS `Nationality`,
                COUNT(DISTINCT b.booking_id) AS `Total Bookings`
            FROM passenger p
            LEFT JOIN booking b
                ON p.user_id = b.user_id
            GROUP BY
                p.passenger_id,
                p.first_name,
                p.last_name,
                p.email,
                p.phone_number,
                p.nationality
            ORDER BY p.passenger_id
        """)

        passengers = cursor.fetchall()

        cursor.close()
        conn.close()

        if passengers:
            st.success(f"{len(passengers)} passenger records found.")

            search = st.text_input(
                "Search by passenger name, ID or email"
            )

            if search:
                passengers = [
                    row for row in passengers
                    if search.lower() in str(row).lower()
                ]

            st.dataframe(
                passengers,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No passenger records found.")

    except Exception as e:
        st.error(f"Unable to load passenger details: {e}")

# =====================================================
# ADMIN: FLIGHT MANAGEMENT
# =====================================================

if page == "Flight Management":

    st.title("Flight Management")
    
    if str(current_user.get("role", "")).lower() != "admin":
        st.error("Access denied. Admin permission required.")

    else:
        st.write("Add flights, create schedules and manage flight status.")

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT airport_id, airport_code, city
                FROM airport
                ORDER BY city
            """)
            airports = cursor.fetchall()

            cursor.execute("""
                SELECT aircraft_id, aircraft_model, registration_no
                FROM aircraft
                ORDER BY aircraft_model
            """)
            aircraft_list = cursor.fetchall()

            cursor.execute("""
                SELECT flight_id, flight_number, flight_type, base_fare
                FROM flight
                ORDER BY flight_number
            """)
            flights = cursor.fetchall()

            cursor.execute("""
                SELECT
                    fs.schedule_id,
                    f.flight_number,
                    fs.schedule_date,
                    fs.departure_time,
                    fs.schedule_status
                FROM flight_schedule fs
                JOIN flight f ON fs.flight_id = f.flight_id
                ORDER BY fs.schedule_date DESC
            """)
            schedules = cursor.fetchall()

            cursor.close()
            conn.close()

            airport_labels = {
                a["airport_id"]:
                f'{a["city"]} ({a["airport_code"]})'
                for a in airports
            }

            aircraft_labels = {
                a["aircraft_id"]:
                f'{a["aircraft_model"]} - {a["registration_no"]}'
                for a in aircraft_list
            }

            # ADD A FLIGHT
            st.subheader("Add New Flight")

            if not airports or not aircraft_list:
                st.warning("Add airports and aircraft before creating flights.")

            else:
                with st.form("add_flight_form"):

                    flight_number = st.text_input("Flight Number")
                    flight_type = st.text_input("Flight Type")

                    source_id = st.selectbox(
                        "Source Airport",
                        list(airport_labels.keys()),
                        format_func=lambda x: airport_labels[x]
                    )

                    destination_options = [
                        x for x in airport_labels if x != source_id
                    ]

                    destination_id = st.selectbox(
                        "Destination Airport",
                        destination_options,
                        format_func=lambda x: airport_labels[x]
                    )

                    aircraft_id = st.selectbox(
                        "Aircraft",
                        list(aircraft_labels.keys()),
                        format_func=lambda x: aircraft_labels[x]
                    )

                    base_fare = st.number_input(
                        "Base Fare", min_value=0.0, step=100.0
                    )

                    baggage = st.number_input(
                        "Baggage Allowance (kg)", min_value=0.0, step=1.0
                    )

                    add_flight = st.form_submit_button("Add Flight")

                if add_flight:

                    if not flight_number.strip():
                        st.error("Enter a flight number.")

                    elif source_id == destination_id:
                        st.error("Source and destination must be different.")

                    else:
                        conn = get_connection()
                        cursor = conn.cursor()

                        try:
                            cursor.execute("""
                                INSERT INTO flight (
                                    flight_number,
                                    flight_type,
                                    source_airport_id,
                                    destination_airport_id,
                                    aircraft_id,
                                    base_fare,
                                    baggage_allowance
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                flight_number.strip(),
                                flight_type or None,
                                source_id,
                                destination_id,
                                aircraft_id,
                                base_fare,
                                baggage
                            ))

                            conn.commit()
                            st.success("Flight added successfully!")
                            st.rerun()

                        except Exception:
                            conn.rollback()
                            raise

                        finally:
                            cursor.close()
                            conn.close()

            st.divider()

            # CREATE FLIGHT SCHEDULE
            st.subheader("Create Flight Schedule")

            if flights:
                flight_options = {
                    f["flight_id"]: f["flight_number"]
                    for f in flights
                }

                with st.form("add_schedule_form"):

                    selected_flight = st.selectbox(
                        "Select Flight",
                        list(flight_options.keys()),
                        format_func=lambda x: flight_options[x]
                    )

                    schedule_date = st.date_input("Travel Date")
                    departure_time = st.time_input("Departure Time")
                    arrival_datetime = st.datetime_input("Arrival Date and Time")

                    departure_terminal = st.text_input("Departure Terminal")
                    arrival_terminal = st.text_input("Arrival Terminal")
                    gate_number = st.text_input("Gate Number")

                    add_schedule = st.form_submit_button("Create Schedule")

                if add_schedule:

                    if arrival_datetime.date() < schedule_date:
                        st.error("Arrival cannot be before the travel date.")

                    elif (
                        arrival_datetime.date() == schedule_date
                        and arrival_datetime.time() <= departure_time
                    ):
                        st.error("Arrival must be after departure.")

                    else:
                        conn = get_connection()
                        cursor = conn.cursor()

                        try:
                            cursor.execute("""
                                INSERT INTO flight_schedule (
                                    flight_id,
                                    schedule_date,
                                    departure_time,
                                    arrival_datetime,
                                    departure_terminal,
                                    arrival_terminal,
                                    gate_number,
                                    schedule_status
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Scheduled')
                            """, (
                                selected_flight,
                                schedule_date,
                                departure_time,
                                arrival_datetime,
                                departure_terminal or None,
                                arrival_terminal or None,
                                gate_number or None
                            ))

                            conn.commit()
                            st.success("Flight schedule created!")
                            st.rerun()

                        except Exception:
                            conn.rollback()
                            raise

                        finally:
                            cursor.close()
                            conn.close()

            else:
                st.info("Add a flight before creating its schedule.")

            st.divider()

            # UPDATE FLIGHT STATUS
            st.subheader("Update Flight Status")

            if schedules:
                schedule_options = {
                    s["schedule_id"]:
                    f'{s["flight_number"]} | {s["schedule_date"]} | {s["schedule_status"]}'
                    for s in schedules
                }

                with st.form("update_status_form"):

                    selected_schedule = st.selectbox(
                        "Select Flight Schedule",
                        list(schedule_options.keys()),
                        format_func=lambda x: schedule_options[x]
                    )

                    new_status = st.selectbox(
                        "New Status",
                        ["Scheduled", "Delayed", "Cancelled", "Completed"]
                    )

                    update_status = st.form_submit_button("Update Status")

                if update_status:
                    conn = get_connection()
                    cursor = conn.cursor()

                    try:
                        cursor.execute("""
                            UPDATE flight_schedule
                            SET schedule_status = %s
                            WHERE schedule_id = %s
                        """, (new_status, selected_schedule))

                        conn.commit()
                        st.success("Flight status updated!")
                        st.rerun()

                    except Exception:
                        conn.rollback()
                        raise

                    finally:
                        cursor.close()
                        conn.close()

            else:
                st.info("No flight schedules are available yet.")

            st.divider()

            # EDIT FLIGHT DETAILS
           
            # EDIT FLIGHT DETAILS
            st.subheader("Edit Flight Details")

            if flights:

                edit_flight_id = st.selectbox(
                    "Select Flight to Edit",
                    [f["flight_id"] for f in flights],
                    format_func=lambda x: next(
                        f["flight_number"] for f in flights
                        if f["flight_id"] == x
                    ),
                    key="edit_flight_id"
                )

                selected_flight_data = next(
                    f for f in flights
                    if f["flight_id"] == edit_flight_id
                )

                with st.form("edit_flight_form"):

                    new_flight_type = st.text_input(
                        "Flight Type",
                        value=selected_flight_data["flight_type"] or ""
                    )

                    new_base_fare = st.number_input(
                        "Base Fare",
                        min_value=0.0,
                        value=float(selected_flight_data["base_fare"]),
                        step=100.0
                    )

                    edit_flight = st.form_submit_button(
                        "Save Flight Changes"
                    )

                if edit_flight:

                    conn = get_connection()
                    cursor = conn.cursor()

                    try:
                        cursor.execute("""
                            UPDATE flight
                            SET flight_type = %s,
                                base_fare = %s
                            WHERE flight_id = %s
                        """, (
                            new_flight_type or None,
                            new_base_fare,
                            edit_flight_id
                        ))

                        conn.commit()
                        st.success("Flight details updated!")
                        st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Unable to update flight: {e}")

                    finally:
                        cursor.close()
                        conn.close()


        except Exception as e:
            st.error(f"Flight Management error: {e}")

# =====================================================
# ADMIN: BOOKING MANAGEMENT
# =====================================================

if page == "Booking Management":

    st.title("Booking Management")

    if str(current_user.get("role", "")).lower() != "admin":
        st.error("Access denied. Admin permission required.")

    else:
        st.write("View, update and cancel passenger bookings.")

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT
                    b.booking_id,
                    b.user_id,
                    GROUP_CONCAT(
                        DISTINCT CONCAT(p.first_name, ' ', p.last_name)
                        SEPARATOR ', '
                    ) AS passenger_names,
                    f.flight_number,
                    b.schedule_date,
                    b.departure_time,
                    b.booking_status,
                    b.payment_status,
                    b.total_fare
                FROM booking b
                LEFT JOIN flight f
                    ON b.flight_id = f.flight_id
                LEFT JOIN booking_passenger bp
                    ON b.booking_id = bp.booking_id
                LEFT JOIN passenger p
                    ON bp.passenger_id = p.passenger_id
                GROUP BY
                    b.booking_id,
                    b.user_id,
                    f.flight_number,
                    b.schedule_date,
                    b.departure_time,
                    b.booking_status,
                    b.payment_status,
                    b.total_fare
                ORDER BY b.booking_date DESC
            """)

            bookings = cursor.fetchall()

            cursor.close()
            conn.close()

            st.subheader("All Bookings")

            if bookings:

                st.success(f"{len(bookings)} bookings found.")

                search = st.text_input(
                    "Search by booking ID, passenger or flight number",
                    key="admin_booking_search"
                )

                filtered_bookings = bookings

                if search:
                    filtered_bookings = [
                        b for b in bookings
                        if search.lower() in str(b).lower()
                    ]

                display_bookings = [
                    {
                        "Booking ID": b["booking_id"],
                        "Passenger": b["passenger_names"],
                        "Flight": b["flight_number"],
                        "Travel Date": b["schedule_date"],
                        "Departure": b["departure_time"],
                        "Booking Status": b["booking_status"],
                        "Payment Status": b["payment_status"],
                        "Total Fare": b["total_fare"]
                    }
                    for b in filtered_bookings
                ]

                st.dataframe(
                    display_bookings,
                    use_container_width=True,
                    hide_index=True
                )

                st.divider()

                # UPDATE BOOKING
                st.subheader("Update Booking")

                booking_options = {
                    b["booking_id"]: b
                    for b in bookings
                }

                selected_booking_id = st.selectbox(
                    "Select Booking",
                    list(booking_options.keys()),
                    format_func=lambda x: (
                        f'Booking #{x} - '
                        f'{booking_options[x]["flight_number"]}'
                    ),
                    key="admin_edit_booking"
                )

                selected_booking = booking_options[selected_booking_id]

                with st.form("admin_update_booking_form"):

                    new_booking_status = st.selectbox(
                        "Booking Status",
                        ["Confirmed", "Pending", "Cancelled"],
                        index=(
                            ["Confirmed", "Pending", "Cancelled"].index(
                                selected_booking["booking_status"]
                            )
                            if selected_booking["booking_status"]
                            in ["Confirmed", "Pending", "Cancelled"]
                            else 0
                        )
                    )

                    new_payment_status = st.selectbox(
                        "Payment Status",
                        ["Pending", "Paid", "Failed", "Refunded"],
                        index=(
                            ["Pending", "Paid", "Failed", "Refunded"].index(
                                selected_booking["payment_status"]
                            )
                            if selected_booking["payment_status"]
                            in ["Pending", "Paid", "Failed", "Refunded"]
                            else 0
                        )
                    )

                    new_total_fare = st.number_input(
                        "Total Fare",
                        min_value=0.0,
                        value=float(selected_booking["total_fare"]),
                        step=100.0
                    )

                    save_booking = st.form_submit_button(
                        "Save Booking Changes"
                    )

                if save_booking:

                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)

                    try:
                        cursor.execute("""
                            SELECT staff_role, staff_status
                            FROM staff
                            WHERE staff_id = %s
                        """, (current_user["id"],))

                        admin_check = cursor.fetchone()

                        if (
                            not admin_check
                            or admin_check["staff_role"].lower() != "admin"
                            or admin_check["staff_status"].lower() != "active"
                        ):
                            raise PermissionError("Admin access could not be verified.")

                        cursor.execute("""
                            UPDATE booking
                            SET booking_status = %s,
                                payment_status = %s,
                                total_fare = %s
                            WHERE booking_id = %s
                        """, (
                            new_booking_status,
                            new_payment_status,
                            new_total_fare,
                            selected_booking_id
                        ))

                        conn.commit()
                        st.success("Booking updated successfully!")
                        st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Unable to update booking: {e}")

                    finally:
                        cursor.close()
                        conn.close()

                st.divider()

                # CANCEL BOOKING
                st.subheader("Cancel Booking")

                cancel_booking_id = st.selectbox(
                    "Select Booking to Cancel",
                    list(booking_options.keys()),
                    format_func=lambda x: (
                        f'Booking #{x} - '
                        f'{booking_options[x]["flight_number"]}'
                    ),
                    key="admin_cancel_booking"
                )

                st.warning(
                    "Cancelling a booking changes its status to Cancelled. "
                    "Passenger and seat records are preserved."
                )

                if st.button(
                    "Cancel Selected Booking",
                    type="secondary"
                ):

                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)

                    try:
                        cursor.execute("""
                            SELECT staff_role, staff_status
                            FROM staff
                            WHERE staff_id = %s
                        """, (current_user["id"],))

                        admin_check = cursor.fetchone()

                        if (
                            not admin_check
                            or admin_check["staff_role"].lower() != "admin"
                            or admin_check["staff_status"].lower() != "active"
                        ):
                            raise PermissionError("Admin access could not be verified.")

                        cursor.execute("""
                            UPDATE booking
                            SET booking_status = 'Cancelled'
                            WHERE booking_id = %s
                        """, (cancel_booking_id,))

                        conn.commit()
                        st.success("Booking cancelled successfully!")
                        st.rerun()

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Unable to cancel booking: {e}")

                    finally:
                        cursor.close()
                        conn.close()

            else:
                st.info("No bookings found.")

        except Exception as e:
            st.error(f"Booking Management error: {e}")

# =====================================================
# TAB 1: FLIGHT SEARCH
# =====================================================

if page=="Book a Flight":
    st.header("Find your flight")

    try:
        airports = get_airports()

        if not airports or len(airports) < 2:

            st.warning(
                "Please add at least two airports to the AIRPORT table."
            )

        else:

            # Map airport IDs to readable labels.
            airport_labels = {
                airport["airport_id"]:
                (
                    f"{airport['city']}, "
                    f"{airport['country']} "
                    f"({airport['airport_code']})"
                )
                for airport in airports
            }

            airport_ids = list(airport_labels.keys())

            # Set default source airport.
            if st.session_state.source_airport_id not in airport_ids:
                st.session_state.source_airport_id = airport_ids[0]

            # Destination must differ from source.
            source_id = st.session_state.source_airport_id

            destination_ids = [
                airport_id
                for airport_id in airport_ids
                if airport_id != source_id
            ]

            # Reset destination if source changes.
            if (
                st.session_state.destination_airport_id
                not in destination_ids
            ):
                st.session_state.destination_airport_id = (
                    destination_ids[0]
                )

            # Airport selection.
            st.selectbox(
                "From",
                options=airport_ids,
                format_func=lambda airport_id: airport_labels[airport_id],
                key="source_airport_id",
            )

            # Recalculate destination choices after source selection.
            source_id = st.session_state.source_airport_id

            destination_ids = [
                airport_id
                for airport_id in airport_ids
                if airport_id != source_id
            ]

            if (
                st.session_state.destination_airport_id
                not in destination_ids
            ):
                st.session_state.destination_airport_id = (
                    destination_ids[0]
                )

            col1, col2 = st.columns(2)

            with col1:
                st.selectbox(
                    "To",
                    options=destination_ids,
                    format_func=lambda airport_id: airport_labels[airport_id],
                    key="destination_airport_id",
                )

            with col2:
                st.date_input(
                    "Travel date",
                    min_value=date.today(),
                    key="travel_date",
                )

            st.write("")

            # Search button.
            search_clicked = st.button(
                "Search flights",
                type="primary",
                use_container_width=True,
            )

            if search_clicked:

                source_id = st.session_state.source_airport_id
                destination_id = st.session_state.destination_airport_id
                travel_date = st.session_state.travel_date

                results = search_flights(
                    source_id,
                    destination_id,
                    travel_date,
                )

                st.session_state.flight_results = results

                # Close any previously opened onboard menu.
                st.session_state.selected_menu = None

            # Retrieve previously searched results.
            results = st.session_state.flight_results

            if search_clicked and not results:
                st.info(
                    "No scheduled flights found for this route and date."
                )

            if results:

                st.success(
                    f"{len(results)} scheduled flight(s) found."
                )

                for flight in results:

                    flight_key = (
                        f"{flight['flight_id']}_"
                        f"{flight['schedule_date']}_"
                        f"{flight['departure_time']}"
                    )

                    with st.container(border=True):

                        st.subheader(
                            f"{flight['flight_number']} | "
                            f"{flight['source_code']} → "
                            f"{flight['destination_code']}"
                        )

                        # Flight overview.
                        col1, col2, col3 = st.columns(3)

                        col1.metric(
                            "Base fare",
                            f"₹{float(flight['base_fare']):,.2f}",
                        )

                        col2.metric(
                            "Aircraft",
                            flight["aircraft_model"],
                        )

                        col3.metric(
                            "Capacity",
                            flight["capacity"],
                        )

                        st.divider()

                        left, right = st.columns(2)

                        with left:

                            st.markdown("**Departure details**")

                            st.write(
                                f"Date: {format_date(flight['schedule_date'])}"
                            )

                            st.write(
                                f"Time: {format_time(flight['departure_time'])}"
                            )

                            st.write(
                                f"Terminal: {flight['departure_terminal']}"
                            )

                            st.write(
                                f"Gate: {flight['gate_number']}"
                            )

                        with right:

                            st.markdown("**Arrival details**")

                            st.write(
                                f"Arrival: {format_datetime(flight['arrival_datetime'])}"
                            )

                            st.write(
                                f"Terminal: {flight['arrival_terminal']}"
                            )

                            st.write(
                                f"Status: {flight['schedule_status']}"
                            )

                        st.divider()

                        # Additional facilities.
                        facility1, facility2, facility3 = st.columns(3)

                        facility1.write(
                            f"**Baggage:** {flight['baggage_allowance']} kg"
                        )

                        facility2.write(
                            f"**Entertainment:** "
                            f"{yes_no(flight['entertainment_available'])}"
                        )

                        facility3.write(
                            f"**Wi-Fi:** "
                            f"{yes_no(flight['wifi_available'])}"
                        )

                        st.write(
                            f"**Meal service:** {flight['meal_service']}"
                        )

                        # Onboard menu toggle.
                        selected_menu = st.session_state.selected_menu

                        is_open = (
                            selected_menu is not None
                            and selected_menu["key"] == flight_key
                        )

                        if st.button(
                            "Hide onboard menu" if is_open
                            else "View onboard menu",
                            key=f"menu_toggle_{flight_key}",
                        ):

                            if is_open:
                                st.session_state.selected_menu = None

                            else:
                                st.session_state.selected_menu = {
                                    "key": flight_key,
                                    "flight_id": flight["flight_id"],
                                    "schedule_date": flight["schedule_date"],
                                    "departure_time": flight["departure_time"],
                                    "flight_number": flight["flight_number"],
                                }

                            st.rerun()


                        # Flight booking form
                        st.divider()
                        st.markdown("### Book this flight")

                        passenger_count = st.selectbox(
                            "Number of passengers",
                            options=[1, 2, 3, 4, 5, 6],
                            key=f"passenger_count_{flight_key}"
                        )

                        available_seats = get_available_seats(
                            flight["flight_id"],
                            flight["schedule_date"],
                            flight["departure_time"]
                        )

                        if len(available_seats) < passenger_count:
                            st.warning(
                                "Not enough available seats for the selected passengers."
                            )

                        
                        with st.form(key=f"booking_form_{flight_key}"):
                            passengers = []
                            selected_seats = []

                            for i in range(passenger_count):
                                st.markdown(f"**Passenger {i + 1}**")

                                seat_options = [
                                    seat for seat in available_seats
                                    if seat not in selected_seats
                                ]

                                if not seat_options:
                                    seat_options = ["No seats available"]

                                col1, col2 = st.columns(2)

                                with col1:
                                    first_name = st.text_input(
                                        "First name *",
                                        key=f"first_{flight_key}_{i}"
                                    )
                                    middle_name = st.text_input(
                                        "Middle name",
                                        key=f"middle_{flight_key}_{i}"
                                    )
                                    last_name = st.text_input(
                                        "Last name *",
                                        key=f"last_{flight_key}_{i}"
                                    )
                                    dob_text = st.text_input(
                                        "Date of birth (YYYY-MM-DD)",
                                        key=f"dob_{flight_key}_{i}",
                                        placeholder="e.g. 2000-05-21"
                                    )

                                with col2:
                                    nationality = st.text_input(
                                        "Nationality",
                                        key=f"nationality_{flight_key}_{i}"
                                    )
                                    passport = st.text_input(
                                        "Passport number",
                                        key=f"passport_{flight_key}_{i}"
                                    )
                                    email = st.text_input(
                                        "Email",
                                        key=f"email_{flight_key}_{i}"
                                    )
                                    phone = st.text_input(
                                        "Phone number",
                                        key=f"phone_{flight_key}_{i}"
                                    )

                                seat_number = st.selectbox(
                                    "Select seat *",
                                    options=seat_options,
                                    key=f"seat_{flight_key}_{i}",
                                    disabled=len(available_seats) < passenger_count
                                )

                                selected_seats.append(seat_number)

                                passengers.append({
                                    "first_name": first_name.strip(),
                                    "middle_name": middle_name.strip(),
                                    "last_name": last_name.strip(),
                                    "date_of_birth": dob_text.strip(),
                                    "nationality": nationality.strip(),
                                    "passport_number": passport.strip(),
                                    "email": email.strip(),
                                    "phone_number": phone.strip(),
                                    "seat_number": seat_number
                                })

                            total_fare = (
                                float(flight["base_fare"]) * passenger_count
                            )

                            st.write(
                                f"**Total fare: ₹{total_fare:,.2f}**"
                            )

                            confirm_booking = st.form_submit_button(
                                "Confirm booking",
                                type="primary",
                                use_container_width=True,
                                disabled=len(available_seats) < passenger_count
                            )


                        
                        if confirm_booking:
                            try:
                                for i, passenger in enumerate(passengers):
                                    if not passenger["first_name"]:
                                        raise ValueError(
                                            f"Enter the first name for passenger {i + 1}."
                                        )

                                    if not passenger["last_name"]:
                                        raise ValueError(
                                            f"Enter the last name for passenger {i + 1}."
                                        )

                                    dob = passenger["date_of_birth"]
                                    passenger["date_of_birth"] = (
                                        date.fromisoformat(dob) if dob else None
                                    )

                                booking_guard_key = f"booking_created_{flight_key}"

                                if booking_guard_key in st.session_state:
                                    st.warning(
                                        f"This flight has already been booked. "
                                        f"Booking ID: {st.session_state[booking_guard_key]}"
                                    )
                                else:
                                    booking_id = create_booking(
                                        user_id=st.session_state.aerobook_user["id"],
                                        flight_id=flight["flight_id"],
                                        schedule_date=flight["schedule_date"],
                                        departure_time=flight["departure_time"],
                                        total_fare=total_fare,
                                        passengers=passengers
                                    )

                                    st.session_state[booking_guard_key] = booking_id

                                    st.success(
                                        f"Booking confirmed! Your booking ID is {booking_id}. "
                                        "Payment is pending."
                                    )

                            except ValueError as error:
                                st.error(str(error))

                            except Exception as error:
                                st.error("Unable to complete your booking.")
                                st.code(str(error))


                # Display the selected flight's onboard menu.
                selected_menu = st.session_state.selected_menu

                if selected_menu:

                    st.divider()

                    st.subheader(
                        f"Onboard Menu — "
                        f"{selected_menu['flight_number']}"
                    )

                    menu = get_flight_food(
                        selected_menu["flight_id"],
                        selected_menu["schedule_date"],
                        selected_menu["departure_time"],
                    )

                    if menu:

                        menu_df = pd.DataFrame(menu)

                        st.dataframe(
                            menu_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                    else:

                        st.info(
                            "No food items are linked to this flight schedule. "
                            "Check the FLIGHT_FOOD table in MySQL."
                        )

                    if st.button(
                        "Close onboard menu",
                        key="close_onboard_menu",
                    ):

                        st.session_state.selected_menu = None
                        st.rerun()

    except Exception as error:

        st.error("Could not load or search flights.")
        st.code(str(error))






elif page =="Food Menu":
# =====================================================
# TAB 2: COMPLETE FOOD CATALOGUE
# =====================================================

    st.header("Food Menu")

    st.write(
        "Browse meals, desserts, snacks and beverages available in AeroBook."
    )

    try:

        food_items = get_food_items()

        if not food_items:

            st.info(
                "No food items found in the FOOD table."
            )

        else:

            df = pd.DataFrame(food_items)

            # Category filter.
            category_options = ["All"] + sorted(
                df["Food_Category"]
                .fillna("Other")
                .astype(str)
                .unique()
                .tolist()
            )

            selected_category = st.selectbox(
                "Filter by category",
                options=category_options,
                key="catalogue_category",
            )

            # Food search.
            search_text = st.text_input(
                "Search food or drinks",
                key="catalogue_search",
            )

            # Apply category filter.
            if selected_category != "All":

                df = df[
                    df["Food_Category"]
                    .fillna("Other")
                    .astype(str)
                    == selected_category
                ]

            # Apply text search.
            if search_text:

                df = df[
                    df["Food_Name"]
                    .astype(str)
                    .str.contains(
                        search_text,
                        case=False,
                        na=False,
                    )
                ]

            st.write(
                f"**{len(df)} item(s) found**"
            )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

    except Exception as error:

        st.error("Could not load the food catalogue.")
        st.code(str(error))




# =====================================================
# MY BOOKINGS PAGE
# =====================================================

elif page == "My Bookings":

    st.title("My Bookings")
    st.caption("View and manage your AeroBook reservations.")

    try:
        bookings = get_passenger_bookings(current_user["id"])
        
        
        

        if not bookings:
            st.info(
                "You haven't made any bookings yet. "
                "Visit Book a Flight to plan your journey."
            )

        else:
            # Booking summary
            total_bookings = len(bookings)

            upcoming_trips = sum(
                1 for booking in bookings
                if booking["schedule_date"] >= date.today()
                and str(booking["booking_status"]).lower() == "confirmed"
            )

            total_spent = sum(
                float(booking["total_fare"] or 0)
                for booking in bookings
            )

            col1, col2, col3 = st.columns(3)

            col1.metric("Total Bookings", total_bookings)
            col2.metric("Upcoming Trips", upcoming_trips)
            col3.metric("Total Fare", f"₹{total_spent:,.2f}")

            st.divider()
            st.subheader("Your Reservations")

            for booking in bookings:

                with st.container(border=True):

                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.subheader(
                            f"✈ {booking['flight_number'] or 'Flight'}"
                        )
                        st.caption(
                            f"Booking Reference: #{booking['booking_id']}"
                        )

                    with col2:
                        st.markdown(
                            f"**{booking['booking_status']}**"
                        )

                    st.divider()

                    detail1, detail2, detail3 = st.columns(3)

                    detail1.write("**Travel Date**")
                    detail1.write(
                        format_date(booking["schedule_date"])
                    )

                    detail2.write("**Departure Time**")
                    detail2.write(
                        format_time(booking["departure_time"])
                    )

                    detail3.write("**Total Fare**")
                    detail3.write(
                        f"₹{float(booking['total_fare']):,.2f}"
                    )

                    st.write(
                        f"**Payment Status:** {booking['payment_status']}"
                    )


                    
                    

                    st.caption(
                        f"Booked on: {format_datetime(booking['booking_date'])}"
                    )

    except Exception as error:
        st.error("Could not load your bookings.")
        st.code(str(error))



# =====================================================
# REWARDS & POINTS PAGE
# =====================================================

elif page == "Rewards":

    st.title("★ Rewards & Points")
    st.caption("Enjoy more benefits with every AeroBook journey.")

    try:
        # Find the passenger record linked to the logged-in account.
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute("""
            SELECT passenger_id
            FROM passenger
            WHERE LOWER(email) = LOWER(%s)
        """, (current_user["email"],))

        passenger = cursor.fetchone()
        cursor.close()
        conn.close()

        if not passenger:
            st.warning(
                "No passenger loyalty profile is linked to this account yet."
            )

        else:
            data = get_passenger_rewards(passenger["passenger_id"])
            award_completed_flight_points()
            data = get_passenger_rewards(passenger["passenger_id"])

            st.markdown("### Your Loyalty Balance")

            st.metric(
                "Available Points",
                f'{data["points"]:,} pts'
            )

            st.divider()
            st.subheader("Explore Rewards")

            rewards = data["rewards"]

            if rewards:
                cols = st.columns(2)

                for index, reward in enumerate(rewards):
                    with cols[index % 2]:
                        with st.container(border=True):
                            st.markdown(
                                f'### {reward["reward_name"]}'
                            )
                            st.caption(reward["reward_type"] or "AeroBook Reward")
                            st.write(
                                reward["reward_description"] or
                                "Enjoy this AeroBook reward."
                            )
                            st.write(
                                f'**{reward["points_required"]:,} points**'
                            )

                        
                            if data["points"] >= reward["points_required"]:
                                st.success("You have enough points!")

                                if st.button(
                                    "Redeem Reward",
                                    key=f"redeem_{reward['reward_id']}"
                                ):
                                    try:
                                        redeem_reward(
                                            passenger["passenger_id"],
                                            reward["reward_id"]
                                        )

                                        st.success(
                                            f'{reward["reward_name"]} redeemed successfully!'
                                        )

                                        st.rerun()

                                    except ValueError as error:
                                        st.warning(str(error))

                                    except Exception as error:
                                        st.error("Could not redeem this reward.")
                                        st.code(str(error))

                            else:
                                st.info(
                                    f'You need {reward["points_required"] - data["points"]:,} more points.'
                                )
                               

            else:
                st.info("No rewards are currently available.")

            st.divider()
            st.subheader("Points Transaction History")

            transactions = data["transactions"]

            if transactions:
                for transaction in transactions:
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])

                        col1.write(
                            f'**{transaction["transaction_type"]}**'
                        )
                        col1.caption(
                            str(transaction["transaction_date"])
                        )

                        points = transaction["points_change"]
                        col2.write(
                            f'{points:+,} pts'
                        )
                        col2.caption(
                            transaction["transaction_status"]
                        )
            else:
                st.info("No points transactions found.")

    except Exception as error:
        st.error("Could not load your rewards information.")
        st.exception(error)


if page == "Entertainment":
    st.title("🎬 In-Flight Entertainment")
    st.caption("Explore entertainment options for your journey.")

    selected = st.session_state.get("selected_entertainment")

    # =================================================
    # WATCH TOGETHER
    # =================================================

    st.divider()
    st.subheader("🤝 Watch Together")
    st.write("Invite multiple passengers on your scheduled flight.")

    # Incoming invitations
    st.markdown("### 📩 Incoming Invitations")

    try:
        invitations = get_pending_watch_invitations(current_user["id"])

        if invitations:
            for invitation in invitations:
                with st.container(border=True):
                    st.write(f"**Movie:** {invitation['title']}")
                    st.write(f"**Inviter's seat:** {invitation['inviter_seat']}")
                    st.write(f"**Your seat:** {invitation['invited_seat']}")

                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button(
                            "Accept",
                            key=f"accept_invite_{invitation['member_id']}",
                            use_container_width=True
                        ):
                            try:
                                respond_to_watch_invitation(
                                    current_user["id"],
                                    invitation["member_id"],
                                    "Accepted"
                                )
                                st.success("Invitation accepted!")
                                st.rerun()

                            except Exception as error:
                                st.error(str(error))

                    with col2:
                        if st.button(
                            "Reject",
                            key=f"reject_invite_{invitation['member_id']}",
                            use_container_width=True
                        ):
                            try:
                                respond_to_watch_invitation(
                                    current_user["id"],
                                    invitation["member_id"],
                                    "Rejected"
                                )
                                st.info("Invitation rejected.")
                                st.rerun()

                            except Exception as error:
                                st.error(str(error))
        else:
            st.info("You have no pending Watch Together invitations.")

    except Exception as error:
        st.error("Unable to load incoming invitations.")
        st.exception(error)

    st.divider()

    # Outgoing invitations
    st.markdown("### 👥 Invite Passengers")

    try:
        watch_options = get_watch_together_options(current_user["id"])

        if watch_options:

            # Group options by scheduled flight and host screen.
            grouped_options = {}

            for option in watch_options:
                group_key = (
                    option["schedule_id"],
                    option["own_screen_id"]
                )

                if group_key not in grouped_options:
                    grouped_options[group_key] = {
                        "flight_number": option["flight_number"],
                        "schedule_id": option["schedule_id"],
                        "own_screen_id": option["own_screen_id"],
                        "own_seat": option["own_seat"],
                        "passengers": []
                    }

                grouped_options[group_key]["passengers"].append(option)

            group_keys = list(grouped_options.keys())

            selected_group_key = st.selectbox(
                "Choose your flight and seat",
                options=group_keys,
                format_func=lambda key: (
                    f"{grouped_options[key]['flight_number']} · "
                    f"Seat {grouped_options[key]['own_seat']}"
                ),
                key="watch_group_selection"
            )

            selected_group = grouped_options[selected_group_key]

            st.write(f"**Flight:** {selected_group['flight_number']}")
            st.write(f"**Your seat:** {selected_group['own_seat']}")

            passenger_options = {
                option["target_screen_id"]: option
                for option in selected_group["passengers"]
            }

            selected_screens = st.multiselect(
                "Select passengers to invite",
                options=list(passenger_options.keys()),
                format_func=lambda screen_id: (
                    f"Seat {passenger_options[screen_id]['target_seat']}"
                ),
                key=f"watch_passengers_{selected_group['schedule_id']}_{selected_group['own_screen_id']}"
            )

            if selected_screens:
                st.write(
                    f"**{len(selected_screens)} passenger(s) selected**"
                )

            if not selected:
                st.info(
                    "First select a movie or show using Watch Now. "
                    "Then you can send invitations."
                )

            if st.button(
                "🤝 Send Invitations",
                type="primary",
                use_container_width=True,
                disabled=not selected or not selected_screens
            ):
                try:
                    session_id = send_watch_together_invitations(
                        current_user["id"],
                        selected["content_id"],
                        selected_group["schedule_id"],
                        selected_group["own_screen_id"],
                        selected_screens
                    )

                    st.success(
                        f"Invitations sent successfully! "
                        f"Group session: {session_id}"
                    )
                    st.rerun()

                except Exception as error:
                    st.error("Could not send the invitations.")
                    st.exception(error)

        else:
            st.info(
                "No other confirmed passengers with operational screens "
                "were found on your scheduled flight."
            )

    except Exception as error:
        st.error("Unable to load Watch Together options.")
        st.exception(error)

    # =================================================
    # SELECTED ENTERTAINMENT
    # =================================================

    if selected:
        st.divider()
        st.subheader("🎬 Now Playing")

        st.markdown(f"### {selected['title']}")
        st.write(f"**Type:** {selected['content_type']}")
        st.write(f"**Duration:** {selected['duration_minutes']} minutes")
        st.write(f"**Language:** {selected['language']}")
        st.write(f"**Age Rating:** {selected['content_rating']}")

        st.info(
            "Your selected entertainment is ready. "
            "Playback can be connected to the onboard screen system."
        )

        if st.button("← Back to Entertainment"):
            st.session_state.selected_entertainment = None
            st.rerun()

    else:
        # Load entertainment catalogue
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT
                    content_id,
                    title,
                    content_type,
                    duration_minutes,
                    language,
                    content_rating
                FROM entertainment_content
                WHERE availability_status = 'Available'
                ORDER BY content_type, title
            """)

            content = cursor.fetchall()

            cursor.close()
            conn.close()

            if not content:
                st.info("No entertainment content is currently available.")

            else:
                movie_tab, show_tab, other_tab = st.tabs(
                    ["🎥 Movies", "📺 Shows", "🎧 Other"]
                )

                categories = [
                    (movie_tab, "Movie"),
                    (show_tab, "TV Show"),
                    (other_tab, "Other")
                ]

                for tab, category in categories:
                    with tab:

                        if category == "Other":
                            items = [
                                item for item in content
                                if item["content_type"] not in ["Movie", "TV Show"]
                            ]
                        else:
                            items = [
                                item for item in content
                                if item["content_type"].lower() == category.lower()
                            ]

                        if not items:
                            st.info(
                                f"No {category.lower()} content available."
                            )

                        else:
                            cols = st.columns(2)

                            for index, item in enumerate(items):
                                with cols[index % 2]:
                                    with st.container(border=True):

                                        st.subheader(item["title"])
                                        st.caption(item["content_type"])

                                        st.write(
                                            f"⏱️ Duration: "
                                            f"{item['duration_minutes']} minutes"
                                        )

                                        st.write(
                                            f"🌐 Language: {item['language']}"
                                        )

                                        st.write(
                                            f"⚠️ Age Rating: "
                                            f"{item['content_rating']}"
                                        )

                                        if st.button(
                                            "▶ Watch Now",
                                            key=f"watch_{item['content_id']}"
                                        ):
                                            st.session_state.selected_entertainment = item
                                            st.rerun()

        except Exception as error:
            st.error("Unable to load entertainment content.")
            st.code(str(error))
