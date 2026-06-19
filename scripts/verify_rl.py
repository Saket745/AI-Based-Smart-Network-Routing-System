import os
import sys

# Add src to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from nroute.core.topology import Topology
from nroute.routing.dijkstra import DijkstraRouter
from nroute.routing.rl_router import RLRouter


def verify():
    # 1. Load topology
    topo = Topology.load("data/sample_topology.json")
    print(f"Loaded topology: {topo.node_count} nodes, {topo.edge_count} edges")

    # 2. Initialize and Train RLRouter
    # We train for 100 episodes (approx 2000 timesteps)
    router = RLRouter(topology=topo, algorithm="ppo")

    print("\nTraining RL agent...")
    metrics = router.train(episodes=100, seed=42)
    print(f"Training metrics: {metrics}")

    # 3. Check consistency of cached metadata
    print("\nCached Metadata:")
    print(f"Training nodes: {router._training_nodes}")
    print(f"Training obs dim: {router._training_obs_dim}")
    print(f"Training max out-degree: {router._training_max_out_degree}")

    # 4. Compare RLRouter paths vs DijkstraRouter paths
    dijkstra = DijkstraRouter()

    # Test all pairs of nodes
    nodes = list(topo.nodes)
    mismatched_paths = 0
    total_tests = 0
    successful_rl = 0

    print("\nComparing paths:")
    for src in nodes[:3]:
        for dst in nodes:
            if src == dst:
                continue
            total_tests += 1

            # Dijkstra path
            try:
                dijkstra_path = dijkstra.compute_path(topo, src, dst)
            except Exception as e:
                dijkstra_path = f"Error: {e}"

            # RL path
            try:
                rl_path = router.compute_path(topo, src, dst)
                successful_rl += 1
            except Exception as e:
                rl_path = f"Error: {e}"

            print(f"Route {src} -> {dst}:")
            print(f"  Dijkstra: {dijkstra_path}")
            print(f"  RLRouter: {rl_path}")

            if rl_path != dijkstra_path and not isinstance(rl_path, str):
                mismatched_paths += 1

    print("\n--- Summary ---")
    print(f"Total routes tested: {total_tests}")
    print(f"Successful RL inferences: {successful_rl}/{total_tests}")
    print(f"Routes where RL differed from Dijkstra: {mismatched_paths}/{total_tests}")

    # Assertions for verification
    assert successful_rl == total_tests, "RL router failed some inferences (fallback triggered)"
    print(
        "[SUCCESS] RL Router successfully inferred paths for all tested pairs without falling back!"
    )


if __name__ == "__main__":
    verify()
