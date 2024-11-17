import pandas as pd
from datetime import datetime, timedelta, date  # [Added 'date' for handling current date]

class GRTSchedule:
    def __init__(self, gtfs_path='gtfs_data/'):
        self.gtfs_path = gtfs_path
        self.load_data()

    # Load the GTFS data into pandas dataframes
    def load_data(self):
        self.stops = pd.read_csv(self.gtfs_path + 'stops.txt')
        self.stop_times = pd.read_csv(self.gtfs_path + 'stop_times.txt')
        self.trips = pd.read_csv(self.gtfs_path + 'trips.txt')
        self.routes = pd.read_csv(self.gtfs_path + 'routes.txt')
        self.calendar_dates = pd.read_csv(self.gtfs_path + 'calendar_dates.txt')  # [Loaded 'calendar_dates.txt']

        # [Ensure 'stop_id' in stop_times is a string to match the mapping]
        self.stop_times['stop_id'] = self.stop_times['stop_id'].astype(str)  # [Added]

        self.prepare_data()

    # Prepare the data for use
    def prepare_data(self):
        # Strip whitespace from 'route_short_name' to avoid mismatches
        self.routes['route_short_name'] = self.routes['route_short_name'].astype(str).str.strip()

        # Normalize stop names by removing extra spaces around slashes and converting to lowercase
        self.stops['normalized_stop_name'] = self.stops['stop_name'].str.lower().str.replace(r'\s*/\s*', '/', regex=True)  # [Added normalization]

        # [Convert 'stop_id' to string to ensure consistent data types]
        self.stop_name_to_id = self.stops.set_index('normalized_stop_name')['stop_id'].astype(str).to_dict()  # [Modified]

        self.route_number_to_id = self.routes.set_index('route_short_name')['route_id'].to_dict()

        # Debugging: Print the route_number_to_id mapping
        print("Route Number to ID Mapping:")
        for route_num, route_id in self.route_number_to_id.items():
            print(f"Route {route_num}: {route_id}")

        # Determine active service IDs based on calendar_dates.txt
        self.active_service_ids = self.get_active_service_ids()  # [Determined active services]

    def get_active_service_ids(self):
        today = date.today()  # [Got today's date]
        today_str = today.strftime('%Y%m%d')  # [Formatted date as string]

        # Filter calendar_dates.txt for today's date
        services_today = self.calendar_dates[self.calendar_dates['date'] == int(today_str)]

        # Services with exception_type=1 are added (active)
        active_services = services_today[services_today['exception_type'] == 1]['service_id'].tolist()  # [Only exception_type=1 indicates added services]

        print(f"Active service IDs today ({today_str}): {active_services}")  # [Debugging]
        return set(active_services)

    def get_route_id(self, route_number):
        route_number = str(route_number).strip()
        route_id = self.route_number_to_id.get(route_number)
        print(f"Looking up Route Number: '{route_number}' -> Route ID: '{route_id}'")  # [Debugging]
        return route_id

    def get_stop_id(self, stop_name):
        # Normalize user input by removing spaces around slashes and converting to lowercase
        normalized_input = stop_name.lower().strip().replace(' / ', '/')
        normalized_input = ' '.join(normalized_input.split())  # [Remove extra spaces]
        stop_id = self.stop_name_to_id.get(normalized_input)
        print(f"Looking up Stop Name: '{stop_name}' -> Normalized: '{normalized_input}' -> Stop ID: '{stop_id}'")  # [Debugging]
        return stop_id

    def get_next_arrivals(self, route_number, stop_name, current_time=None, timezone_offset=0):
        # Returns the next arrival times for a desired bus and stop.

        if current_time is None:
            current_time = datetime.now()
        else:
            current_time = datetime.strptime(current_time, '%H:%M:%S')

        # Adjust for timezone
        current_time += timedelta(hours=timezone_offset)
        print(f"Current Time (adjusted): {current_time}")  # [Debugging]

        route_id = self.get_route_id(route_number)
        if not route_id:
            return f"Route {route_number} is not found."

        stop_id = self.get_stop_id(stop_name)
        if not stop_id:
            return f"Stop {stop_name} is not found."

        # Get trips for desired route and active services
        route_trips = self.trips[
            (self.trips['route_id'] == route_id) &
            (self.trips['service_id'].isin(self.active_service_ids))  # [Filtered by active services]
        ]
        print(f"Number of active trips for route {route_number}: {len(route_trips)}")  # [Debugging]

        if route_trips.empty:
            return f"No active trips found for Route {route_number} today."

        # Merge with stop_times to get times at stop
        route_stop_times = pd.merge(route_trips, self.stop_times, on='trip_id')
        stop_times_at_stop = route_stop_times[route_stop_times['stop_id'] == stop_id]
        print(f"Number of stop times for route {route_number} at stop '{stop_name}': {len(stop_times_at_stop)}")  # [Debugging]

        if stop_times_at_stop.empty:
            return f"No arrivals found for {route_number} at {stop_name}."

        # Convert arrival times into datetime 
        stop_times_at_stop['arrival_time'] = pd.to_datetime(stop_times_at_stop['arrival_time'], format='%H:%M:%S', errors='coerce').dt.time
        # Remove missing arrival times
        stop_times_at_stop = stop_times_at_stop.dropna(subset=['arrival_time'])
        print(f"Valid stop times after parsing: {len(stop_times_at_stop)}")  # [Debugging]

        # Get the next arrival times
        next_arrivals = []

        for i, row in stop_times_at_stop.iterrows():
            arrival_datetime = datetime.combine(current_time.date(), row['arrival_time'])
            # Times past midnight
            if arrival_datetime < current_time:
                arrival_datetime += timedelta(days=1)
            wait_time = (arrival_datetime - current_time).total_seconds() / 60
            if wait_time >= 0:
                next_arrivals.append((arrival_datetime.strftime('%H:%M'), wait_time))

        next_arrivals.sort(key=lambda x: x[1])

        print(f"Number of upcoming arrivals: {len(next_arrivals)}")  # [Debugging]

        if not next_arrivals:
            return f"There are no upcoming arrivals for {route_number} at {stop_name}."

        # Show the next 3 arrivals
        response = f"Next arrivals for bus {route_number} at {stop_name}:\n"
        for arrival_time, wait in next_arrivals[:3]:
            response += f"- {arrival_time} (in {int(wait)} minutes)\n"

        print("Response:", response)  # [Debugging]

        return response
