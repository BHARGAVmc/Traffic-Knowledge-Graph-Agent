import argparse
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# Andhra Pradesh Districts
# Approximate district center coordinates
# ============================================================

DISTRICTS = {
    "Alluri Sitharama Raju": (17.9800, 82.7000),
    "Anakapalli": (17.6900, 83.0100),
    "Ananthapuramu": (14.6800, 77.6000),
    "Annamayya": (14.0700, 79.0200),
    "Bapatla": (15.9000, 80.4700),
    "Chittoor": (13.2200, 79.1000),
    "Dr. B. R. Ambedkar Konaseema": (16.6700, 82.0000),
    "East Godavari": (16.9800, 82.2400),
    "Eluru": (16.7100, 81.1000),
    "Guntur": (16.3000, 80.4400),
    "Kakinada": (16.9900, 82.2500),
    "Krishna": (16.2000, 81.1400),
    "Kurnool": (15.8300, 78.0500),
    "Nandyal": (15.4800, 78.4800),
    "NTR": (16.5200, 80.6300),
    "Palnadu": (16.0000, 79.7500),
    "Parvathipuram Manyam": (18.7800, 83.4200),
    "Prakasam": (15.5000, 80.0500),
    "Sri Potti Sriramulu Nellore": (14.4400, 79.9900),
    "Sri Sathya Sai": (14.1700, 77.8100),
    "Srikakulam": (18.3000, 83.9000),
    "Tirupati": (13.6300, 79.4200),
    "Visakhapatnam": (17.6900, 83.2200),
    "Vizianagaram": (18.1200, 83.4000),
    "West Godavari": (16.6000, 81.5000),
    "YSR Kadapa": (14.4700, 78.8200),
}


# ============================================================
# Create synthetic road segment
# ============================================================

def make_random_segment(
    rng,
    center_lat,
    center_lon,
    district,
    segment_number
):
    """
    Create a synthetic road segment around a district center.
    """

    start_lat = center_lat + rng.uniform(-0.08, 0.08)
    start_lon = center_lon + rng.uniform(-0.08, 0.08)

    # Segment length between 0.3 km and 3 km
    length_km = rng.uniform(0.3, 3.0)

    # Random direction
    bearing_rad = rng.uniform(0, 2 * np.pi)

    # Approximate degree conversion
    dlat = (length_km / 111.0) * np.cos(bearing_rad)

    dlon = (
        length_km
        / (111.0 * np.cos(np.radians(start_lat)))
    ) * np.sin(bearing_rad)

    end_lat = start_lat + dlat
    end_lon = start_lon + dlon

    wkt = (
        f"LINESTRING "
        f"({start_lat:.6f} {start_lon:.6f}, "
        f"{end_lat:.6f} {end_lon:.6f})"
    )

    length_m = length_km * 1000.0

    return wkt, length_m


# ============================================================
# Traffic pattern
# ============================================================

def congestion_multiplier(ts):
    """
    Simulate traffic congestion.

    Weekdays:
        Morning peak
        Evening peak

    Weekends:
        Flatter traffic pattern
    """

    hour = ts.hour + ts.minute / 60.0

    is_weekend = ts.dayofweek >= 5

    def bump(center, width, height):
        return height * np.exp(
            -0.5 * ((hour - center) / width) ** 2
        )

    if is_weekend:

        base = 0.05

        level = (
            base
            + bump(13.0, 3.0, 0.25)
        )

    else:

        base = 0.05

        level = (
            base
            + bump(8.0, 1.0, 0.55)
            + bump(18.0, 1.5, 0.60)
        )

    return float(
        np.clip(level, 0.0, 1.0)
    )


# ============================================================
# Generate dataset
# ============================================================

def generate(
    segments_per_district,
    days,
    seed,
    start
):

    rng = np.random.default_rng(seed)

    segments = []

    # --------------------------------------------
    # Create road segments for every AP district
    # --------------------------------------------

    for district, (lat, lon) in DISTRICTS.items():

        for segment_number in range(
            1,
            segments_per_district + 1
        ):

            wkt, length_m = make_random_segment(
                rng,
                lat,
                lon,
                district,
                segment_number
            )

            segments.append(
                {
                    "district": district,
                    "segment_number": segment_number,
                    "wkt": wkt,
                    "length_m": length_m
                }
            )
        # Create road segment metadata
    metadata = []

    for index, segment in enumerate(segments, start=1):

        metadata.append({
            "segment_id": f"SEG{index:03d}",
            "district": segment["district"],
            "linestring": segment["wkt"],
            "length_m": round(segment["length_m"], 3)
        })

    metadata_df = pd.DataFrame(metadata)

    # --------------------------------------------
    # Create timestamps
    # --------------------------------------------

    start_ts = pd.Timestamp(start)

    num_steps = days * 24 * 12

    timestamps = [
        start_ts + timedelta(minutes=5 * i)
        for i in range(num_steps)
    ]

    # --------------------------------------------
    # Prepare output
    # --------------------------------------------

    data = {
        "Timestamp": [
            t.strftime("%Y-%m-%d %H:%M:%S")
            for t in timestamps
        ]
    }

    # --------------------------------------------
    # Generate traffic values
    # --------------------------------------------

    for segment in segments:

        wkt = segment["wkt"]
        length_m = segment["length_m"]

        # Different roads have different busyness
        busyness = rng.uniform(0.4, 1.0)

        values = np.empty(
            num_steps,
            dtype="float32"
        )

        for i, ts in enumerate(timestamps):

            level = (
                congestion_multiplier(ts)
                * busyness
            )

            noise = rng.normal(
                0,
                0.05
            )

            percentage = float(
                np.clip(
                    level + noise,
                    0.0,
                    1.0
                )
            )

            values[i] = round(
                percentage * length_m,
                3
            )

        data[wkt] = values

    return pd.DataFrame(data), metadata_df


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Generate synthetic Andhra Pradesh traffic data"
    )

    parser.add_argument(
        "--segments-per-district",
        type=int,
        default=5,
        help="Number of road segments per AP district"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed"
    )

    parser.add_argument(
        "--start",
        type=str,
        default="2026-01-01 00:00:00",
        help="Starting timestamp"
    )

    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output CSV path"
    )

    args = parser.parse_args()

    # --------------------------------------------
    # Output location
    # --------------------------------------------

    if args.out is None:

        output_path = (
            Path(__file__).resolve().parent
            / "AP_TrafficData.csv"
        )

    else:

        output_path = Path(args.out)

    # --------------------------------------------
    # Generate
    # --------------------------------------------

    df, metadata_df = generate(
        segments_per_district=args.segments_per_district,
        days=args.days,
        seed=args.seed,
        start=args.start
    )

    # --------------------------------------------
    # Save
    # --------------------------------------------

    df.to_csv(
        output_path,
        index=False
    )
    metadata_path = (
        output_path.parent / "road_segments.csv"
    )

    metadata_df.to_csv(
        metadata_path,
        index=False
    )

    print(
        f"Road metadata: {metadata_path}"
    )
    print(
        f"\nSynthetic AP traffic dataset created!"
    )

    print(
        f"Districts: {len(DISTRICTS)}"
    )

    print(
        f"Segments per district: "
        f"{args.segments_per_district}"
    )

    print(
        f"Total road segments: "
        f"{len(DISTRICTS) * args.segments_per_district}"
    )

    print(
        f"Days: {args.days}"
    )

    print(
        f"Rows: {len(df)}"
    )

    print(
        f"Columns: {len(df.columns)}"
    )

    print(
        f"Output: {output_path}"
    )


if __name__ == "__main__":
    main()