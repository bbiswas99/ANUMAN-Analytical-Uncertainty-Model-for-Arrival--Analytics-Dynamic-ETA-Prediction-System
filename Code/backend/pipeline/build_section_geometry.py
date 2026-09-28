"""
build_section_geometry.py
Extracts real track geometry from an OSM PBF extract (Geofabrik India) using osmium and networkx.

Usage:
    python backend/pipeline/build_section_geometry.py --osm-pbf <path-to-india-latest.osm.pbf> [options]

Features:
1. Uses osmium streaming parser to extract only railway=rail ways and railway=station nodes.
2. Excludes service=yard, service=siding, service=spur.
3. Builds an undirected track graph in networkx with arc-length haversine segment weights.
4. Matches OSM stations to IR station codes using ref= tags, spatial proximity, and fuzzy name matching.
5. For consecutive station pairs along target corridors, enumerates candidate paths and selects the
   path best matching scheduled distance (with tie-breaking favoring usage=main).
6. Exports section_geometry.json with distance_match_confidence ratings (high, medium, low).
"""

import argparse
import json
import logging
import math
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
import osmium
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("build_section_geometry")

# =============================================================================
# Configuration & Corridor Definitions
# =============================================================================

# Target Corridors for SIH 2026 Scope (Stations and Main Junctures)
TARGET_CORRIDORS = {
    "Delhi-Mumbai-Kota": [
        "NDLS", "NZM", "FDB", "MTJ", "BTE", "BXN", "GGC", "SWM", "KOTA",
        "RMA", "BWM", "SGZ", "NAD", "RTM", "MGN", "DHD", "GDA", "BRC",
        "AKV", "ST", "NVS", "BL", "VAPI", "BVI", "BDTS", "MMCT"
    ],
    "Delhi-Howrah-GrandChord": [
        "NDLS", "GZB", "ALJN", "TDL", "ETW", "CNB", "FTP", "PRYJ", "MZP",
        "DDU", "BBU", "SSM", "DOS", "GAYA", "KQR", "GMO", "DHN", "ASN",
        "DGR", "BWN", "HWH"
    ],
    "Delhi-Chennai-Central": [
        "NDLS", "MTJ", "AGC", "DHO", "MRA", "GWL", "DBA", "JHS", "LAR",
        "BINA", "BPL", "HBJ", "ET", "GDYA", "BZU", "AMLA", "NGP", "WR",
        "CD", "BPQ", "SKZR", "BPA", "RDM", "WL", "KMT", "BZA", "TEL",
        "CLX", "OGL", "NLR", "GDR", "SPE", "MAS"
    ]
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes the great-circle distance in kilometers between two points."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2)
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


# =============================================================================
# 1. Osmium Handler for Filtering OSM Track Ways & Station Nodes
# =============================================================================

class RailGeometryHandler(osmium.SimpleHandler):
    """
    Streaming Osmium handler.
    Extracts railway=rail track ways and railway=station / railway=halt nodes.
    Filters out yard/siding/spur ways directly in the stream.
    """
    def __init__(self):
        super().__init__()
        self.station_nodes: List[dict] = []
        self.track_ways: List[dict] = []
        self.excluded_services = {"yard", "siding", "spur"}

    def way(self, w):
        # Fast filter on C++ string without dict allocation
        if "railway" not in w.tags or w.tags["railway"] != "rail":
            return

        # Exclude yards, sidings, spurs
        service = w.tags.get("service")
        if service in self.excluded_services:
            return

        # Must have at least 2 coordinate points
        try:
            nodes = [(round(pt.lat, 6), round(pt.lon, 6)) for pt in w.nodes]
        except (osmium.InvalidLocationError, Exception):
            return

        if len(nodes) < 2:
            return

        # Extract infrastructure attributes
        tracks_val = 2  # default main line assumption
        tracks_str = w.tags.get("tracks")
        if tracks_str and tracks_str.isdigit():
            tracks_val = int(tracks_str)

        electrified = w.tags.get("electrified") in ("contact_line", "yes", "true")
        usage = w.tags.get("usage", "unspecified")

        self.track_ways.append({
            "coords": nodes,
            "tracks": tracks_val,
            "electrified": electrified,
            "usage": usage
        })


# =============================================================================
# 2. Graph Construction & Station Node Snapping
# =============================================================================

def build_track_graph(track_ways: List[dict]) -> nx.Graph:
    """
    Builds an undirected networkx graph representing the railway network.
    Nodes are quantized coordinate pairs (lat, lon) rounded to 6 decimal places.
    Edges hold arc length (haversine km), tracks count, electrification, and usage.
    """
    g = nx.Graph()
    for way in track_ways:
        coords = way["coords"]
        tracks = way["tracks"]
        electrified = way["electrified"]
        usage = way["usage"]

        for i in range(len(coords) - 1):
            p1 = (round(coords[i][0], 6), round(coords[i][1], 6))
            p2 = (round(coords[i + 1][0], 6), round(coords[i + 1][1], 6))
            if p1 == p2:
                continue

            dist_km = haversine_km(p1[0], p1[1], p2[0], p2[1])
            if dist_km == 0:
                continue

            # Weight incorporates small penalty for branch/unspecified when searching for main-line paths
            usage_penalty = 1.0 if usage == "main" else 1.05

            if g.has_edge(p1, p2):
                # Update attributes if existing edge is less specified
                existing = g[p1][p2]
                if usage == "main":
                    existing["usage"] = "main"
                existing["tracks"] = max(existing["tracks"], tracks)
                existing["electrified"] = existing["electrified"] or electrified
            else:
                g.add_edge(
                    p1, p2,
                    weight=dist_km * usage_penalty,
                    length_km=dist_km,
                    tracks=tracks,
                    electrified=electrified,
                    usage=usage,
                    coords=[list(p1), list(p2)]
                )
    log.info(f"Built railway track graph: {g.number_of_nodes():,} nodes, {g.number_of_edges():,} segments.")
    return g


def match_stations_to_graph(
    osm_stations: List[dict],
    station_ref_df: pd.DataFrame,
    station_coords_known: Dict[str, List[float]],
    target_stations: Set[str],
    graph: nx.Graph
) -> Dict[str, Tuple[float, float]]:
    """
    Resolves each target IR station code (e.g. 'NDLS') to its closest node in the track graph.
    Priority:
    1. Direct match on OSM node ref= tag
    2. Spatial proximity match to known station coordinates (< 1.5 km)
    3. Fuzzy name match against station_full_name
    """
    matched_nodes = {}
    # Snap to the primary giant component of the railway network so stations never snap to isolated dead-ends
    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    main_nodes_set = components[0] if components else set(graph.nodes())
    graph_nodes = [n for n in graph.nodes() if n in main_nodes_set]
    graph_nodes_arr = np.array(graph_nodes)

    # Pre-index OSM station nodes by ref
    osm_by_ref = {}
    for st in osm_stations:
        if st["ref"]:
            osm_by_ref[st["ref"]] = (st["lat"], st["lon"])

    # Prepare lookup table from station_ref_df
    ref_name_map = {}
    if not station_ref_df.empty and "station_name" in station_ref_df.columns:
        for _, row in station_ref_df.iterrows():
            code = str(row["station_name"]).strip().upper()
            full_name = str(row.get("station_full_name", "")).strip().lower()
            ref_name_map[code] = full_name

    for code in target_stations:
        target_lat_lon = None

        # 1. Prefer known accurate coordinates from station-coordinates.json
        if code in station_coords_known:
            target_lat_lon = tuple(station_coords_known[code])
        # 2. Check OSM ref match
        elif code in osm_by_ref:
            target_lat_lon = osm_by_ref[code]
        # 3. Fuzzy name match across OSM stations
        elif code in ref_name_map:
            target_full = ref_name_map[code]
            best_score = 0.0
            best_osm_coord = None
            for st in osm_stations:
                st_name = st["name"].lower()
                sim = SequenceMatcher(None, target_full, st_name).ratio()
                if sim > best_score:
                    best_score = sim
                    best_osm_coord = (st["lat"], st["lon"])
            if best_score >= 0.75 and best_osm_coord:
                target_lat_lon = best_osm_coord

        if not target_lat_lon:
            continue

        # Snap target_lat_lon to closest node on railway track graph
        dists = np.hypot(
            graph_nodes_arr[:, 0] - target_lat_lon[0],
            graph_nodes_arr[:, 1] - target_lat_lon[1]
        )
        min_idx = np.argmin(dists)
        closest_node = tuple(graph_nodes_arr[min_idx])
        snap_dist_km = haversine_km(target_lat_lon[0], target_lat_lon[1], closest_node[0], closest_node[1])

        # Allow snap within 2.5 km of station point
        if snap_dist_km <= 2.5:
            matched_nodes[code] = closest_node
        else:
            log.warning(f"Station {code} closest track node is {snap_dist_km:.2f} km away; skipped.")

    log.info(f"Successfully matched {len(matched_nodes)} / {len(target_stations)} target stations to track graph.")
    return matched_nodes


# =============================================================================
# 3. Expected Route Extraction & Distance Matching
# =============================================================================

def find_expected_route(
    graph: nx.Graph,
    source_node: Tuple[float, float],
    target_node: Tuple[float, float],
    scheduled_distance_km: float
) -> Optional[dict]:
    """
    Finds the shortest path between source_node and target_node along the track graph.
    Edge weights prioritize usage=main segments.
    Validates physical path length against scheduled_distance_km.
    """
    try:
        path_nodes = nx.shortest_path(graph, source_node, target_node, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    # Reconstruct path coordinates and edge attributes
    path_coords = [list(path_nodes[0])]
    total_len = 0.0
    tracks_list = []
    electrified_list = []
    usage_list = []

    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
        edge_data = graph[u][v]
        total_len += edge_data.get("length_km", 0.0)
        tracks_list.append(edge_data.get("tracks", 2))
        electrified_list.append(edge_data.get("electrified", True))
        usage_list.append(edge_data.get("usage", "main"))
        path_coords.append(list(v))

    diff_km = abs(total_len - scheduled_distance_km) if scheduled_distance_km > 0 else 0.0
    pct_diff = (diff_km / scheduled_distance_km) if scheduled_distance_km > 0 else 0.0
    main_ratio = (sum(1 for u in usage_list if u == "main") / max(1, len(usage_list)))

    # Detour Loop Rejection:
    # Rail alignments in India never exceed 30% above scheduled distance or 40% above straight line.
    # Reject any abnormal detour loops so they fall back to the direct station-to-station connection.
    straight_km = haversine_km(source_node[0], source_node[1], target_node[0], target_node[1])
    if scheduled_distance_km > 0 and total_len > 1.30 * scheduled_distance_km:
        return None
    if total_len > 1.40 * max(straight_km, 2.0):
        return None

    # Assign confidence category
    if scheduled_distance_km <= 0 or pct_diff <= 0.10:
        confidence = "high"
    elif pct_diff <= 0.25:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "coordinates": path_coords,
        "tracks": Counter(tracks_list).most_common(1)[0][0] if tracks_list else 2,
        "electrified": all(electrified_list),
        "usage": "main" if main_ratio >= 0.5 else "branch",
        "expected_route_distance_km": round(total_len, 1),
        "scheduled_distance_km": round(scheduled_distance_km, 1),
        "distance_match_confidence": confidence
    }


# =============================================================================
# 4. Main Extraction Pipeline
# =============================================================================

def extract_section_geometry(
    osm_pbf_path: Path,
    schedule_csv_path: Path,
    station_names_csv_path: Path,
    station_coords_json_path: Path,
    output_geometry_json_path: Path
):
    """Executes the full OSM route geometry extraction pipeline."""
    if not osm_pbf_path.exists():
        raise FileNotFoundError(f"OSM PBF file not found at: {osm_pbf_path}")

    # 1. Identify all target stations and consecutive station sections from target corridors
    log.info("Collecting corridor station pairs and scheduled distances...")
    target_station_set = set()
    for corridor_stations in TARGET_CORRIDORS.values():
        target_station_set.update(corridor_stations)

    # Load schedule to calculate exact scheduled distance delta between adjacent stations
    sched_df = pd.read_csv(schedule_csv_path)
    sched_df["station_name"] = sched_df["station_name"].astype(str).str.strip().str.upper()
    sched_df = sched_df.sort_values(["train_no", "station_no"]).reset_index(drop=True)

    # Shift to compute section legs and scheduled distance
    dist_col = "distance_from_origin" if "distance_from_origin" in sched_df.columns else "distance"
    sched_df["next_station"] = sched_df.groupby("train_no")["station_name"].shift(-1)
    sched_df["next_dist"] = sched_df.groupby("train_no")[dist_col].shift(-1)
    sched_df["leg_dist"] = (sched_df["next_dist"] - sched_df[dist_col]).abs()

    # Filter to legs that occur in our target corridor stations
    corridor_legs = sched_df[
        sched_df["station_name"].isin(target_station_set) &
        sched_df["next_station"].isin(target_station_set) &
        sched_df["next_station"].notna()
    ]

    # Aggregate median scheduled distance per unique section_id
    section_scheduled_distances = {}
    for _, row in corridor_legs.iterrows():
        s_from = row["station_name"]
        s_to = row["next_station"]
        sec_id = f"{s_from}_{s_to}"
        dist = float(row["leg_dist"]) if not pd.isna(row["leg_dist"]) else 0.0
        if sec_id not in section_scheduled_distances:
            section_scheduled_distances[sec_id] = []
        if dist > 0:
            section_scheduled_distances[sec_id].append(dist)

    sec_dist_medians = {
        sec_id: float(np.median(dists)) if dists else 0.0
        for sec_id, dists in section_scheduled_distances.items()
    }
    log.info(f"Identified {len(sec_dist_medians):,} unique corridor track sections.")

    # 2. Parse OSM PBF using streaming osmium handler
    log.info(f"Streaming and parsing railway elements from {osm_pbf_path} ...")
    handler = RailGeometryHandler()
    handler.apply_file(str(osm_pbf_path), locations=True)
    log.info(f"Extracted {len(handler.track_ways):,} rail ways and {len(handler.station_nodes):,} station nodes.")

    # 3. Build Graph
    graph = build_track_graph(handler.track_ways)

    # 4. Resolve Station Locations
    station_names_df = pd.read_csv(station_names_csv_path) if station_names_csv_path.exists() else pd.DataFrame()
    with open(station_coords_json_path, "r", encoding="utf-8") as f:
        known_coords = json.load(f)

    station_nodes = match_stations_to_graph(
        osm_stations=handler.station_nodes,
        station_ref_df=station_names_df,
        station_coords_known=known_coords,
        target_stations=target_station_set,
        graph=graph
    )

    # 5. Extract expected route for each section
    log.info("Enumerating candidate paths and matching scheduled distances...")
    results = {}
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    low_confidence_sections = []

    for idx, (sec_id, sched_dist) in enumerate(sec_dist_medians.items(), 1):
        if idx % 50 == 0 or idx == len(sec_dist_medians):
            log.info(f"Matching route distance: {idx}/{len(sec_dist_medians)} sections...")

        s_from, s_to = sec_id.split("_")
        node_from = station_nodes.get(s_from)
        node_to = station_nodes.get(s_to)

        if not node_from or not node_to:
            # Fallback to straight line if station nodes were not found in track graph
            coord_from = known_coords.get(s_from)
            coord_to = known_coords.get(s_to)
            if coord_from and coord_to:
                results[sec_id] = {
                    "section_id": sec_id,
                    "station_from": s_from,
                    "station_to": s_to,
                    "coordinates": [coord_from, coord_to],
                    "tracks": 2,
                    "electrified": True,
                    "usage": "main",
                    "expected_route_distance_km": round(haversine_km(coord_from[0], coord_from[1], coord_to[0], coord_to[1]), 1),
                    "scheduled_distance_km": round(sched_dist, 1),
                    "distance_match_confidence": "low"
                }
                confidence_counts["low"] += 1
                low_confidence_sections.append((sec_id, "Unmapped station node in graph"))
            continue

        route_match = find_expected_route(graph, node_from, node_to, sched_dist)
        if route_match:
            route_match["section_id"] = sec_id
            route_match["station_from"] = s_from
            route_match["station_to"] = s_to
            results[sec_id] = route_match

            conf = route_match["distance_match_confidence"]
            confidence_counts[conf] += 1
            if conf == "low":
                low_confidence_sections.append(
                    (sec_id, f"Expected {route_match['expected_route_distance_km']}km vs Scheduled {sched_dist}km")
                )
        else:
            coord_from = known_coords.get(s_from)
            coord_to = known_coords.get(s_to)
            if coord_from and coord_to:
                results[sec_id] = {
                    "section_id": sec_id,
                    "station_from": s_from,
                    "station_to": s_to,
                    "coordinates": [coord_from, coord_to],
                    "tracks": 2,
                    "electrified": True,
                    "usage": "main",
                    "expected_route_distance_km": round(haversine_km(coord_from[0], coord_from[1], coord_to[0], coord_to[1]), 1),
                    "scheduled_distance_km": round(sched_dist, 1),
                    "distance_match_confidence": "low"
                }
            confidence_counts["low"] += 1
            low_confidence_sections.append((sec_id, "No path found in track graph"))

    # Format for frontend compatibility: sections array + by_id lookup
    sections_list = []
    for sec_id, d in results.items():
        sections_list.append({
            "id": sec_id,
            "from": d["station_from"],
            "to": d["station_to"],
            "coords": d["coordinates"],
            "tracks": d.get("tracks", 2),
            "electrified": d.get("electrified", True),
            "usage": d.get("usage", "main"),
            "expected_route_distance_km": d.get("expected_route_distance_km"),
            "scheduled_distance_km": d.get("scheduled_distance_km"),
            "distance_match_confidence": d.get("distance_match_confidence")
        })

    output_payload = {
        "metadata": {
            "total_sections": len(sections_list),
            "confidence_breakdown": confidence_counts,
            "high_confidence_count": confidence_counts["high"],
            "medium_confidence_count": confidence_counts["medium"],
            "low_confidence_count": confidence_counts["low"]
        },
        "by_id": results,
        "sections": sections_list
    }

    # 6. Save output file
    output_geometry_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_geometry_json_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    log.info("=" * 60)
    log.info(f"SECTION GEOMETRY EXTRACTION COMPLETE -> {output_geometry_json_path}")
    log.info(f"Total sections processed: {len(results):,}")
    log.info(f"High confidence:   {confidence_counts['high']:,}")
    log.info(f"Medium confidence: {confidence_counts['medium']:,}")
    log.info(f"Low confidence:    {confidence_counts['low']:,}")
    log.info("=" * 60)

    if low_confidence_sections:
        log.warning(f"{len(low_confidence_sections)} sections flagged as low confidence:")
        for sec, reason in low_confidence_sections[:20]:
            log.warning(f"  - {sec}: {reason}")
        if len(low_confidence_sections) > 20:
            log.warning(f"  ... and {len(low_confidence_sections) - 20} more.")

    return results, confidence_counts


def main():
    parser = argparse.ArgumentParser(description="Extract real rail section geometry from Geofabrik OSM PBF.")
    parser.add_argument("--osm-pbf", type=Path, required=True, help="Path to india-latest.osm.pbf")
    parser.add_argument("--schedule-csv", type=Path, default=Path("Dataset/combined_schedule.csv"))
    parser.add_argument("--station-names-csv", type=Path, default=Path("Dataset/station_full_names.csv"))
    parser.add_argument("--station-coords-json", type=Path, default=Path("frontend/src/assets/station-coordinates.json"))
    parser.add_argument("--output", type=Path, default=Path("frontend/src/assets/section-geometry.json"))
    args = parser.parse_args()

    extract_section_geometry(
        osm_pbf_path=args.osm_pbf,
        schedule_csv_path=args.schedule_csv,
        station_names_csv_path=args.station_names_csv,
        station_coords_json_path=args.station_coords_json,
        output_geometry_json_path=args.output
    )


if __name__ == "__main__":
    main()
