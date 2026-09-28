import pandas as pd
import json
import os
import urllib.request

def main():
    print("Loading datasets...")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dataset_dir = os.path.join(base_dir, "Dataset")
    
    details_path = os.path.join(dataset_dir, "train_details.csv")
    sched_path = os.path.join(dataset_dir, "combined_schedule.csv")
    etrain_path = os.path.join(dataset_dir, "etrain_delays.csv")
    stn_path = os.path.join(dataset_dir, "station_full_names.csv")
    demo_path = os.path.join(base_dir, "frontend", "src", "assets", "train-list.json")
    out_train_path = os.path.join(base_dir, "frontend", "src", "assets", "train-list.json")
    out_coords_path = os.path.join(base_dir, "frontend", "src", "assets", "station-coordinates.json")

    df_details = pd.read_csv(details_path)
    df_sched = pd.read_csv(sched_path, low_memory=False)
    df_etrain = pd.read_csv(etrain_path)
    df_stn = pd.read_csv(stn_path)

    print("Building station map...")
    stn_map = dict(zip(
        df_stn['station_name'].astype(str).str.strip().str.upper(),
        df_stn['station_full_name'].astype(str).str.strip()
    ))

    def norm(x):
        try:
            return int(str(x).strip())
        except:
            return None

    # 1. Fetch & Build Station Coordinates
    print("Downloading / building station coordinates...")
    stn_coords = {}
    try:
        url = "https://raw.githubusercontent.com/datameet/railways/master/stations.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for f in data.get('features', []):
                p = f.get('properties') or {}
                g = f.get('geometry') or {}
                code = p.get('code')
                coords = g.get('coordinates')
                if code and coords and len(coords) >= 2:
                    lon, lat = coords[0], coords[1]
                    stn_coords[str(code).strip().upper()] = [round(lat, 4), round(lon, 4)]
        print(f"Downloaded {len(stn_coords)} station coordinates from datameet/railways.")
    except Exception as e:
        print(f"Could not download stations.json: {e}")

    # Standard Indian Railways station code aliases & key coordinates
    aliases = {
        'MMCT': 'BCT',
        'DDU':  'MGS',
        'PRYJ': 'ALD',
        'AY':   'FD',
        'VGLJ': 'JHS',
        'SMVB': 'BYPL',
        'NZM':  'HNZM',
        'CSMT': 'CSTM',
        'SVDK': 'UHP',
    }
    for new_c, old_c in aliases.items():
        if old_c in stn_coords and new_c not in stn_coords:
            stn_coords[new_c] = stn_coords[old_c]

    # Explicit accurate coordinates for major terminals and corridor stations
    known_overrides = {
        'NDLS': [28.6419, 77.2194],
        'MMCT': [18.9690, 72.8205],
        'BCT':  [18.9690, 72.8205],
        'CSMT': [18.9402, 72.8357],
        'CSTM': [18.9402, 72.8357],
        'HWH':  [22.5840, 88.3426],
        'MAS':  [13.0827, 80.2755],
        'SBC':  [12.9781, 77.5695],
        'ADI':  [23.0232, 72.5996],
        'PUNE': [18.5284, 73.8743],
        'MTJ':  [27.4924, 77.6737],
        'AGC':  [27.1592, 77.9776],
        'GWL':  [26.2183, 78.1828],
        'JHS':  [25.4484, 78.5685],
        'BPL':  [23.2599, 77.4126],
        'ET':   [22.6136, 77.7600],
        'BSL':  [21.0393, 75.7849],
        'KYN':  [19.2437, 73.1355],
    }
    stn_coords.update(known_overrides)

    with open(out_coords_path, 'w', encoding='utf-8') as f:
        json.dump(stn_coords, f, ensure_ascii=False)
    print(f"Saved {len(stn_coords)} station coordinates to {out_coords_path}")

    # 2. Process schedules for origin, destination, and complete list of stops
    print("Processing schedules...")
    df_sched['t_num'] = df_sched['train_no'].apply(norm)
    df_sched = df_sched.dropna(subset=['t_num'])
    df_sched['t_num'] = df_sched['t_num'].astype(int)
    df_sched['station_no'] = pd.to_numeric(df_sched['station_no'], errors='coerce')
    df_sched = df_sched.sort_values(['t_num', 'station_no'])

    origins = df_sched.groupby('t_num').first()['station_name'].to_dict()
    destinations = df_sched.groupby('t_num').last()['station_name'].to_dict()
    train_stops = df_sched.groupby('t_num')['station_name'].apply(
        lambda s: [str(x).strip().upper() for x in s.dropna() if str(x).strip()]
    ).to_dict()

    # Load existing demo trains
    with open(demo_path, 'r', encoding='utf-8') as f:
        demo_trains = json.load(f)

    trains_dict = {}

    # Seed with existing demo corridor trains
    for t in demo_trains:
        t_num = norm(t['train_no'])
        if not t_num:
            continue
        orig = str(origins.get(t_num, '')).strip().upper()
        dest = str(destinations.get(t_num, '')).strip().upper()
        
        if not orig and ' → ' in t.get('route', ''):
            parts = t['route'].split(' → ')
            orig = parts[0].strip().upper()
            dest = parts[1].strip().upper()

        route = f"{orig} → {dest}" if orig and dest else t.get('route', '--')
        stops = train_stops.get(t_num, [orig, dest] if orig and dest else [])

        trains_dict[t_num] = {
            'train_no': t_num,
            'train_name': t['train_name'],
            'type_code': t.get('type_code', 'EXP-TRAINS'),
            'route': route,
            'origin': orig,
            'destination': dest,
            'origin_name': stn_map.get(orig, ''),
            'destination_name': stn_map.get(dest, ''),
            'stops': stops,
            'is_corridor': True
        }

    # Process all trains in train_details.csv
    print(f"Processing {len(df_details)} rows from train_details.csv...")
    for _, row in df_details.iterrows():
        t_num = norm(row['train_no'])
        if not t_num:
            continue
        orig = str(origins.get(t_num, '')).strip().upper() if t_num in origins else ''
        dest = str(destinations.get(t_num, '')).strip().upper() if t_num in destinations else ''
        route = f"{orig} → {dest}" if orig and dest else '--'
        stops = train_stops.get(t_num, [orig, dest] if orig and dest else [])

        if t_num not in trains_dict:
            trains_dict[t_num] = {
                'train_no': t_num,
                'train_name': str(row['train_name']).strip(),
                'type_code': str(row['type_code']).strip() if pd.notna(row['type_code']) else 'EXP-TRAINS',
                'route': route,
                'origin': orig,
                'destination': dest,
                'origin_name': stn_map.get(orig, ''),
                'destination_name': stn_map.get(dest, ''),
                'stops': stops,
                'is_corridor': False
            }

    # Process etrain_delays.csv
    print(f"Processing {len(df_etrain)} rows from etrain_delays.csv...")
    for _, row in df_etrain.iterrows():
        t_num = norm(row['train_number'])
        if not t_num:
            continue
        orig = str(origins.get(t_num, '')).strip().upper() if t_num in origins else ''
        dest = str(destinations.get(t_num, '')).strip().upper() if t_num in destinations else ''
        route = f"{orig} → {dest}" if orig and dest else '--'
        stops = train_stops.get(t_num, [orig, dest] if orig and dest else [])

        if t_num not in trains_dict:
            trains_dict[t_num] = {
                'train_no': t_num,
                'train_name': str(row['train_name']).strip(),
                'type_code': 'EXP-TRAINS',
                'route': route,
                'origin': orig,
                'destination': dest,
                'origin_name': stn_map.get(orig, ''),
                'destination_name': stn_map.get(dest, ''),
                'stops': stops,
                'is_corridor': False
            }

    # Filter to only keep trains with at least one intermediate station (>= 3 distinct stops)
    # Excludes trains with no intermediate stops (only source & destination or incomplete data)
    raw_count = len(trains_dict)
    all_trains = [
        t for t in trains_dict.values()
        if len(t.get('stops', [])) >= 3 and len(set(t.get('stops', []))) >= 3
    ]
    excluded_count = raw_count - len(all_trains)
    print(f"Total compiled: {raw_count}. Excluded {excluded_count} trains with no intermediate stations.")
    print(f"Retained {len(all_trains)} trains with valid intermediate stops.")

    with open(out_train_path, 'w', encoding='utf-8') as f:
        json.dump(all_trains, f, ensure_ascii=False, indent=2)

    file_size_kb = os.path.getsize(out_train_path) / 1024
    print(f"Successfully saved {len(all_trains)} trains to {out_train_path} ({file_size_kb:.1f} KB)")

if __name__ == "__main__":
    main()
