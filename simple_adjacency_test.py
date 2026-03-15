#!/usr/bin/env python3
"""
Simple test to verify adjacency prevention logic
"""

def test_adjacency():
    # Simulate student queues
    by_year = {
        1: ['s1', 's2', 's3', 's4', 's5'],
        2: ['s6', 's7', 's8', 's9'],
        3: ['s10', 's11', 's12'],
        4: ['s13', 's14']
    }
    
    print("Testing Column Adjacency Prevention")
    print("=" * 50)
    
    columns = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']
    previous_year_in_row = None
    allocation_log = []
    
    for col in columns:
        # Get available years
        available_years = [year for year, queue in by_year.items() if queue]
        
        if not available_years:
            break
        
        # Remove previous year if exists
        if previous_year_in_row is not None and previous_year_in_row in available_years:
            available_years.remove(previous_year_in_row)
        
        # Allow back if no options
        if not available_years:
            available_years = [year for year, queue in by_year.items() if queue]
        
        # Pick year with most students
        selected_year = max(available_years, key=lambda y: len(by_year[y]))
        
        # Assign student
        by_year[selected_year].pop(0)
        allocation_log.append(f"Column {col}: Year {selected_year} (Prev: {previous_year_in_row})")
        previous_year_in_row = selected_year
    
    # Print results
    for log in allocation_log:
        print(log)
    
    # Check violations
    years_assigned = []
    for log in allocation_log:
        year = int(log.split("Year ")[1].split(" ")[0])
        years_assigned.append(year)
    
    violations = 0
    for i in range(len(years_assigned) - 1):
        if years_assigned[i] == years_assigned[i + 1]:
            violations += 1
            print(f"VIOLATION: Column {chr(65+i)} and {chr(66+i)} both Year {years_assigned[i]}")
    
    if violations == 0:
        print("SUCCESS: No same-year adjacency!")
    
    print(f"Total allocated: {len(allocation_log)}, Violations: {violations}")

if __name__ == "__main__":
    test_adjacency()
