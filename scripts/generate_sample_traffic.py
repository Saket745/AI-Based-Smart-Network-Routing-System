import csv
import random


def main():
    nodes = [str(i) for i in range(10)]
    protocols = ["TCP", "UDP", "ICMP"]

    # Keep seed for reproducibility
    random.seed(42)

    filename = "data/sample_traffic.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "source",
                "destination",
                "bytes",
                "packets",
                "duration",
                "protocol",
                "timestamp",
            ]
        )

        for _ in range(200):
            src = random.choice(nodes)
            dst = random.choice([n for n in nodes if n != src])
            proto = random.choice(protocols)

            # TCP/UDP flow size distributions
            if proto == "TCP":
                pkts = random.randint(5, 500)
                # average packet size around 1000 bytes
                bytes_count = pkts * random.randint(500, 1450)
                duration = round(random.uniform(0.1, 10.0), 3)
            elif proto == "UDP":
                pkts = random.randint(1, 100)
                bytes_count = pkts * random.randint(64, 500)
                duration = round(random.uniform(0.01, 2.0), 3)
            else:  # ICMP
                pkts = random.randint(1, 10)
                bytes_count = pkts * 64
                duration = round(random.uniform(0.001, 0.5), 3)

            timestamp = round(1000.0 + random.uniform(0.0, 60.0), 3)

            writer.writerow([src, dst, bytes_count, pkts, duration, proto, timestamp])

    print(f"Generated {filename} with 200 rows of traffic data.")


if __name__ == "__main__":
    main()
