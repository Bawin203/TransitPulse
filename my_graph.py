import pandas as pd
import networkx as nx

def load_data(demand_scale=1.0, capacity_scale=1.0):
    nodes = pd.read_csv("nodes.csv")
    edges = pd.read_csv("edges.csv")
    od_demand = pd.read_csv("od_demand.csv")

    # Apply Streamlit slider multipliers safely
    od_demand["passengers"] = od_demand["passengers"] * demand_scale
    edges["capacity"] = (edges["capacity"] * capacity_scale).clip(lower=1.0)
    return nodes, edges, od_demand

def build_graph(nodes, edges):
    G = nx.DiGraph()
    for _, row in nodes.iterrows():
        G.add_node(row["node_id"], name=row["name"], lat=row["lat"], lon=row["lon"])

    for _, row in edges.iterrows():
        G.add_edge(
            row["source"],
            row["target"],
            mode=row["mode"],
            base_time=float(row["time_min"]),
            time=float(row["time_min"]),
            capacity=float(row["capacity"]),
            load=0.0
        )
    return G

def get_critical_stations(G):
    scores = nx.betweenness_centrality(G, weight="time")
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    bridges = list(nx.articulation_points(G.to_undirected()))
    return ranked, bridges

def simulate_outage(G, od_demand, closed_stations=None):
    G_sim = G.copy()
    if closed_stations:
        for st in closed_stations:
            if st in G_sim:
                G_sim.remove_node(st)

    routes = []
    unserved_passengers = 0.0

    for _, row in od_demand.iterrows():
        start, end, pax = row["origin"], row["destination"], float(row["passengers"])
        if start not in G_sim or end not in G_sim:
            unserved_passengers += pax
            continue
        try:
            path = nx.shortest_path(G_sim, source=start, target=end, weight="time")
            routes.append({"origin": start, "destination": end, "passengers": pax, "path": path})
            for i in range(len(path) - 1):
                G_sim[path[i]][path[i + 1]]["load"] += pax
        except nx.NetworkXNoPath:
            unserved_passengers += pax

    return G_sim, routes, unserved_passengers

# Quick test when you run this file directly
if __name__ == "__main__":
    nodes, edges, od = load_data()
    G = build_graph(nodes, edges)
    ranked, bridges = get_critical_stations(G)
    G_sim, routes, unserved = simulate_outage(G, od, closed_stations=["MAJ"])

    # Conservation check (Total OD == Routed + Unserved)
    routed_pax = sum(r["passengers"] for r in routes)
    assert abs(od["passengers"].sum() - (routed_pax + unserved)) < 1e-6
    print("Verification passed! Routed:", int(routed_pax), "| Unserved:", int(unserved))
