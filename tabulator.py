import json
from tabulate import tabulate

def display_timetable(timetable_json):
    # Load the timetable data
    timetable = json.loads(timetable_json) if isinstance(timetable_json, str) else timetable_json
    
    # Define days and periods (5 days × 8 periods = 40 slots)
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods_per_day = 8

    for class_name, slots in timetable.items():
        print(f"\n📅 TIMETABLE FOR {class_name.upper()}")
        print("=" * 50)
        
        # Initialize an empty timetable grid
        table = []
        for day in days:
            for period in range(1, periods_per_day + 1):
                slot = days.index(day) * periods_per_day + (period - 1)
                subjects = slots.get(str(slot), [])  # Get subject(s) for this slot
                subject = ", ".join(subjects) if subjects else "Free"
                table.append([day, period, subject])
        
        # Print as a formatted table
        print(tabulate(table, headers=["Day", "Period", "Subject"], tablefmt="grid"))
        print("\n")

# Load your JSON file
with open("timetable_output.json", "r") as f:
    timetable_data = json.load(f)

# Display the timetable
display_timetable(timetable_data)