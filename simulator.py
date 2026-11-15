import pandas as pd
import networkx as nx
from my_graph import load_data, build_graph, get_critical_stations

def update_bpr_times(G, alpha=0.15, beta=4):
    for edge in G.edges(data=True):
        data = edge[2]
        vc_ratio = data["load"] / data["capacity"]
        data["time"] = data["base_time"] * (1.0 + alpha * (vc_ratio ** beta))

def run_msa_simulation(G, od_demand, closed_stations=None, iterations=10):
    G_sim = G.copy()
    if closed_stations:
        for st in closed_stations:
            if st in G_sim:
                G_sim.remove_node(st)

    for edge in G_sim.edges(data=True):
        edge[2]["load"] = 0.0
        edge[2]["time"] = edge[2]["base_time"]

    unserved_list = []
    routed_paths = []
    total_person_minutes = 0.0

    for k in range(1, iterations + 1):
        step = 1.0 / k
        aux_loads = {(edge[0], edge[1]): 0.0 for edge in G_sim.edges()}
        current_unserved = []
        current_paths = []
        current_pmins = 0.0

        for _, row in od_demand.iterrows():
            orig, dest, pax = row["origin"], row["destination"], float(row["passengers"])

            if orig not in G_sim or dest not in G_sim:
                current_unserved.append({"origin": orig, "destination": dest, "passengers": pax, "reason": "Hub closed"})
                continue

            try:
                path = nx.shortest_path(G_sim, source=orig, target=dest, weight="time")
                travel_time = nx.path_weight(G_sim, path, weight="time")
                current_pmins += pax * travel_time
                current_paths.append({
                    "origin": orig,
                    "destination": dest,
                    "passengers": pax,
                    "path": " -> ".join(path),
                    "time_min": round(travel_time, 1)
                })
                for i in range(len(path) - 1):
                    aux_loads[(path[i], path[i + 1])] += pax
            except nx.NetworkXNoPath:
                current_unserved.append({"origin": orig, "destination": dest, "passengers": pax, "reason": "No path"})

        for edge in G_sim.edges(data=True):
            u, v, data = edge[0], edge[1], edge[2]
            data["load"] = (1.0 - step) * data["load"] + step * aux_loads[(u, v)]

        update_bpr_times(G_sim)
        unserved_list = current_unserved
        routed_paths = current_paths
        total_person_minutes = current_pmins

    return G_sim, routed_paths, unserved_list, total_person_minutes

def allocate_bus_bridges(G_base, G_sim, depots_df, unserved_list, closed_stations=None):
    closed_set = set(closed_stations or [])
    demand_nodes = {}

    for edge in G_sim.edges(data=True):
        u, v, data = edge[0], edge[1], edge[2]
        if data["load"] > data["capacity"]:
            excess = data["load"] - data["capacity"]
            demand_nodes[u] = demand_nodes.get(u, 0.0) + excess

    for item in unserved_list:
        orig = item["origin"]
        if orig not in closed_set:
            demand_nodes[orig] = demand_nodes.get(orig, 0.0) + item["passengers"]

    if not demand_nodes:
        return [], 0

    F = nx.DiGraph()
    total_supply = 0
    active_depots = []

    for _, row in depots_df.iterrows():
        dep_node = row["nearest_node"]
        if dep_node in closed_set:
            continue
        cap_pax = int(row["available_buses"] * row["bus_capacity"])
        active_depots.append((row["depot_id"], row["name"], dep_node, cap_pax, int(row["bus_capacity"])))
        total_supply += cap_pax

    total_need = int(sum(demand_nodes.values()))
    allocatable = min(total_supply, total_need)

    if allocatable <= 0:
        return [], total_need

    F.add_node("SOURCE", demand=-allocatable)
    F.add_node("SINK", demand=allocatable)

    for dep_id, dep_name, dep_node, cap_pax, bus_cap in active_depots:
        F.add_edge("SOURCE", dep_id, capacity=cap_pax, weight=0)
        F.add_edge(dep_id, "SINK", capacity=cap_pax, weight=9999)

        for target_stop, need_pax in demand_nodes.items():
            try:
                dist_cost = int(nx.shortest_path_length(G_base, dep_node, target_stop, weight="base_time"))
            except nx.NetworkXNoPath:
                dist_cost = 30
            F.add_edge(dep_id, f"DEM_{target_stop}", capacity=int(need_pax), weight=dist_cost)

    for target_stop, need_pax in demand_nodes.items():
        F.add_edge(f"DEM_{target_stop}", "SINK", capacity=int(need_pax), weight=0)

    flow_dict = nx.min_cost_flow(F)
    allocations = []
    served_by_buses = 0

    for dep_id, dep_name, dep_node, _, bus_cap in active_depots:
        for target_stop in demand_nodes:
            moved = flow_dict[dep_id].get(f"DEM_{target_stop}", 0)
            if moved > 0:
                buses_needed = -(-moved // bus_cap)
                served_by_buses += moved
                allocations.append({
                    "Depot": dep_name,
                    "Target Hub": target_stop,
                    "Passengers Covered": int(moved),
                    "Buses Dispatched": int(buses_needed)
                })

    remaining_unserved = max(0, total_need - served_by_buses)
    return allocations, remaining_unserved
