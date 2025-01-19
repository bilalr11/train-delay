from flask import Flask, render_template, request, send_file
import requests
from datetime import datetime, timedelta
import pandas as pd
import io
import os

app = Flask(__name__)

def format_time(time_str):
    """Convert time string from HHMM to HH:MM format"""
    if time_str == 'N/A':
        return time_str
    time_str = time_str.zfill(4)
    return f"{time_str[:2]}:{time_str[2:]}"

def calculate_arrival_delay(scheduled, expected):
    """Calculate arrival delay in minutes"""
    if scheduled == 'N/A' or expected == 'N/A':
        return 'N/A'
    
    try:
        scheduled_time = datetime.strptime(scheduled, '%H:%M')
        expected_time = datetime.strptime(expected, '%H:%M')
        
        scheduled_mins = scheduled_time.hour * 60 + scheduled_time.minute
        expected_mins = expected_time.hour * 60 + expected_time.minute
        
        if expected_mins < scheduled_mins:
            expected_mins += 24 * 60
            
        if expected_time>=scheduled_time:
            delay = expected_time - scheduled_time
        else:
            delay = datetime.now() - datetime.now()
            
        return delay.seconds // 60
    except ValueError:
        return 'N/A'

def get_train_services(api_user, api_pass, date):
    """Get train services between Huddersfield and Leeds for a specific date"""
    base_url = "https://api.rtt.io/api/v1"
    formatted_date = date.strftime("%Y/%m/%d")
    endpoint = f"/json/search/HUD/to/LDS/{formatted_date}"
    
    try:
        response = requests.get(
            f"{base_url}{endpoint}",
            auth=(api_user, api_pass)
        )
        response.raise_for_status()
        
        data = response.json()
        services = data.get('services')
        
        if services is None or not services:
            return []
            
        service_details = []
        for service in services:
            location_detail = service.get('locationDetail', {})
            
            service_info = {
                'date': date,
                'scheduled_arrival': format_time(location_detail.get('gbttBookedArrival', 'N/A')),
                'expected_arrival': format_time(location_detail.get('realtimeArrival', 'N/A')),
                'platform': location_detail.get('platform', 'N/A')
            }
            service_details.append(service_info)
            
        return service_details
            
    except Exception as e:
        print(f"Error for {formatted_date}: {e}")
        return []

def analyze_arrival_delays(df):
    """Analyze arrival delays and return statistics"""
    delays = {
        '15-29 mins': 0,
        '30-59 mins': 0,
        '60+ mins': 0,
        'N/A': 0
    }
    
    detailed_delays = []
    
    for idx, row in df.iterrows():
        delay = calculate_arrival_delay(row['scheduled_arrival'], row['expected_arrival'])
        
        if delay == 'N/A':
            delays['N/A'] += 1
        elif delay >= 60:
            delays['60+ mins'] += 1
        elif delay >= 30:
            delays['30-59 mins'] += 1
        elif delay >= 15:
            delays['15-29 mins'] += 1
            
        # Add to detailed delays if delayed
        if isinstance(delay, (int, float)) and delay >= 15:
            detailed_delays.append({
                'date': row['date'],
                'scheduled': row['scheduled_arrival'],
                'expected': row['expected_arrival'],
                'delay': delay,
                'platform': row['platform']
            })
    
    return delays, detailed_delays

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        api_user = "rttapi_bilalrx12"
        api_pass = "604cdf1c1e3aa50297ef5a27256b4fd590d085b8"
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        
        all_services = []
        current_date = start_date
        
        while current_date <= end_date:
            services = get_train_services(api_user, api_pass, current_date)
            all_services.extend(services)
            current_date += timedelta(days=1)
        
        if all_services:
            df = pd.DataFrame(all_services)
            df['date'] = pd.to_datetime(df['date']).dt.date
            
            delay_stats, detailed_delays = analyze_arrival_delays(df)
            
            return render_template('results.html', 
                                 delay_stats=delay_stats,
                                 detailed_delays=detailed_delays,
                                 services=df.to_dict('records'))
        else:
            return render_template('index.html', error="No services found for the specified date range")
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
