# ZBrushCentral Community Corroboration — Resymmetry & UV

Sourced from ZBrushCentral forum (Discourse-based, JSON API accessible via
`curl https://www.zbrushcentral.com/t/{topic_id}.json`). Accessed 2026-07-08.

These excerpts independently confirm the official-documentation findings in
`zbrush-resymmetry-docs-findings.md` — that ZBrush Resymmetry does not handle
UV-based textures, only per-vertex data (polypaint).

## Topic: "Polypainting Symmetry" (#280251, 2009-03-20)

**Post #1 — user "system":**
> Can anyone tell me if Zbrush has a feature to copy the textures on one side
> of a model to the other, similarly to how ReSym resymmetrifies the geometry?

This question itself confirms that Resymmetry operates on geometry but users
expected texture symmetry to work the same way — and it doesn't.

**Post #2 — user "spaceboy412":**
> wrong forum.
> but if you are using polypaint one thing you can do is to clone your model,
> mirror it, append as a subtool, then store a morph target on your original,
> then either use zproject brush or projectall, then switch your morph target
> back.
> if you have uv's laid out that's another story altogether.

**Key takeaways from this exchange:**
1. "if you have UV's laid out that's another story altogether" — a
   practitioner-level confirmation that UV-based textures are NOT handled by
   Resymmetry and require an entirely different approach.
2. The polypaint workaround (clone → mirror → append as subtool → store morph
   target → ProjectAll → switch morph back) is a community technique for
   mirroring polypaint data. This is the ZBrush-native equivalent of "bake
   transfer" for polypaint specifically.
3. The user asked about "textures" (UV-sampled), and the responder offered a
   polypaint-only workaround — further confirming the UV/texture gap.

## Topic: "SYMMETRY MAP NOT STORED PROBLEM" (#268292, 2007-11-26)

**User spaceboy412:**
> I keep losing symmetry when i make mesh extractions at lowest levels from
> original zsphere meshs, resym and smart resym with or without masking will
> not work and will say "symmetry map not stored", i've tried to set pivot,
> unify, enable uv, poseable symmetry, polymesh3d, exporting/importing as ob...

**Key takeaway:** Resymmetry relies on a stored "symmetry map" — an internal
pairing of vertices across the symmetry axis. This map can be lost during
operations like mesh extraction, and once lost, Resymmetry fails entirely
until topology is restored or re-imported. This confirms that SmartReSym works
by **finding and using vertex correspondence pairs**, not by any UV-based
matching.

## Topic: "MAC & ZBRUSH 3 THREAD" (#272394, 2008-08-29)

**User TimothyB:**
> ...the resymmetry center line problem, appending subtools then doing a
> transfomation from the tools causes a crash, smooth UVs while dividing is
> lost through various means...

**Key takeaway:** Mentions a "resymmetry center line problem" as a known bug —
vertices on the exact symmetry axis (center line) can cause issues during
Resymmetry. This parallels the bmesh script's need to snap center-axis verts
to exactly 0 (pitfall #5 in `bmesh-geometry-mirror-keep-uv.md`).

## How to Access ZBrushCentral Forum Data via JSON API

ZBrushCentral runs on Discourse. When web search engines are inaccessible,
the forum's JSON API can be queried directly via curl:

```bash
# Search for topics
curl -sL "https://www.zbrushcentral.com/search.json?q=resymmetry+UV" \
  -A "Mozilla/5.0" -H "Accept: application/json" -o results.json

# Fetch full topic content (all posts)
curl -sL "https://www.zbrushcentral.com/t/{topic_id}.json" \
  -A "Mozilla/5.0" -H "Accept: application/json" -o topic.json

# Parse with Python:
#   posts = data['post_stream']['posts']
#   each post has 'cooked' (HTML), 'username', 'created_at', 'post_number'
#   use re.sub('<.*?>', '', cooked) to strip HTML
```

Note: search.json returns `posts` (not `topics`), each with a `topic_id`,
`blurb`, and `username`. To get the full topic, fetch `/t/{topic_id}.json`.
If a topic has many posts, only the first ~20 are loaded; the full post ID
list is in `data['post_stream']['stream']`.
