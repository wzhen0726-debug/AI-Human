#!/usr/bin/env python
"""
Analyze a head mesh template to determine if it has interior cavity walls
for eye sockets, oral cavity, and lips.

Usage:
    python analyze_head_cavity.py <path/to/template.obj>

Outputs:
    - Whether the mesh is watertight
    - Number and location of boundary loops (openings)
    - Inward-facing face analysis (interior geometry detection)
    - Per-cavity depth profiling (eye sockets, mouth, nostrils)
    - Exports interior geometry as PLY files for visualization

Requires: pip install trimesh scipy numpy
"""
import sys
import trimesh
import numpy as np
from collections import defaultdict
from scipy.cluster.hierarchy import fclusterdata


def analyze_mesh(mesh_path):
    print(f"Loading: {mesh_path}")
    mesh = trimesh.load(mesh_path)

    V = len(mesh.vertices)
    F = len(mesh.faces)
    face_normals = mesh.face_normals
    face_centers = mesh.triangles.mean(axis=1)
    centroid = mesh.centroid

    print(f"\n{'='*60}")
    print(f"BASIC STATS")
    print(f"{'='*60}")
    print(f"Vertices: {V}")
    print(f"Faces: {F}")
    print(f"Bounds X: [{mesh.bounds[0][0]:.4f}, {mesh.bounds[1][0]:.4f}]")
    print(f"Bounds Y: [{mesh.bounds[0][1]:.4f}, {mesh.bounds[1][1]:.4f}]")
    print(f"Bounds Z: [{mesh.bounds[0][2]:.4f}, {mesh.bounds[1][2]:.4f}]")
    print(f"Watertight: {mesh.is_watertight}")

    # --- Boundary loop detection ---
    print(f"\n{'='*60}")
    print(f"BOUNDARY LOOPS (OPENINGS)")
    print(f"{'='*60}")

    edge_face_count = {}
    for f in mesh.faces:
        for i in range(3):
            e = tuple(sorted([f[i], f[(i+1) % 3]]))
            edge_face_count[e] = edge_face_count.get(e, 0) + 1

    boundary_edges = [(v1, v2) for (v1, v2), c in edge_face_count.items() if c == 1]
    print(f"Boundary edges: {len(boundary_edges)}")

    boundary_adj = defaultdict(list)
    for v1, v2 in boundary_edges:
        boundary_adj[v1].append(v2)
        boundary_adj[v2].append(v1)

    visited = set()
    loops = []
    for start in boundary_adj:
        if start in visited:
            continue
        loop = []
        current = start
        while current not in visited and current in boundary_adj:
            visited.add(current)
            loop.append(current)
            next_verts = [v for v in boundary_adj[current] if v not in visited]
            if next_verts:
                current = next_verts[0]
            else:
                break
        if len(loop) > 2:
            loops.append(loop)

    loops.sort(key=lambda l: len(l), reverse=True)
    print(f"Boundary loops: {len(loops)}")
    for i, loop in enumerate(loops):
        verts = mesh.vertices[loop]
        center = np.mean(verts, axis=0) * 1000
        size = np.max(np.ptp(verts, axis=0)) * 1000
        print(f"  Loop {i}: {len(loop)} verts, center=({center[0]:.1f}, {center[1]:.1f}, {center[2]:.1f})mm, size={size:.1f}mm")

    # --- Inward-facing face analysis ---
    print(f"\n{'='*60}")
    print(f"INTERIOR GEOMETRY ANALYSIS")
    print(f"{'='*60}")

    directions = face_centers - centroid
    dot_products = np.sum(directions * face_normals, axis=1)
    inward_mask = dot_products < -0.0001
    inward_count = np.sum(inward_mask)
    print(f"Inward-facing faces: {inward_count} ({inward_count/F*100:.1f}%)")

    if inward_count < F * 0.05:
        print("\n>>> NO SIGNIFICANT INTERIOR GEOMETRY")
        print(">>> Mesh is a pure open shell with NO interior cavity walls")
        print(">>> Eye sockets and mouth are open holes")
        return

    print(f"\n>>> SIGNIFICANT INTERIOR GEOMETRY DETECTED ({inward_count} faces)")
    print(">>> This suggests interior cavity walls exist")

    # --- Cluster inward faces ---
    inward_faces = np.where(inward_mask)[0]
    inward_centers = face_centers[inward_faces]

    clusters = fclusterdata(inward_centers, t=0.03, criterion='distance')
    n_clusters = len(set(clusters))

    print(f"\nInterior clusters (distance < 30mm): {n_clusters}")
    for c in range(1, n_clusters + 1):
        mask = clusters == c
        cluster_face_idx = inward_faces[mask]
        cluster_centers = face_centers[cluster_face_idx]
        center = np.mean(cluster_centers, axis=0)
        count = np.sum(mask)
        xr = (cluster_centers[:, 0].min(), cluster_centers[:, 0].max())
        yr = (cluster_centers[:, 1].min(), cluster_centers[:, 1].max())
        zr = (cluster_centers[:, 2].min(), cluster_centers[:, 2].max())
        print(f"  Cluster {c}: {count} faces, center=({center[0]*1000:.1f}, {center[1]*1000:.1f}, {center[2]*1000:.1f})mm")
        print(f"    X[{xr[0]*1000:.1f},{xr[1]*1000:.1f}] Y[{yr[0]*1000:.1f},{yr[1]*1000:.1f}] Z[{zr[0]*1000:.1f},{zr[1]*1000:.1f}]mm")

    # --- Export interior geometry ---
    import os
    out_dir = os.path.dirname(mesh_path) or "."
    interior_mesh = mesh.submesh([inward_mask])[0]
    interior_path = os.path.join(out_dir, "interior_geometry.ply")
    interior_mesh.export(interior_path)
    print(f"\nExported interior geometry: {interior_path} ({len(interior_mesh.faces)} faces)")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"1. Mesh is {'NOT ' if not mesh.is_watertight else ''}watertight (open shell)")
    print(f"2. Has {len(loops)} boundary loops (openings)")
    print(f"3. Has {inward_count} inward-facing faces ({inward_count/F*100:.1f}%)")
    if inward_count > F * 0.05:
        print(f"4. Interior cavity walls DETECTED — eye sockets and mouth have interior mesh")
        print(f"   Template is suitable for wrap (interior surfaces will be fitted)")
    else:
        print(f"4. NO interior cavity walls — eye sockets and mouth are open holes")
        print(f"   Template will need post-wrap cavity patching")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_head_cavity.py <path/to/template.obj>")
        sys.exit(1)
    analyze_mesh(sys.argv[1])
