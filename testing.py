import pandas as pd

# Load the GTFS data
stop_times_df = pd.read_csv('gtfs_data/stop_times.txt')  # Update the path
trips_df = pd.read_csv('gtfs_data/trips.txt')  # Update the path

# Step 1: Filter trips for Route 7
route_7_trip_ids = trips_df[trips_df['route_id'] == 7]['trip_id'].unique()

# Step 2: Check if any of these trips stop at Stop ID 4073
stops_at_4073 = stop_times_df[
    (stop_times_df['trip_id'].isin(route_7_trip_ids)) & 
    (stop_times_df['stop_id'] == '4072')  # Ensure '4073' is treated as a string
]

# Check if there are any matching stops
if not stops_at_4073.empty:
    print("Route 7 stops at King/Columbia (Stop ID 4073).")
else:
    print("Route 7 does NOT stop at King/Columbia (Stop ID 4073).")
