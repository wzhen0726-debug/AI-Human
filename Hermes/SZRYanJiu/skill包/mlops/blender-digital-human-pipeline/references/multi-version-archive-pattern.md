# Multi-Version Project Archive Pattern

When a project evolves through distinct technical approaches, create detailed archive MD files so other AI agents can pick up from any checkpoint.

## Archive Structure

Each version gets one or more `档案_vN_*.md` files covering:

1. **Environment**: Blender version, path, Python version, paid plugins, project paths
2. **Goal**: What this version aimed to achieve, and why it differs from previous versions
3. **Research Process**: Every investigation, source of information, key findings
4. **Approaches Tried**: ALL methods attempted, with success rates, error details, and reasons for failure
5. **Key Technical Findings**: Verified facts (e.g., "bmesh vert.co and UV layer independence confirmed with 0.0 diff across all tests")
6. **API/Tool Notes**: Exact APIs used, version-specific quirks, gotchas
7. **File Inventory**: Where every script, model, and report lives
8. **Current State**: What works, what doesn't, and why

## Level of Detail

The target reader is another AI agent on a different PC with NO prior context. Include:
- Exact file paths
- Exact commands that were run
- Exact error messages
- Exact API calls with parameters
- Reasoning behind every key decision
- What was ruled out and why

## Three-Version Example (from this project)

| Version | Goal | Archive Files |
|------|------|------|
| v1 MetaHuman Wrap | Full body template wrap + ARKit 52 + Mixamo | `档案_v1_MetaHumanWrap.md` |
| v2 Mirror Symmetry | ZBrush Smart ReSym in Blender Python | `档案_v2_镜像对称_上.md` + `_下.md` |
| v3 Quad Remesher | Simplified fully automated pipeline | `档案_v3_QuadRemesher_上.md` + `_中.md` + `_下.md` |

## Context Compression

When the conversation gets too long, archive the current state into these MDs — future sessions can load them instead of replaying the full conversation history.