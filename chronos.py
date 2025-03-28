import json
from ortools.sat.python import cp_model
from collections import defaultdict

# Load input data
with open("timetable_data.json", "r") as file:
    data = json.load(file)

# Parameters
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

# ===== HARD CONSTRAINTS =====
for c in classes:
    class_name = c["class"]
    for subject in c["subjects"]:
        # Correct number of periods per subject
        model.Add(sum(schedule[class_name][subject]) == subjects[subject])
    
    # No double-booking in a class
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

# ===== SOFT CONSTRAINT: Minimize consecutive repeats =====
penalties = []
for c in classes:
    class_name = c["class"]
    for s in range(SLOTS - 1):
        for subject in c["subjects"]:
            # Add penalty if subject repeats consecutively
            penalty = model.NewBoolVar(f"penalty_{class_name}_{subject}_slot{s}")
            model.AddBoolAnd([
                schedule[class_name][subject][s],
                schedule[class_name][subject][s + 1]
            ]).OnlyEnforceIf(penalty)
            penalties.append(penalty)

model.Minimize(sum(penalties))  # Objective: Minimize repeats

# ===== SOLVE & SAVE OUTPUT =====
solver = cp_model.CpSolver()
status = solver.Solve(model)

if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    timetable = {}
    for c in classes:
        class_name = c["class"]
        timetable[class_name] = {str(s): [] for s in range(SLOTS)}
        for subject in c["subjects"]:
            for s in range(SLOTS):
                if solver.Value(schedule[class_name][subject][s]):
                    timetable[class_name][str(s)].append(subject)
    
    # Save to JSON file
    with open("timetable_output.json", "w") as outfile:
        json.dump(timetable, outfile, indent=2)
    
    print("✅ Timetable generated successfully!")
    print(f"📊 Consecutive repeats: {solver.ObjectiveValue()}")
    print("💾 Saved to 'timetable_output.json'")
else:
    print("❌ No feasible solution found!")