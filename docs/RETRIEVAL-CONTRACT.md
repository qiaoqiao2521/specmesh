# Optional evidence retrieval v0

Run from the source checkout (not the independent runtime ZIP):

```sh
python3 scripts/retrieve_evidence.py --project qiaoqiao2521/specmesh \
  --spec spec://map-v0 'Map v0 cache_is_fresh'
```

The CLI rebuilds the existing Map v0 graph in memory. It identifies the spec by exact ID or a lexical name match, requires current scoped anchors, follows asserted code/test relations and ranks matching symbols inside those files. Plans matched by name are candidates only. Unrecognized or ambiguous requests never silently pick another spec; use `--spec` and `--area` to clarify. Supply `--revision` as a full commit for external joins. This is a caller-supplied target identity, not proof that a working tree equals that commit; the actual input state has its own source fingerprint.

## External evidence is opt-in

All bindings match the exact lower-case `owner/repository`, `spec_uri`, `area` and full `revision`. Keep private binding files outside the source tree. No command starts a native history crawl, reads Drive bodies, uses credentials, writes back to another tool, or promotes external context to reviewed project memory.

- **History:** Export selected fragments with AgentTraceMesh’s native `materials SESSION --index-revision REV --message INDEX:OFFSET` on your authorized source. Provide `--history-materials` and a separate `--history-binding` JSON object with `schema: "specmesh-history-binding-v0"`, the four scope fields, and the expected `source`, `store_id`, `session_id`, `index_revision` from review. The command returns only locators; it drops text, Markdown and local paths. Revision mismatch is disallowed; indexed selection is not live verification. For an explicitly recorded unsuccessful scoped search, a binding without materials may set `search_status` to `not_indexed`, `no_match` or `failed`; these are reported as supplied, not inferred.
- **ControlMesh:** `--control-export` accepts a caller-prepared JSON object with `schema: "controlmesh-receipts-v0"` and `items` containing the four scope fields, `task_id`, `run_id`, `event_id`, `outcome` (`succeeded`, `failed`, `cancelled`, or `unknown`). This is not an automatic native ControlMesh export. A matched failed run stays a failed run.
- **Drive:** `--drive-manifest` accepts `{"schema_version":1,"items":[...]}`; each row contains the four scope fields, `file_id`, `title`, and UTC `observed_at`. Build the manifest only from approved queries/files you can bind to the exact task; the tool reconstructs canonical file links from the IDs. A match is a metadata reference, not proof of current access or freshness. Do not bulk copy Drive.
- Check each source’s `status`: `matched`, `partial`, `not_checked`, `not_indexed`, `no_match`, `unbound`, or `failed`. An empty list alone does not tell the story. A missing source is never called a verified non-match.

This is a separate, optional CLI in the source tree. No changes to the versioned standard or existing machine interfaces. No vector index or RAG service is needed to run it; measure real paraphrase misses before adding one.
