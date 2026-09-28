"""
build_railway_network.py
Extracts the strict physical railway track network of India from combined_schedule.csv
and station-coordinates.json.

Produces frontend/src/assets/railway-network.json containing:
- tracks: Array of [[lat1, lon1], [lat2, lon2]] for all 9,000 physical track segments across India.
- adj: Graph adjacency list for instantaneous shortest-path track routing in the browser.
"""

import json
import math
import os
import pandas as pd

def build():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    coords_path = os.path.join(base_dir, "frontend", "src", "assets", "station-coordinates.json")
    sched_path = os.path.join(base_dir, "Dataset", "combined_schedule.csv")
    out_path = os.path.join(base_dir, "frontend", "src", "assets", "railway-network.json")

    print(f"Loading station coordinates from {coords_path}...")
    with open(coords_path, "r", encoding="utf-8") as f:
        coords = json.load(f)

    print(f"Loading train schedules from {sched_path}...")
    df = pd.read_csv(sched_path, low_memory=False)

    print("Extracting physical station chains...")
    sequences = []
    for _, g in df.groupby("train_no"):
        stns = [str(s).strip().upper() for s in g.sort_values("station_no")["station_name"].tolist() if str(s).strip().upper() in coords]
        if len(stns) >= 2:
            sequences.append(stns)

    has_intermediate = set()
    for seq in sequences:
        for i in range(len(seq)):
            u = seq[i]
            for j in range(i + 2, len(seq)):
                has_intermediate.add(tuple(sorted([u, seq[j]])))

    raw_pairs = set(tuple(sorted([seq[i], seq[i+1]])) for seq in sequences for i in range(len(seq)-1))
    strict_adjacent = sorted(list(raw_pairs - has_intermediate))

    tracks = []
    adj = {}
    for u, v in strict_adjacent:
        c1, c2 = coords[u], coords[v]
        # Filter out any unrealistic teleport hops (> 120 km)
        if math.hypot((c1[0]-c2[0])*111, (c1[1]-c2[1])*100) < 120:
            tracks.append([[round(c1[0], 4), round(c1[1], 4)], [round(c2[0], 4), round(c2[1], 4)]])
            adj.setdefault(u, []).append(v)
            adj.setdefault(v, []).append(u)

    print(f"Extracted {len(tracks)} physical rail segments across {len(adj)} railway stations.")

    data = {
        "tracks": tracks,
        "adj": adj
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))

    size_kb = os.path.getsize(out_path) / 1024
    print(f"Successfully saved {out_path} ({size_kb:.1f} KB)")

if __name__ == "__main__":
    build()
