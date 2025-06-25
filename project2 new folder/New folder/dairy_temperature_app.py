import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import pytz
import plotly.express as px
import random
import hashlib
import json
import sqlite3
from passlib.hash import pbkdf2_sha256

# Database Setup
def init_db():
    conn = sqlite3.connect('dairy_temperature.db')
    c = conn.cursor()
    
    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password_hash TEXT,
                  role TEXT,
                  full_name TEXT,
                  email TEXT,
                  approved INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  min_temp REAL,
                  max_temp REAL,
                  humidity REAL,
                  shelf_life INTEGER,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS rooms
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  current_temp REAL,
                  target_temp REAL,
                  humidity REAL,
                  current_product_id INTEGER,
                  last_updated TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  room_id INTEGER,
                  temperature REAL,
                  humidity REAL,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  action TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS weather_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  location TEXT,
                  temperature REAL,
                  humidity REAL,
                  conditions TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Insert default admin if not exists
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        admin_hash = pbkdf2_sha256.hash("sujal@2794")
        c.execute("INSERT INTO users (username, password_hash, role, full_name, email, approved) VALUES (?, ?, ?, ?, ?, ?)",
                  ("vs27", admin_hash, "admin", "System Admin", "admin@flavidairy.com", 1))
    
    # Insert some default products if empty
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        default_products = [
            ("Milk", 2, 4, 70, 5),
            ("Curd", 2, 4, 75, 7),
            ("Butter", -15, -10, 80, 90),
            ("Cheese", 1, 4, 85, 30),
            ("Ice Cream", -25, -18, 70, 365)
        ]
        c.executemany("INSERT INTO products (name, min_temp, max_temp, humidity, shelf_life) VALUES (?, ?, ?, ?, ?)", default_products)
    
    # Insert some rooms if empty
    c.execute("SELECT COUNT(*) FROM rooms")
    if c.fetchone()[0] == 0:
        default_rooms = [
            ("Room 1", 4.0, 4.0, 70.0, None),
            ("Room 2", 4.0, 4.0, 70.0, None),
            ("Freezer 1", -18.0, -18.0, 70.0, None)
        ]
        c.executemany("INSERT INTO rooms (name, current_temp, target_temp, humidity, current_product_id) VALUES (?, ?, ?, ?, ?)", default_rooms)
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Database helper functions
def get_db_connection():
    return sqlite3.connect('dairy_temperature.db')

def get_user(username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user

def verify_password(username, password):
    user = get_user(username)
    if user and pbkdf2_sha256.verify(password, user[2]):
        return user
    return None

def register_user(username, password, role, full_name, email):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        password_hash = pbkdf2_sha256.hash(password)
        c.execute("INSERT INTO users (username, password_hash, role, full_name, email) VALUES (?, ?, ?, ?, ?)",
                  (username, password_hash, role, full_name, email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_pending_users():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, role, full_name, email, created_at FROM users WHERE approved = 0")
    users = c.fetchall()
    conn.close()
    return users

def approve_user(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def reject_user(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_products():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, min_temp, max_temp, humidity, shelf_life FROM products")
    products = c.fetchall()
    conn.close()
    return products

def get_product_by_name(name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, min_temp, max_temp, humidity, shelf_life FROM products WHERE name = ?", (name,))
    product = c.fetchone()
    conn.close()
    return product

def add_product(name, min_temp, max_temp, humidity, shelf_life):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO products (name, min_temp, max_temp, humidity, shelf_life) VALUES (?, ?, ?, ?, ?)",
                  (name, min_temp, max_temp, humidity, shelf_life))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_rooms():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, current_temp, target_temp, humidity, current_product_id FROM rooms")
    rooms = c.fetchall()
    conn.close()
    return rooms

def update_room(room_id, target_temp=None, current_product_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    if target_temp is not None:
        c.execute("UPDATE rooms SET target_temp = ? WHERE id = ?", (target_temp, room_id))
    if current_product_id is not None:
        c.execute("UPDATE rooms SET current_product_id = ? WHERE id = ?", (current_product_id, room_id))
    conn.commit()
    conn.close()

def log_action(user_id, action):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO audit_log (user_id, action) VALUES (?, ?)", (user_id, action))
    conn.commit()
    conn.close()

def get_audit_logs(limit=100):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT a.timestamp, u.username, a.action 
                 FROM audit_log a
                 JOIN users u ON a.user_id = u.id
                 ORDER BY a.timestamp DESC
                 LIMIT ?''', (limit,))
    logs = c.fetchall()
    conn.close()
    return logs

# Simulated IoT sensors
class RoomSensor:
    def __init__(self, room_id):
        self.room_id = room_id
        self.update_sensor_data()
    
    def update_sensor_data(self):
        conn = get_db_connection()
        c = conn.cursor()
        # Get current room data
        c.execute("SELECT current_temp, humidity FROM rooms WHERE id = ?", (self.room_id,))
        room = c.fetchone()
        
        if room:
            # Simulate small fluctuations
            new_temp = room[0] + random.uniform(-0.2, 0.2)
            new_humidity = room[1] + random.uniform(-1, 1)
            
            # Update room data
            c.execute("UPDATE rooms SET current_temp = ?, humidity = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                      (new_temp, new_humidity, self.room_id))
            
            # Log sensor data
            c.execute("INSERT INTO sensor_data (room_id, temperature, humidity) VALUES (?, ?, ?)",
                      (self.room_id, new_temp, new_humidity))
            
            conn.commit()
            conn.close()
            return new_temp, new_humidity, datetime.now()
        
        conn.close()
        return None, None, None

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.full_name = None
    st.session_state.current_room_id = 1  # Default to Room 1
    st.session_state.room_sensor = RoomSensor(1)
    st.session_state.weather_data = None
    st.session_state.alerts = []
    st.session_state.energy_saving = False
    st.session_state.manual_override = False

# Helper functions
def recommend_temperature(product, external_temp):
    if not product:
        return None
    
    # Simple AI recommendation based on external temp
    if external_temp > 30:
        return max(product[2], (product[2] + product[3])/2 - 1)
    elif external_temp < 10:
        return min(product[3], (product[2] + product[3])/2 + 1)
    else:
        return (product[2] + product[3])/2

def check_for_alerts():
    alerts = []
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get current room data
    c.execute('''SELECT r.current_temp, r.humidity, r.target_temp, p.min_temp, p.max_temp, p.humidity 
                 FROM rooms r
                 LEFT JOIN products p ON r.current_product_id = p.id
                 WHERE r.id = ?''', (st.session_state.current_room_id,))
    room_data = c.fetchone()
    conn.close()
    
    if room_data:
        current_temp, current_humidity, target_temp, min_temp, max_temp, ideal_humidity = room_data
        
        if min_temp is not None and current_temp < min_temp:
            alerts.append(f"Temperature too low! Current: {current_temp:.1f}°C, Minimum: {min_temp}°C")
        if max_temp is not None and current_temp > max_temp:
            alerts.append(f"Temperature too high! Current: {current_temp:.1f}°C, Maximum: {max_temp}°C")
        if ideal_humidity is not None and abs(current_humidity - ideal_humidity) > 10:
            alerts.append(f"Humidity deviation! Current: {current_humidity:.1f}%, Ideal: {ideal_humidity}%")
    
    if st.session_state.manual_override:
        alerts.append("Manual override active - automated controls disabled")
    
    st.session_state.alerts = alerts

def get_weather(location="Ahmedabad"):
    # Simulated weather API call
    weather = {
        "temperature": random.uniform(15, 45),
        "humidity": random.uniform(30, 90),
        "conditions": random.choice(["Sunny", "Cloudy", "Rainy", "Partly Cloudy"]),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    st.session_state.weather_data = weather
    return weather

# Login Page
def login_page():
    st.title("Flavi Dairy Solutions - Temperature Control System")
    st.image("https://via.placeholder.com/800x200?text=Dairy+Temperature+Control", use_column_width=True)
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                user = verify_password(username, password)
                if user:
                    if user[6]:  # Check if approved
                        st.session_state.logged_in = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1]
                        st.session_state.user_role = user[3]
                        st.session_state.full_name = user[4]
                        log_action(user[0], "User logged in")
                        st.rerun()
                    else:
                        st.error("Your account is pending approval. Please contact admin.")
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        with st.form("register_form"):
            st.subheader("New User Registration")
            username = st.text_input("Choose Username")
            password = st.text_input("Choose Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            full_name = st.text_input("Full Name")
            email = st.text_input("Email")
            role = st.selectbox("Role", ["technician", "viewer"], index=0)
            
            if st.form_submit_button("Register"):
                if password != confirm_password:
                    st.error("Passwords do not match!")
                elif not all([username, password, full_name, email]):
                    st.error("Please fill all fields!")
                else:
                    if register_user(username, password, role, full_name, email):
                        st.success("Registration successful! Your account is pending approval.")
                    else:
                        st.error("Username already exists. Please choose another.")

# User Approval Page (Admin only)
def user_approval_page():
    st.title("User Approval")
    
    pending_users = get_pending_users()
    if not pending_users:
        st.info("No pending user approvals")
        return
    
    for user in pending_users:
        user_id, username, role, full_name, email, created_at = user
        
        with st.expander(f"{full_name} ({username}) - {role}"):
            st.write(f"**Email:** {email}")
            st.write(f"**Registered on:** {created_at}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Approve {username}", key=f"approve_{user_id}"):
                    approve_user(user_id)
                    log_action(st.session_state.user_id, f"Approved user {username}")
                    st.success(f"User {username} approved!")
                    time.sleep(1)
                    st.rerun()
            with col2:
                if st.button(f"Reject {username}", key=f"reject_{user_id}"):
                    reject_user(user_id)
                    log_action(st.session_state.user_id, f"Rejected user {username}")
                    st.success(f"User {username} rejected!")
                    time.sleep(1)
                    st.rerun()

# Main Application
def main_app():
    # Sidebar
    with st.sidebar:
        st.image("logo.png", width=150)
        st.title(f"Welcome, {st.session_state.full_name}")
        st.caption(f"Role: {st.session_state.user_role}")
        
        # Navigation
        if st.session_state.user_role == "admin":
            menu_options = ["Dashboard", "User Approval", "System Settings", "Audit Log"]
        elif st.session_state.user_role == "technician":
            menu_options = ["Dashboard", "Temperature Control", "Product Management"]
        else:  # viewer
            menu_options = ["Dashboard"]
        
        selected_page = st.sidebar.radio("Navigation", menu_options)
        
        # Room selection for technicians and admins
        if st.session_state.user_role in ["admin", "technician"]:
            rooms = get_all_rooms()
            room_names = [room[1] for room in rooms]
            current_room_name = next((room[1] for room in rooms if room[0] == st.session_state.current_room_id), "Room 1")
            
            new_room = st.selectbox(
                "Select Room", 
                room_names,
                index=room_names.index(current_room_name)
            )
            
            if new_room != current_room_name:
                new_room_id = next(room[0] for room in rooms if room[1] == new_room)
                st.session_state.current_room_id = new_room_id
                st.session_state.room_sensor = RoomSensor(new_room_id)
                log_action(st.session_state.user_id, f"Switched to room {new_room}")
        
        # System controls
        if st.session_state.user_role in ["admin", "technician"]:
            st.session_state.manual_override = st.toggle("Manual Override", st.session_state.manual_override)
            st.session_state.energy_saving = st.toggle("Energy Saving Mode", st.session_state.energy_saving)
        
        if st.button("Refresh Weather Data"):
            get_weather()
            log_action(st.session_state.user_id, "Refreshed weather data")
            st.toast("Weather data refreshed")
        
        if st.button("Logout"):
            log_action(st.session_state.user_id, "User logged out")
            st.session_state.logged_in = False
            st.rerun()
    
    # Page routing
    if selected_page == "Dashboard":
        dashboard_page()
    elif selected_page == "User Approval" and st.session_state.user_role == "admin":
        user_approval_page()
    elif selected_page == "System Settings" and st.session_state.user_role == "admin":
        system_settings_page()
    elif selected_page == "Audit Log" and st.session_state.user_role == "admin":
        audit_log_page()
    elif selected_page == "Temperature Control" and st.session_state.user_role in ["admin", "technician"]:
        temperature_control_page()
    elif selected_page == "Product Management" and st.session_state.user_role in ["admin", "technician"]:
        product_management_page()

# Dashboard Page
def dashboard_page():
    st.title("Dairy Temperature Control Dashboard")
    
    # Get current sensor data
    current_temp, current_humidity, last_updated = st.session_state.room_sensor.update_sensor_data()
    weather = st.session_state.weather_data if st.session_state.weather_data else get_weather()
    
    # Get current room and product info
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT r.name, p.name 
                 FROM rooms r
                 LEFT JOIN products p ON r.current_product_id = p.id
                 WHERE r.id = ?''', (st.session_state.current_room_id,))
    room_info = c.fetchone()
    conn.close()
    
    room_name = room_info[0] if room_info else "Unknown Room"
    current_product = room_info[1] if room_info and room_info[1] else None
    
    # Check for alerts
    check_for_alerts()
    
    # Display alerts if any
    if st.session_state.alerts:
        for alert in st.session_state.alerts:
            st.warning(alert)
    
    # Dashboard metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Room Temperature", f"{current_temp:.1f}°C" if current_temp else "N/A", 
                 delta=f"{(current_temp - weather['temperature']):.1f}°C from external" if current_temp and weather else None)
    with col2:
        st.metric("Room Humidity", f"{current_humidity:.1f}%" if current_humidity else "N/A")
    with col3:
        st.metric("External Temperature", f"{weather['temperature']:.1f}°C", weather['conditions'])
    with col4:
        status = "Normal" if not st.session_state.alerts else "Alert"
        status += " (Energy Saving)" if st.session_state.energy_saving else ""
        st.metric("System Status", status)
    
    # Product information
    if current_product:
        st.subheader(f"Product: {current_product}")
        product = get_product_by_name(current_product)
        
        if product:
            cols = st.columns(3)
            with cols[0]:
                st.write(f"**Temperature Range:** {product[2]}°C to {product[3]}°C")
            with cols[1]:
                st.write(f"**Humidity:** {product[4]}%")
            with cols[2]:
                st.write(f"**Shelf Life:** {product[5]} days")
            
            # AI recommendation
            recommended_temp = recommend_temperature(product, weather['temperature'])
            if recommended_temp:
                st.info(f"Recommended temperature based on external conditions: {recommended_temp:.1f}°C")
    
    # Historical data visualization
    st.subheader("Temperature & Humidity Trends")
    
    # Get historical data from database
    conn = get_db_connection()
    sensor_data = pd.read_sql('''SELECT timestamp, temperature, humidity 
                                FROM sensor_data 
                                WHERE room_id = ?
                                ORDER BY timestamp DESC
                                LIMIT 100''', 
                             conn, params=(st.session_state.current_room_id,))
    conn.close()
    
    if not sensor_data.empty:
        # Plot temperature
        fig_temp = px.line(sensor_data, x="timestamp", y="temperature", 
                          title="Temperature History",
                          labels={"temperature": "Temperature (°C)", "timestamp": "Time"})
        st.plotly_chart(fig_temp, use_container_width=True)
        
        # Plot humidity
        fig_humidity = px.line(sensor_data, x="timestamp", y="humidity", 
                              title="Humidity History",
                              labels={"humidity": "Humidity (%)", "timestamp": "Time"})
        st.plotly_chart(fig_humidity, use_container_width=True)
    else:
        st.info("No historical data available yet")

# Temperature Control Page
def temperature_control_page():
    st.title("Temperature Control")
    
    # Get current room data
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT r.target_temp, r.current_product_id, p.name, p.min_temp, p.max_temp
                 FROM rooms r
                 LEFT JOIN products p ON r.current_product_id = p.id
                 WHERE r.id = ?''', (st.session_state.current_room_id,))
    room_data = c.fetchone()
    conn.close()
    
    target_temp = room_data[0] if room_data else 4.0
    current_product_id = room_data[1] if room_data else None
    current_product = room_data[2] if room_data and room_data[2] else None
    min_temp = room_data[3] if room_data and room_data[3] else -30.0
    max_temp = room_data[4] if room_data and room_data[4] else 30.0
    
    # Product selection
    products = get_all_products()
    product_options = [""] + [product[1] for product in products]
    current_product_index = 0 if not current_product else [product[1] for product in products].index(current_product) + 1
    
    new_product = st.selectbox(
        "Select Product", 
        product_options,
        index=current_product_index
    )
    
    if new_product and new_product != current_product:
        product_id = next((product[0] for product in products if product[1] == new_product), None)
        if product_id:
            update_room(st.session_state.current_room_id, current_product_id=product_id)
            log_action(st.session_state.user_id, f"Set product to {new_product} in room {st.session_state.current_room_id}")
            st.success(f"Product set to {new_product}")
            st.rerun()
    
    # Temperature control
    if st.session_state.manual_override:
        st.warning("Manual override is active")
        
        new_target_temp = st.slider(
            "Set Target Temperature", 
            min_value=-30.0, 
            max_value=30.0, 
            value=target_temp,
            step=0.5
        )
        
        if st.button("Apply Temperature"):
            update_room(st.session_state.current_room_id, target_temp=new_target_temp)
            log_action(st.session_state.user_id, f"Manually set temperature to {new_target_temp}°C in room {st.session_state.current_room_id}")
            st.success(f"Temperature set to {new_target_temp}°C")
            st.rerun()
    else:
        st.info("Temperature is automatically controlled. Enable manual override to change.")
        
        if current_product:
            weather = st.session_state.weather_data if st.session_state.weather_data else get_weather()
            recommended_temp = recommend_temperature((0, "", min_temp, max_temp, 0, 0), weather['temperature'])
            
            if recommended_temp:
                st.write(f"Recommended temperature: {recommended_temp:.1f}°C")
                
                if st.button("Apply Recommended Temperature"):
                    update_room(st.session_state.current_room_id, target_temp=recommended_temp)
                    log_action(st.session_state.user_id, f"Applied recommended temperature {recommended_temp:.1f}°C in room {st.session_state.current_room_id}")
                    st.success(f"Temperature set to {recommended_temp:.1f}°C")
                    st.rerun()

# Product Management Page
def product_management_page():
    st.title("Product Management")
    
    tab1, tab2 = st.tabs(["View Products", "Add New Product"])
    
    with tab1:
        products = get_all_products()
        if products:
            df = pd.DataFrame(products, columns=["ID", "Name", "Min Temp", "Max Temp", "Humidity", "Shelf Life"])
            st.dataframe(df.set_index("ID"), use_container_width=True)
        else:
            st.info("No products in database")
    
    with tab2:
        with st.form("new_product_form"):
            st.subheader("Add New Product")
            name = st.text_input("Product Name")
            min_temp = st.number_input("Minimum Temperature (°C)", value=4.0)
            max_temp = st.number_input("Maximum Temperature (°C)", value=6.0)
            humidity = st.number_input("Humidity (%)", value=70.0)
            shelf_life = st.number_input("Shelf Life (days)", value=7)
            
            if st.form_submit_button("Add Product"):
                if name:
                    if add_product(name, min_temp, max_temp, humidity, shelf_life):
                        st.success(f"Product {name} added successfully!")
                        log_action(st.session_state.user_id, f"Added new product: {name}")
                        st.rerun()
                    else:
                        st.error("Product with this name already exists")
                else:
                    st.error("Please enter a product name")

# System Settings Page (Admin only)
def system_settings_page():
    st.title("System Settings")
    st.warning("Administrator access only")
    
    with st.expander("Database Maintenance"):
        if st.button("Backup Database"):
            # In a real implementation, this would create a backup file
            st.success("Database backup created (simulated)")
            log_action(st.session_state.user_id, "Created database backup")
        
        if st.button("Clear Historical Data (older than 30 days)"):
            # In a real implementation, this would delete old records
            st.success("Old data cleared (simulated)")
            log_action(st.session_state.user_id, "Cleared historical data")
    
    with st.expander("System Configuration"):
        # Simulated configuration options
        alert_email = st.text_input("Alert Email Address", "alerts@flavidairy.com")
        temp_check_interval = st.selectbox("Temperature Check Interval", ["1 minute", "5 minutes", "15 minutes"], index=1)
        
        if st.button("Save Configuration"):
            st.success("Configuration saved (simulated)")
            log_action(st.session_state.user_id, "Updated system configuration")

# Audit Log Page (Admin only)
def audit_log_page():
    st.title("Audit Logs")
    
    logs = get_audit_logs()
    if logs:
        df = pd.DataFrame(logs, columns=["Timestamp", "User", "Action"])
        st.dataframe(df.set_index("Timestamp"), use_container_width=True)
        
        if st.button("Clear Logs"):
            # In a real implementation, this would clear the logs
            st.success("Logs cleared (simulated)")
            log_action(st.session_state.user_id, "Cleared audit logs")
    else:
        st.info("No audit logs available")

# Run the app
if not st.session_state.logged_in:
    login_page()
else:
    main_app()