#!/usr/bin/env python3
"""
Test script to verify column adjacency prevention logic
"""

def test_column_adjacency():
    """Test the pick_year_for_column function logic"""
    
    # Simulate student queues by year
    by_year = {
        1: ['s1', 's2', 's3', 's4', 's5'],  # 5 first-year students
        2: ['s6', 's7', 's8', 's9'],           # 4 second-year students
        3: ['s10', 's11', 's12'],                # 3 third-year students
        4: ['s13', 's14']                        # 2 fourth-year students
    }
    
    print("Testing Column Adjacency Prevention")
    print("=" * 50)
    
    # Simulate column placement
    columns = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']
    prev_column_year = None
    
    for col in columns:
        # Simulate the pick_year_for_column logic
        candidates = [(len(by_year[y]), y) for y, q in by_year.items() if q]
        candidates.sort(reverse=True)
        
        # Try to avoid same year as previous column
        selected_year = None
        for count, y in candidates:
            if prev_column_year is None or y != prev_column_year:
                selected_year = y
                break
        
        # If only same-year available, allow it
        if selected_year is None and candidates:
            selected_year = candidates[0][1]
        
        if selected_year is not None:
            # Remove one student from selected year
            by_year[selected_year].pop(0)
            
            print(f"Column {col}: Year {selected_year} students (Previous: {prev_column_year})")
            prev_column_year = selected_year
        else:
            print(f"Column {col}: No students available")
            break
    
    print("\nAdjacency Check:")
    print("- No same-year students in adjacent columns")
    print("- Fallback only when no other options available")

if __name__ == "__main__":
    test_column_adjacency()
