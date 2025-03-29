import streamlit as st
import json
import pandas as pd
from ortools.sat.python import cp_model
from collections import defaultdict

# Set page config
st.set_page_config(page_title="Timetable Generator", layout="wide")

# Title and description
st.title("🏫 School Timetable Generator")
st.markdown("""
This tool generates optimal timetables considering:
- Teacher availability
- Classroom constraints
- Subject requirements
""")

def solve_timetable(data, periods_per_day=8):
    DAYS = 5  # Monday to Friday
    SLOTS = DAYS * periods_per_day
    classes = data.get("classes", [])
    subjects = {s["Subject"]: s["Periods"] for s in data.get("subjects", [])}
    teachers = {t["Subject"].strip(): t["Teacher"] for t in data.get("teachers", [])}

    # Error checks
    missing_teachers = [subject for subject in subjects if subject not in teachers]
    if missing_teachers:
        return {"status": "fail", "message": f"No teachers assigned for subjects: {', '.join(missing_teachers)}"}

    if not classes:
        return {"status": "fail", "message": "No classes defined in the input data."}

    for class_info in classes:
        if not class_info.get("subjects"):
            return {"status": "fail", "message": f"Class {class_info['class']} has no subjects assigned."}

    for subject, periods in subjects.items():
        if periods > SLOTS:
            return {"status": "fail", "message": f"Subject '{subject}' requires {periods} periods, but only {SLOTS} slots are available."}

    # Create model
    model = cp_model.CpModel()

    # Variables: schedule[class][subject][slot]
    schedule = {}
    for c in classes:
        class_name = c["class"]
        schedule[class_name] = {}
        for subject in c["subjects"]:
            if subject not in subjects:
                return {"status": "fail", "message": f"Subject '{subject}' in class '{class_name}' is not defined in subjects list."}
            schedule[class_name][subject] = [
                model.NewBoolVar(f"{class_name}_{subject}_slot{s}") for s in range(SLOTS)
            ]

    # Hard constraints
    for c in classes:
        class_name = c["class"]
        for subject in c["subjects"]:
            model.Add(sum(schedule[class_name][subject]) == subjects[subject])
        
        for s in range(SLOTS):
            model.AddAtMostOne(schedule[class_name][subject][s] for subject in c["subjects"])

    # Teacher conflicts
    teacher_subjects = defaultdict(list)
    for subject, teacher in teachers.items():
        teacher_subjects[teacher].append(subject)

    for teacher, subs in teacher_subjects.items():
        for s in range(SLOTS):
            model.AddAtMostOne(
                schedule[c["class"]][subject][s]
                for c in classes if subject in c["subjects"] and subject in subs
            )

    # Soft constraints
    consecutive_penalties = []
    other_penalties = []

    for c in classes:
        class_name = c["class"]

        # 1. Penalty for consecutive same-subject periods (3x weight)
        for s in range(SLOTS - 1):
            for subject in c["subjects"]:
                penalty = model.NewBoolVar(f"penalty_consec_{class_name}_{subject}_slot{s}")
                model.AddBoolAnd([
                    schedule[class_name][subject][s],
                    schedule[class_name][subject][s + 1]
                ]).OnlyEnforceIf(penalty)
                consecutive_penalties.append(penalty)

        # 2. Penalty for same period across days (1x weight)
        for period in range(periods_per_day):
            for subject in c["subjects"]:
                daily_slots = [day * periods_per_day + period for day in range(DAYS)]
                repeat_penalty = model.NewBoolVar(f"penalty_repeat_{class_name}_{subject}_period{period}")
                model.Add(sum(schedule[class_name][subject][slot] for slot in daily_slots) > 1).OnlyEnforceIf(repeat_penalty)
                other_penalties.append(repeat_penalty)

    # Weighted objective
    model.Minimize(3 * sum(consecutive_penalties) + sum(other_penalties))

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        timetable = {}
        free_periods = {}
        actual_consecutives = 0
        
        for c in classes:
            class_name = c["class"]
            timetable[class_name] = {str(s): [] for s in range(SLOTS)}
            
            # Build timetable
            for subject in c["subjects"]:
                for s in range(SLOTS):
                    if solver.Value(schedule[class_name][subject][s]):
                        timetable[class_name][str(s)].append(subject)
            
            # Count actual consecutive periods
            class_consecutives = 0
            for s in range(SLOTS - 1):
                current_slot = timetable[class_name][str(s)]
                next_slot = timetable[class_name][str(s + 1)]
                
                if current_slot and next_slot and current_slot[0] == next_slot[0]:
                    class_consecutives += 1
            
            actual_consecutives += class_consecutives
            
            # Count free periods
            free_count = sum(1 for s in range(SLOTS) if not timetable[class_name][str(s)])
            free_periods[class_name] = free_count
        
        return {
            "status": "success",
            "timetable": timetable,
            "free_periods": free_periods,
            "consecutive_repeats": actual_consecutives,
            "solver_score": solver.ObjectiveValue(),
            "periods_per_day": periods_per_day,
            "classes": [c["class"] for c in classes]
        }
    else:
        return {"status": "fail", "message": "No feasible solution. Try adjusting the constraints."}

def get_timetable_data(timetable, class_name, periods_per_day):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods = [f"Period {i+1}" for i in range(periods_per_day)]
    
    data = []
    for day_idx, day in enumerate(days):
        row = {"Day": day}
        for period in range(periods_per_day):
            slot = day_idx * periods_per_day + period
            subjects = timetable[class_name].get(str(slot), [])
            row[periods[period]] = ", ".join(subjects) if subjects else "Free"
        data.append(row)
    
    return pd.DataFrame(data).set_index("Day")

# Main app logic
if 'timetable_data' not in st.session_state:
    st.session_state.timetable_data = None

with st.sidebar:
    st.header("Configuration")
    periods_per_day = st.number_input("Periods per day", min_value=1, max_value=12, value=8, help="Number of periods in each school day")
    uploaded_file = st.file_uploader("Upload JSON Data", type=["json"])
    
    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            if st.button("Generate Timetable"):
                with st.spinner("Generating optimal timetable..."):
                    result = solve_timetable(data, periods_per_day=periods_per_day)
                    st.session_state.timetable_data = result
                    if result["status"] == "success":
                        st.success("Timetable generated!")
                    else:
                        st.error(result["message"])
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")

# Display results
if st.session_state.timetable_data and st.session_state.timetable_data["status"] == "success":
    result = st.session_state.timetable_data
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Consecutive Repeats", result["consecutive_repeats"])
    with col2:
        st.metric("Total Classes", len(result["classes"]))
    with col3:
        st.metric("Periods per Day", result["periods_per_day"])
    
    # Free periods chart
    st.subheader("Free Periods Distribution")
    free_df = pd.DataFrame.from_dict(result["free_periods"], orient="index", columns=["Free Periods"])
    st.bar_chart(free_df)
    
    # Class selector
    st.subheader("Timetable Viewer")
    selected_class = st.selectbox("Select Class", result["classes"])
    
    # Display timetable with dark theme
    df = get_timetable_data(result["timetable"], selected_class, result["periods_per_day"])
    
    st.markdown("""
    <style>
        .stDataFrame div[data-testid="stDataFrame"] {
            background-color: transparent !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.dataframe(
        df.style.applymap(
            lambda x: 'background-color: #2d3741; color: #a6b3bf' if x == "Free" 
                     else 'background-color: #1e2937; color: #f0f2f6'
        ).set_table_styles([
            {'selector': 'th',
             'props': [('background-color', '#0e1117'), ('color', 'white'),
                      ('border', '1px solid #3d4b5d')]},
            {'selector': 'td',
             'props': [('border', '1px solid #3d4b5d')]}
        ]),
        height=275,
        use_container_width=True
    )
    
    # Download buttons
    st.download_button(
        label="Download Timetable (JSON)",
        data=json.dumps(result["timetable"], indent=2),
        file_name="timetable.json",
        mime="application/json"
    )
    
    st.download_button(
        label="Download as CSV",
        data=df.reset_index().to_csv(index=False),
        file_name=f"timetable_{selected_class}.csv",
        mime="text/csv"
    )

elif st.session_state.timetable_data and st.session_state.timetable_data["status"] == "fail":
    st.error("❌ Failed to generate timetable. Please check your constraints.")

# Sample data
with st.expander("Need sample data?"):
    st.download_button(
        label="Download Sample JSON",
        data=json.dumps({
            "classes": [
                {"class": "Grade 10A", "subjects": ["Math", "English", "Science"]},
                {"class": "Grade 10B", "subjects": ["Math", "History", "Art"]}
            ],
            "subjects": [
                {"Subject": "Math", "Periods": 5},
                {"Subject": "English", "Periods": 4},
                {"Subject": "Science", "Periods": 4},
                {"Subject": "History", "Periods": 3},
                {"Subject": "Art", "Periods": 2}
            ],
            "teachers": [
                {"Teacher": "Mr. Smith", "Subject": "Math"},
                {"Teacher": "Ms. Johnson", "Subject": "English"},
                {"Teacher": "Dr. Brown", "Subject": "Science"},
                {"Teacher": "Prof. Lee", "Subject": "History"},
                {"Teacher": "Mrs. Davis", "Subject": "Art"}
            ]
        }, indent=2),
        file_name="sample_timetable_data.json",
        mime="application/json"
    )