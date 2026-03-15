#!/usr/bin/env python3
"""
Test script to verify the corrected column adjacency prevention logic
"""

def test_corrected_adjacency():
    """Test the exact logic implemented in the corrected algorithm"""
    
    # Simulate student queues by year
    by_year = {
        1: ['s1', 's2', 's3', 's4', 's5'],  # 5 first-year students
        2: ['s6', 's7', 's8', 's9'],           # 4 second-year students
        3: ['s10', 's11', 's12'],                # 3 third-year students
        4: ['s13', 's14']                        # 2 fourth-year students
    }
    
    print("Testing Corrected Column Adjacency Prevention")
    print("=" * 60)
    print("Implementing exact logic from allocation loop")
    print()
    
    # Simulate column placement for one row
    columns = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']
    previous_year_in_row = None
    allocation_log = []
    
    for col in columns:
        # Exact logic from the corrected algorithm
        selected_year = None
        
        # Get all available years with students
        available_years = [year for year, queue in by_year.items() if queue]
        
        if not available_years:
            break
        
        # Remove previous year from available options if it exists
        if previous_year_in_row is not None and previous_year_in_row in available_years:
            available_years.remove(previous_year_in_row)
        
        # If no years available after removing previous year, allow it back (edge case)
        if not available_years:
            available_years = [year for year, queue in by_year.items() if queue]
        
        # Pick year with most remaining students from available years
        selected_year = max(available_years, key=lambda y: len(by_year[y]))
        
        # Assign student from selected year
        student = by_year[selected_year].pop(0)
        
        allocation_log.append(f"Column {col}: Year {selected_year} student (Previous: {previous_year_in_row})")
        
        # Update for next column
        previous_year_in_row = selected_year
    
    # Print results
    for log in allocation_log:
        print(log)
    
    print("\n" + "=" * 60)
    print("VERIFICATION:")
    
    # Verify no same-year adjacency
    years_assigned = []
    for log in allocation_log:
        year = int(log.split("Year ")[1].split(" ")[0])
        years_assigned.append(year)
    
    adjacency_violations = 0
    for i in range(len(years_assigned) - 1):
        if years_assigned[i] == years_assigned[i + 1]:
            adjacency_violations += 1
            print(f"❌ VIOLATION: Column {chr(65+i)} and {chr(66+i)} both have Year {years_assigned[i]}")
    
    if adjacency_violations == 0:
        print("✅ SUCCESS: No same-year students in adjacent columns")
    
    print(f"\nTotal students allocated: {len(allocation_log)}")
    print(f"Adjacency violations: {adjacency_violations}")

def test_single_year_edge_case():
    """Test the single-year edge case with middle column avoidance"""
    
    print("\n" + "=" * 60)
    print("TESTING SINGLE-YEAR EDGE CASE")
    print("=" * 60)
    
    # Single-year scenario
    by_year = {
        1: ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8']  # 8 first-year students
    }
    
    total_rows = 6
    remaining_students = 8
    
    # Test column selection logic
    is_single_year = True
    middle_columns = ['B', 'E', 'H']
    preferred_columns = ['A', 'C', 'D', 'F', 'G', 'I']
    
    usable_capacity = total_rows * len(preferred_columns)  # 6 * 6 = 36
    
    print(f"Total students: {remaining_students}")
    print(f"Usable capacity without middle columns: {usable_capacity}")
    print(f"Middle columns to skip: {middle_columns}")
    print(f"Preferred columns: {preferred_columns}")
    
    if remaining_students <= usable_capacity:
        print("✅ Should skip middle columns B, E, H")
        needed_cols = (remaining_students + total_rows - 1) // total_rows  # ceil
        needed_cols = max(1, min(len(preferred_columns), needed_cols))
        columns_to_use = preferred_columns[:needed_cols]
        print(f"Columns to use: {columns_to_use}")
    else:
        print("❌ Would use all columns")

if __name__ == "__main__":
    test_corrected_adjacency()
    test_single_year_edge_case()
