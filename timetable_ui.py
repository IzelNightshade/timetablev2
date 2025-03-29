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

# Solver function
def solve_timetable(data):
    SLOTS = 40  # 5 days × 8 periods
    classes = data["classes"]
    subjects = {s["Subject"]: s["Periods"] for s in data["subjects"]}
    teachers = {t["Subject"].strip(): t["Teacher"] for t in data["teachers"]}

    # Create model
    model = cp_model.CpModel()

    # Variables: schedule[class][subject][slot]
    schedule = {}
    for c in classes:
        class_name = c["class"]
        schedule[class_name] = {}
        for subject in c["subjects"]:
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

    # Soft constraint: Minimize consecutive repeats
    penalties = []
    for c in classes:
        class_name = c["class"]
        for s in range(SLOTS - 1):
            for subject in c["subjects"]:
                penalty = model.NewBoolVar(f"penalty_{class_name}_{subject}_slot{s}")
                model.AddBoolAnd([
                    schedule[class_name][subject][s],
                    schedule[class_name][subject][s + 1]
                ]).OnlyEnforceIf(penalty)
                penalties.append(penalty)

    model.Minimize(sum(penalties))

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        timetable = {}
        free_periods = {}
        
        for c in classes:
            class_name = c["class"]
            timetable[class_name] = {str(s): [] for s in range(SLOTS)}
            free_count = 0
            
            for subject in c["subjects"]:
                for s in range(SLOTS):
                    if solver.Value(schedule[class_name][subject][s]):
                        timetable[class_name][str(s)].append(subject)
            
            for s in range(SLOTS):
                if not timetable[class_name][str(s)]:
                    free_count += 1
            free_periods[class_name] = free_count
        
        return {
            "status": "success",
            "timetable": timetable,
            "free_periods": free_periods,
            "consecutive_repeats": solver.ObjectiveValue(),
            "classes": [c["class"] for c in classes]
        }
    else:
        return {"status": "fail", "message": "No feasible solution"}

# Timetable display function
def get_timetable_data(timetable, class_name):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods = [f"Period {i+1}" for i in range(8)]
    
    data = []
    for day_idx, day in enumerate(days):
        row = {"Day": day}
        for period in range(8):
            slot = day_idx * 8 + period
            subjects = timetable[class_name].get(str(slot), [])
            row[periods[period]] = ", ".join(subjects) if subjects else "Free"
        data.append(row)
    
    return pd.DataFrame(data).set_index("Day")

# Main app logic
if 'timetable_data' not in st.session_state:
    st.session_state.timetable_data = None

with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload JSON Data", type=["json"])
    
    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            if st.button("Generate Timetable"):
                with st.spinner("Generating optimal timetable..."):
                    result = solve_timetable(data)
                    st.session_state.timetable_data = result
                    st.success("Timetable generated!")
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")

# Display results
if st.session_state.timetable_data and st.session_state.timetable_data["status"] == "success":
    result = st.session_state.timetable_data
    
    # Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Consecutive Repeats", result["consecutive_repeats"])
    with col2:
        st.metric("Total Classes", len(result["classes"]))
    
    # Free periods chart
    st.subheader("Free Periods Distribution")
    free_df = pd.DataFrame.from_dict(result["free_periods"], orient="index", columns=["Free Periods"])
    st.bar_chart(free_df)
    
    # Class selector
    st.subheader("Timetable Viewer")
    selected_class = st.selectbox("Select Class", result["classes"])
    
    # Display timetable with dark theme
    df = get_timetable_data(result["timetable"], selected_class)
    
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
        height=275,  # Fixed height for 5 rows
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
            "classes": [{"class": "Grade 10A", "subjects": ["Math", "English"]}],
            "subjects": [{"Subject": "Math", "Periods": 5}, {"Subject": "English", "Periods": 4}],
            "teachers": [{"Teacher": "T1", "Subject": "Math"}, {"Teacher": "T2", "Subject": "English"}]
        }, indent=2),
        file_name="sample_timetable_data.json",
        mime="application/json"
    )