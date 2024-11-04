import tkinter as tk
from tkinter import messagebox
from ttkbootstrap import Style, ttk
import mysql.connector
from mysql.connector import Error
import re
from PIL import Image, ImageTk
from ttkbootstrap.constants import CENTER
import requests
from io import BytesIO

# MySQL Configuration
MYSQL_HOST = '139.99.97.250'
MYSQL_DATABASE = 'evote'
MYSQL_USER = 'evote'
MYSQL_PASSWORD = 'TacHIuuWOuhPS!Oh'

# Connect to MySQL Database
def connect_to_db():
    try:
        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            database=MYSQL_DATABASE,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )
        if connection.is_connected():
            return connection
    except Error as e:
        messagebox.showerror("Database Error", f"Error connecting to MySQL: {e}")
    return None

# Fetch Departments from the database
def fetch_departments():
    connection = connect_to_db()
    if connection is None:
        return []
    try:
        cursor = connection.cursor(dictionary=True)
        departments_query = "SELECT department_id, department_name FROM department ORDER BY department_name"
        cursor.execute(departments_query)
        departments = cursor.fetchall()
        return departments
    except Error as e:
        messagebox.showerror("Database Error", f"Failed to fetch departments: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return []

# Fetch Courses based on Department ID
def fetch_courses(department_id):
    connection = connect_to_db()
    if connection is None:
        return []
    try:
        cursor = connection.cursor(dictionary=True)
        courses_query = """
            SELECT course_id, course_name 
            FROM course 
            WHERE course_department = %s 
            ORDER BY course_name
        """
        cursor.execute(courses_query, (department_id,))
        courses = cursor.fetchall()
        return courses
    except Error as e:
        messagebox.showerror("Database Error", f"Failed to fetch courses: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return []

# Register User with additional details
def register_user(student_id, first_name, middle_name, last_name, suffix_name, year_level, department_id, course_id):
    if not re.match(r'^[A-Za-z0-9\-]+$', student_id):
        messagebox.showerror("Invalid ID", "School ID format is invalid. Please use only letters, numbers, and hyphens.")
        return False
    connection = connect_to_db()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO students 
            (student_id, first_name, middle_name, last_name, suffix_name, year_level, department, course) 
        VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            student_id, 
            first_name, 
            middle_name, 
            last_name, 
            suffix_name if suffix_name else None,  
            year_level, 
            department_id, 
            course_id
        ))
        connection.commit()
        messagebox.showinfo("Success", "Registration successful!")
        return True
    except mysql.connector.IntegrityError:
        messagebox.showerror("Registration Error", "This School ID is already registered.")
    except Error as e:
        messagebox.showerror("Database Error", f"Failed to register user: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return False

# Login User
def login_user(student_id):
    if not re.match(r'^[A-Za-z0-9\-]+$', student_id):
        messagebox.showerror("Invalid ID", "School ID format is invalid. Please use only letters, numbers, and hyphens.")
        return None
    connection = connect_to_db()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        select_query = """
        SELECT s.id, s.student_id, s.first_name, s.middle_name, s.last_name, s.suffix_name,
               s.year_level, d.department_name, c.course_name
        FROM students s
        INNER JOIN department d ON s.department = d.department_id
        INNER JOIN course c ON s.course = c.course_id
        WHERE s.student_id = %s
        """
        cursor.execute(select_query, (student_id,))
        result = cursor.fetchone()
        if result:
            return result  # Return a dictionary with student data
        else:
            return None
    except Error as e:
        messagebox.showerror("Database Error", f"Failed to login: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None

# Fetch Candidates for Voting
def fetch_candidates():
    connection = connect_to_db()
    if connection is None:
        return [], {}
    try:
        cursor = connection.cursor(dictionary=True)
        positions_query = "SELECT * FROM positions"
        cursor.execute(positions_query)
        positions = cursor.fetchall()

        result = []
        candidate_partylist_map = {}  # Mapping from candidate_id to partylist_id

        for position in positions:
            position_id = position['position_id']
            position_name = position['position_name']

            candidates_query = """
            SELECT candidates.*, department.*, 
                   CONCAT(students.first_name, ' ', students.middle_name, ' ', students.last_name) AS candidate_name, 
                   partylists.partylist_name, partylists.partylist_id,
                   candidates.platform
            FROM candidates
            INNER JOIN students ON candidates.student_id = students.id
            INNER JOIN department ON candidates.department = department.department_id
            LEFT JOIN partylists ON candidates.partylist_id = partylists.partylist_id
            WHERE candidates.candidate_position = %s
            """
            cursor.execute(candidates_query, (position_id,))
            candidates = cursor.fetchall()

            # Build candidate to partylist mapping
            for candidate in candidates:
                candidate_partylist_map[candidate['candidate_id']] = candidate['partylist_id']

            result.append({
                'position_id': position_id,
                'position_name': position_name,
                'candidates': candidates
            })
        return result, candidate_partylist_map
    except Error as e:
        messagebox.showerror("Database Error", f"Failed to fetch candidates: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return [], {}

# Get Voted Candidate Details
def get_vote(student_db_id, position_id):
    connection = connect_to_db()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT c.candidate_id, c.position_id, c.partylist_id,
               CONCAT(s.first_name, ' ', s.middle_name, ' ', s.last_name) AS candidate_name,
               p.partylist_name,
               v.voted_at
        FROM votes v
        INNER JOIN candidates c ON v.candidate_id = c.candidate_id
        INNER JOIN students s ON c.student_id = s.id
        LEFT JOIN partylists p ON c.partylist_id = p.partylist_id
        WHERE v.student_id = %s AND v.position_id = %s
        """
        cursor.execute(query, (student_db_id, position_id))
        result = cursor.fetchone()
        return result
    except Error as e:
        messagebox.showerror("Database Error", f"Failed to retrieve vote: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None

# Get All Votes for a User
def get_all_votes(student_db_id):
    connection = connect_to_db()
    if connection is None:
        return []
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT 
                positions.position_id,
                positions.position_name,
                partylists.partylist_name,
                CONCAT(students.first_name, ' ', students.middle_name, ' ', students.last_name) AS candidate_name,
                votes.voted_at,
                candidates.platform,
                department.department_name,
                candidates.candidate_id
            FROM 
                votes
            INNER JOIN 
                candidates ON candidates.candidate_id = votes.candidate_id
            INNER JOIN 
                students ON students.id = candidates.student_id
            INNER JOIN 
                course ON students.course = course.course_id
            INNER JOIN 
                department ON department.department_id = students.department
            INNER JOIN 
                positions ON positions.position_id = votes.position_id
            LEFT JOIN 
                partylists ON partylists.partylist_id = candidates.partylist_id
            WHERE 
                votes.student_id = %s 
            ORDER BY 
                votes.voted_at;
        """
        cursor.execute(query, (student_db_id,))
        votes = cursor.fetchall()
        
        # Debugging: Print fetched votes
        print(f"Fetched Votes: {votes}")
        
        return votes
    except Error as e:
        messagebox.showerror("Database Error", f"Failed to retrieve votes: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return []

# Submit Vote to Database
def submit_vote(student_db_id, votes, candidate_partylist_map):
    if not votes:
        messagebox.showwarning("No Selection", "Please select at least one candidate to vote.")
        return
    connection = connect_to_db()
    if connection is None:
        return
    try:
        # Begin a transaction
        connection.start_transaction()
        cursor = connection.cursor()

        # Check if the student has already voted for all available positions
        sql_check_vote = """
        SELECT COUNT(DISTINCT position_id) FROM votes WHERE student_id = %s
        """
        cursor.execute(sql_check_vote, (student_db_id,))
        voted_positions_count = cursor.fetchone()[0]

        # Fetch total number of positions
        sql_total_positions = "SELECT COUNT(*) FROM positions"
        cursor.execute(sql_total_positions)
        total_positions = cursor.fetchone()[0]

        if voted_positions_count >= total_positions:
            raise Exception("You have already voted for all available positions.")

        # Insert the votes into the database
        for vote in votes:
            candidate_id = vote['candidate_id']
            position_id = vote['position_id']
            partylist_id = candidate_partylist_map.get(candidate_id, None)

            # Validate candidate_id
            sql_check_candidate = """
            SELECT COUNT(*) FROM candidates WHERE candidate_id = %s
            """
            cursor.execute(sql_check_candidate, (candidate_id,))
            candidate_exists = cursor.fetchone()[0]

            if candidate_exists == 0:
                raise Exception(f"Candidate ID {candidate_id} does not exist.")

            # Validate position_id
            sql_check_position = """
            SELECT COUNT(*) FROM positions WHERE position_id = %s
            """
            cursor.execute(sql_check_position, (position_id,))
            position_exists = cursor.fetchone()[0]

            if position_exists == 0:
                raise Exception(f"Position ID {position_id} does not exist.")

            # Check if already voted for this position
            sql_check_individual_vote = """
            SELECT COUNT(*) FROM votes WHERE student_id = %s AND position_id = %s
            """
            cursor.execute(sql_check_individual_vote, (student_db_id, position_id))
            already_voted = cursor.fetchone()[0]
            if already_voted > 0:
                raise Exception(f"You have already voted for the position: {position_id}.")

            # Insert the vote, allowing partylist_id to be NULL
            sql_insert_vote = """
            INSERT INTO votes (student_id, candidate_id, position_id, partylist_id) 
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_insert_vote, (
                student_db_id, 
                candidate_id, 
                position_id, 
                partylist_id
            ))

        # Commit the transaction
        connection.commit()
        messagebox.showinfo("Success", "Your vote has been submitted successfully!")
    except Exception as e:
        # Roll back the transaction on error
        connection.rollback()
        messagebox.showerror("Database Error", f"Failed to submit vote: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Check if User Voted for a Specific Position
def has_voted(student_db_id, position_id):
    vote = get_vote(student_db_id, position_id)
    return vote is not None

# Create a Scrollable Frame
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        canvas = tk.Canvas(self, bg='#f8f9fa')  # Light background
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas, padding=10)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

# Handle extended registration with all fields
def on_register_extended(student_id, first_name, middle_name, last_name, suffix_name, year_level, department_name, course_name):
    # Validate mandatory fields
    if not student_id or not first_name or not last_name or not year_level or not department_name or not course_name:
        messagebox.showerror("Input Error", "Please fill in all mandatory fields.")
        return

    # Handle Suffix Name
    suffix = suffix_name if suffix_name.strip().upper() != "N/A" else None

    # Get Department ID
    departments = fetch_departments()
    department_id = None
    for dept in departments:
        if dept['department_name'] == department_name:
            department_id = dept['department_id']
            break
    if not department_id:
        messagebox.showerror("Selection Error", "Invalid Department selected.")
        return

    # Get Course ID
    courses = fetch_courses(department_id)
    course_id = None
    for course in courses:
        if course['course_name'] == course_name:
            course_id = course['course_id']
            break
    if not course_id:
        messagebox.showerror("Selection Error", "Invalid Course selected.")
        return

    # Call the register_user function with all parameters
    success = register_user(
        student_id=student_id,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        suffix_name=suffix,
        year_level=year_level,
        department_id=department_id,
        course_id=course_id
    )

    if success:
        # Optionally, clear the fields after successful registration
        messagebox.showinfo("Registration Success", "You have been registered successfully! Please log in.")
        switch_frame(login_frame)

# Create Tkinter GUI
def create_gui():
    # Initialize ttkbootstrap style
    style = Style(theme='flatly')  # You can choose other themes like 'cosmo', 'darkly', etc.

    window = style.master
    window.title("eVote System")
    window.geometry("900x800")  # Increased size for better spacing
    window.configure(bg='#f8f9fa')  # Light background

    # Configure styles
    style.configure("TButton", font=('Helvetica', 12), padding=10)
    style.configure("TLabel", font=('Helvetica', 12), background='#f8f9fa')
    style.configure("TEntry", font=('Helvetica', 12))
    style.configure("TRadiobutton", font=('Helvetica', 10), background='#f8f9fa')
    style.configure("TFrame", background='#f8f9fa')
    style.configure("TLabelFrame.Label", font=('Helvetica', 14, 'bold'))  # Position headers

    # Initialize student_id_entry as StringVar
    student_id_entry = tk.StringVar()

    # This will hold the mapping from candidate_id to partylist_id
    candidate_partylist_map = {}

    def switch_frame(new_frame_func):
        for widget in window.winfo_children():
            widget.destroy()
        new_frame_func()

    def on_login():
        student_id = student_id_entry.get().strip()
        if not student_id:
            messagebox.showerror("Input Error", "Please enter your School ID to login.")
            return
        student_data = login_user(student_id)
        if student_data:
            messagebox.showinfo("Login Success", f"Welcome, {student_data['first_name']}!")
            switch_frame(lambda: voting_frame(student_data))
        else:
            messagebox.showerror("Login Failed", "Invalid School ID.")

    # Updated registration_frame with additional fields
    def registration_frame():
        frame = ttk.Frame(window, padding=40)
        frame.pack(expand=True, fill='both')

        ttk.Label(frame, text="Register", font=('Helvetica', 24, 'bold')).pack(pady=20)

        form_frame = ttk.Frame(frame)
        form_frame.pack(pady=10)

        # Define all necessary StringVars
        student_id_var = tk.StringVar()
        first_name_var = tk.StringVar()
        middle_name_var = tk.StringVar()
        last_name_var = tk.StringVar()
        suffix_name_var = tk.StringVar()
        year_level_var = tk.StringVar()
        department_var = tk.StringVar()
        course_var = tk.StringVar()

        # Labels and Entries
        labels = [
            ("School ID:", student_id_var, "Enter your valid School ID"),
            ("First Name:", first_name_var, "Enter your First Name"),
            ("Middle Name:", middle_name_var, "Enter your Middle Name"),
            ("Last Name:", last_name_var, "Enter your Last Name"),
            ("Suffix Name:", suffix_name_var, "Enter your Suffix Name (e.g., Jr., Sr.) or N/A"),
        ]

        for idx, (label_text, var, tooltip_text) in enumerate(labels):
            ttk.Label(form_frame, text=label_text, font=('Helvetica', 14)).grid(row=idx, column=0, pady=5, sticky='e')
            entry = ttk.Entry(form_frame, textvariable=var, font=('Helvetica', 14), width=30)
            entry.grid(row=idx, column=1, pady=5, padx=10)
            if idx == 0:
                entry.focus()  # Focus on School ID

        # Year Level
        ttk.Label(form_frame, text="Year Level:", font=('Helvetica', 14)).grid(row=5, column=0, pady=10, sticky='e')
        year_levels = ["1", "2", "3", "4"]
        year_level_combo = ttk.Combobox(form_frame, textvariable=year_level_var, values=year_levels, state='readonly', font=('Helvetica', 14), width=28)
        year_level_combo.grid(row=5, column=1, pady=10, padx=10)
        year_level_combo.set("Select Year Level")

        # Department
        ttk.Label(form_frame, text="Department:", font=('Helvetica', 14)).grid(row=6, column=0, pady=10, sticky='e')
        departments = fetch_departments()
        department_names = [dept['department_name'] for dept in departments]
        department_combo = ttk.Combobox(form_frame, textvariable=department_var, values=department_names, state='readonly', font=('Helvetica', 14), width=28)
        department_combo.grid(row=6, column=1, pady=10, padx=10)
        department_combo.set("Select Department")

        # Course
        ttk.Label(form_frame, text="Course:", font=('Helvetica', 14)).grid(row=7, column=0, pady=10, sticky='e')
        course_combo = ttk.Combobox(form_frame, textvariable=course_var, values=[], state='readonly', font=('Helvetica', 14), width=28)
        course_combo.grid(row=7, column=1, pady=10, padx=10)
        course_combo.set("Select Course")

        # Function to update courses based on selected department
        def update_courses(event):
            selected_department = department_var.get()
            department_id = None
            for dept in departments:
                if dept['department_name'] == selected_department:
                    department_id = dept['department_id']
                    break
            if department_id:
                courses = fetch_courses(department_id)
                course_names = [course['course_name'] for course in courses]
                course_combo['values'] = course_names
                course_combo.set("Select Course")
            else:
                course_combo['values'] = []
                course_combo.set("Select Course")

        # Bind the department selection to update courses
        department_combo.bind("<<ComboboxSelected>>", update_courses)

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=30)

        ttk.Button(button_frame, text="Register", command=lambda: on_register_extended(
            student_id_var.get(),
            first_name_var.get(),
            middle_name_var.get(),
            last_name_var.get(),
            suffix_name_var.get(),
            year_level_var.get(),
            department_var.get(),
            course_var.get()
        ), bootstyle='success').grid(row=0, column=0, padx=20)
        ttk.Button(button_frame, text="Back to Login", command=lambda: switch_frame(login_frame), bootstyle='secondary').grid(row=0, column=1, padx=20)

    def login_frame():
        frame = ttk.Frame(window, padding=40)
        frame.pack(expand=True, fill='both')

        ttk.Label(frame, text="Login", font=('Helvetica', 24, 'bold')).pack(pady=30)

        form_frame = ttk.Frame(frame)
        form_frame.pack(pady=10)

        ttk.Label(form_frame, text="School ID:", font=('Helvetica', 14)).grid(row=0, column=0, pady=10, sticky='e')
        entry = ttk.Entry(form_frame, textvariable=student_id_entry, font=('Helvetica', 14), width=30)
        entry.grid(row=0, column=1, pady=10, padx=10)
        entry.focus()

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=30)

        ttk.Button(button_frame, text="Login", command=on_login, bootstyle='primary').grid(row=0, column=0, padx=20)
        ttk.Button(button_frame, text="Register", command=lambda: switch_frame(registration_frame), bootstyle='info').grid(row=0, column=1, padx=20)

    def voting_frame(student_data):
        student_db_id = student_data['id']
        # Main Frame
        frame = ttk.Frame(window, padding=20)
        frame.pack(fill='both', expand=True)

        # Header with "Voting List" and "Logout" button
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill='x', pady=10)

        # Display Student's Name in the Header
        student_name = f"{student_data['first_name']} {student_data['middle_name']} {student_data['last_name']}"
        if student_data['suffix_name']:
            student_name += f" {student_data['suffix_name']}"
        
        ttk.Label(header_frame, text=f"Voting List - {student_name}", font=('Helvetica', 24, 'bold')).pack(side='left', padx=10)
        ttk.Button(header_frame, text="Logout", command=lambda: switch_frame(login_frame), bootstyle='danger-outline').pack(side='right', padx=10)

        # Display additional student info
        ttk.Label(header_frame, text=f"Department: {student_data['department_name']} | Course: {student_data['course_name']} | Year Level: {student_data['year_level']}", font=('Helvetica', 12)).pack(side='left', padx=10, pady=5)

        # Main Content Frame with two columns
        content_frame = ttk.Frame(frame)
        content_frame.pack(fill='both', expand=True, pady=10)

        # Left Column: Voting List
        voting_list_frame = ttk.LabelFrame(content_frame, text="Voting List", padding=15)
        voting_list_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))

        # Right Column: Platform Display
        platform_frame = ttk.LabelFrame(content_frame, text="Platform", padding=15)
        platform_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))

        # Create a scrollable frame for the voting list
        scrollable = ScrollableFrame(voting_list_frame)
        scrollable.pack(fill='both', expand=True)

        voting_vars = {}
        positions, candidate_partylist_map_local = fetch_candidates()

        if not positions:
            ttk.Label(scrollable.scrollable_frame, text="No positions available for voting.", font=('Helvetica', 16)).pack(pady=20)
            return

        # Update the global mapping
        candidate_partylist_map.update(candidate_partylist_map_local)

        # Retrieve all votes once to minimize database calls
        all_votes = get_all_votes(student_db_id)
        # Create a dictionary with position_id as keys for easier access
        votes_dict = {vote['position_id']: vote for vote in all_votes}

        # Function to display the platform in the right column
        def display_platform(candidate_id):
            # Clear the platform frame
            for widget in platform_frame.winfo_children():
                widget.destroy()
            if candidate_id:
                connection = connect_to_db()
                if connection:
                    try:
                        cursor = connection.cursor(dictionary=True)
                        query = "SELECT platform FROM candidates WHERE candidate_id = %s"
                        cursor.execute(query, (candidate_id,))
                        result = cursor.fetchone()
                        platform_text = result['platform'] if result and result['platform'] else "No platform information available."
                        # If platform is stored as JSON string, you might need to parse it
                        # For simplicity, assuming it's a plain string
                        ttk.Label(platform_frame, text=platform_text, font=('Helvetica', 12), wraplength=400, justify='left').pack(pady=10)
                    except Error as e:
                        messagebox.showerror("Database Error", f"Failed to retrieve platform: {e}")
                    finally:
                        cursor.close()
                        connection.close()
            else:
                ttk.Label(platform_frame, text="Select a candidate to view their platform.", font=('Helvetica', 12), wraplength=400, justify='left').pack(pady=10)

        for position in positions:
            position_id = position['position_id']
            position_name = position['position_name']
            candidates = position['candidates']

            position_frame_inner = ttk.LabelFrame(scrollable.scrollable_frame, text=position_name, padding=15)
            position_frame_inner.pack(fill='x', padx=10, pady=10)

            # Retrieve vote details if already voted
            vote_info = votes_dict.get(position_id)
            if vote_info:
                # Load and display the image from URL
                image_url = "https://i.imgflip.com/5zbwfe.gif"  # Replace with actual image URL or candidate's image URL
                try:
                    response = requests.get(image_url)
                    response.raise_for_status()
                    image_data = BytesIO(response.content)
                    image = Image.open(image_data).resize((90, 90), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(image)  # Ensure `photo` stays in scope
                except requests.RequestException:
                    # Use a placeholder if the image cannot be fetched
                    photo = None

                # Main Frame for the horizontal card layout within `position_frame_inner`
                card_frame = ttk.Frame(position_frame_inner)
                card_frame.pack(pady=10, padx=10, fill="x", expand=True)

                if photo:
                    # Display the image on the left side
                    image_label = ttk.Label(card_frame, image=photo)
                    image_label.image = photo  # Keep a reference to avoid garbage collection
                    image_label.grid(row=0, column=0, rowspan=4, padx=(10, 20), pady=10, sticky='nw')

                # Name label
                name_label = ttk.Label(card_frame, text=vote_info['candidate_name'], font=("Helvetica", 14, "bold"))
                name_label.grid(row=0, column=1, sticky="w")

                # College label
                college_label = ttk.Label(card_frame, text=vote_info['department_name'], font=("Helvetica", 10), foreground="gray")
                college_label.grid(row=1, column=1, sticky="w")

                # Partylist name label
                partylist_name_label = ttk.Label(card_frame, text=vote_info['partylist_name'] if vote_info['partylist_name'] else "Independent", font=("Helvetica", 10), foreground="gray")
                partylist_name_label.grid(row=2, column=1, sticky="w", pady=(5, 10))

                # Voted at label
                voted_at_label = ttk.Label(card_frame, text=f"Voted at: {vote_info['voted_at']}", font=("Helvetica", 8), foreground="gray")
                voted_at_label.grid(row=3, column=1, sticky="w", padx=10)

                # Platform text
                platform_text = vote_info['platform'] if vote_info['platform'] else "No platform information available."
                ttk.Label(card_frame, text=platform_text, font=('Helvetica', 10), wraplength=400, justify='left').grid(row=4, column=0, columnspan=2, sticky='w', padx=10, pady=(5, 10))

                # Skip voting options since already voted
                continue

            candidate_var = tk.StringVar()
            voting_vars[position_id] = candidate_var

            for candidate in candidates:
                candidate_id = candidate['candidate_id']
                candidate_name = candidate['candidate_name']
                partylist_name = candidate['partylist_name'] if candidate['partylist_name'] else "Independent"

                rb_text = f"{candidate_name} ({partylist_name})"
                
                # Styled Radiobutton to look like a card
                rb = ttk.Radiobutton(
                    position_frame_inner, 
                    text=rb_text, 
                    variable=candidate_var, 
                    value=str(candidate_id), 
                    command=lambda cand_id=candidate_id: display_platform(cand_id),
                    style="Card.TRadiobutton"  # Apply a custom style
                )
                rb.pack(anchor='w', pady=5, padx=10, ipadx=10, ipady=10)  # Padding to mimic card spacing

        # Define on_vote inside voting_frame to access voting_vars
        def on_vote():
            votes = []
            for position_id, candidate_var in voting_vars.items():
                candidate_id = candidate_var.get()
                if candidate_id:
                    votes.append({
                        'candidate_id': int(candidate_id),
                        'position_id': position_id
                    })
            if not votes:
                messagebox.showwarning("No Selection", "Please select at least one candidate to vote.")
                return
            submit_vote(student_db_id, votes, candidate_partylist_map)
            switch_frame(login_frame)

        # Submit and Logout Buttons (Already present in the header and at the bottom)
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=20)

        # Check if the user has already voted for all positions
        connection = connect_to_db()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM positions")
                total_positions = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(DISTINCT position_id) FROM votes WHERE student_id = %s", (student_db_id,))
                voted_positions = cursor.fetchone()[0]
                if voted_positions < total_positions:
                    ttk.Button(button_frame, text="Submit Vote", command=on_vote, bootstyle='success-outline').grid(row=0, column=0, padx=20)
                else:
                    ttk.Label(button_frame, text="You have voted for all positions.", font=('Helvetica', 12, 'bold'), foreground='green').grid(row=0, column=0, padx=20)
            except Error as e:
                messagebox.showerror("Database Error", f"Failed to verify voting status: {e}")
            finally:
                cursor.close()
                connection.close()

    # Start with login frame
    login_frame()
    window.mainloop()

if __name__ == "__main__":
    create_gui()
