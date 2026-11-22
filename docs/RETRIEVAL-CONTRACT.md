# Optional evidence retrieval v0

Run from the source checkout (not the independent runtime ZIP):

```sh
python3 scripts/retrieve_evidence.py --project qiaoqiao2521/specmesh \
  --spec spec://map-v0 'Map v0 cache_is_fresh'
```

The CLI rebuilds the existing Map v0 graph in memory. It identifies the spec by exact ID or a lexical name match, requires current scoped anchors, follows asserted code/test relations and ranks matching symbols inside those files. Plans matched by name are candidates only. Unrecognized or ambiguous requests never silently pick another spec; use `--spec` and `--area` to clarify. Supply `--revision` as a full commit for external joins. This is a caller-supplied target identity, not proof that a working tree equals that commit; the actual input state has its own source fingerprint.

## External evidence is opt-in

All bindings match the exact lower-case `owner/repository`, `spec_uri`, `area` and full `revision`. Keep private binding files outside the source tree. The retrieval CLI does not start a native history crawl, read Drive bodies, use credentials, write back to another tool, or promote external context to reviewed project memory.

- **History:** Export selected fragments with AgentTraceMesh’s native `materials SESSION --index-revision REV --message INDEX:OFFSET` on your authorized source. Provide `--history-materials` and a separate `--history-binding` JSON object with `schema: "specmesh-history-binding-v0"`, the four scope fields, and the expected `source`, `store_id`, `session_id`, `index_revision` from review. The command returns only locators; it drops text, Markdown and local paths. Revision mismatch is disallowed; indexed selection is not live verification. For an explicitly recorded unsuccessful scoped search, a binding without materials may set `search_status` to `not_indexed`, `no_match` or `failed`; these are reported as supplied, not inferred.
- **ControlMesh:** `--control-export` accepts a caller-prepared JSON object with `schema: "controlmesh-receipts-v0"` and `items` containing the four scope fields, `task_id`, `run_id`, `event_id`, `outcome` (`succeeded`, `failed`, `cancelled`, or `unknown`). This is not an automatic native ControlMesh export. A matched failed run stays a failed run.
- **Drive:** `--drive-manifest` accepts `{"schema_version":1,"items":[...]}`; each row contains the four scope fields, `file_id`, `title`, and UTC `observed_at`. Build the manifest only from approved queries/files you can bind to the exact task; the tool reconstructs canonical file links from the IDs. A match is a metadata reference, not proof of current access or freshness. Do not bulk copy Drive.
- Check each source’s `status`: `matched`, `partial`, `not_checked`, `not_indexed`, `no_match`, `unbound`, or `failed`. An empty list alone does not tell the story. A missing source is never called a verified non-match.

## History from compressed cases

Use AgentTraceMesh's existing case catalogue and native material exporter. A
`compress` or `recall` response is not a `history.indexed-materials.v1` packet.
Run the following from the selected AgentTraceMesh checkout, with source, cache
and case paths explicitly chosen outside the SpecMesh source tree:

```sh
python3 -m history_core --source codex --source-path "$SOURCE_PATH" \
  --data-dir "$CACHE_DIR" compress "$SESSION_ID" --save --case-dir "$CASE_DIR"
python3 -m history_core recall --directory "$CASE_DIR" --query 'Map v0 cache_is_fresh'
python3 -m history_core cases --directory "$CASE_DIR" show "$CASE_ID"
```

1. Select the case by its returned ID and read its full `evidence` using
   `cases show`. Recall displays at most three evidence entries; later user
   corrections or stop requests may be absent from that compact result. Read
   continuation pages when `has_more` or `next_text_offset` indicates them.
2. Review the relevant original message locators. `message_index` is the
   original message slot, including gaps for hidden messages; it is neither a
   recall rank nor a JSONL line number. Preserve `text_offset` in indexed-text
   coordinates and the exact `index_revision`.
3. Export at most five selected windows on the same selected source/cache:

   ```sh
   python3 -m history_core --source codex --source-path "$SOURCE_PATH" \
     --data-dir "$CACHE_DIR" materials "$SESSION_ID" \
     --index-revision "$INDEX_REVISION" --message "$MESSAGE_INDEX:$TEXT_OFFSET" \
     > "$MATERIALS_FILE"
   ```

   Repeat `--message` for other reviewed windows, including a later correction
   when relevant. Require the selected case evidence and the new packet to
   agree on `source`, `store_id`, `session_id` and `index_revision`.
4. Create the separate reviewed `specmesh-history-binding-v0` object with those
   four native identity fields and `project`, `spec_uri`, `area`, `revision`.
   Pass it and the unmodified native packet to `retrieve_evidence.py` through
   `--history-binding` and `--history-materials`. Keep history as
   `indexed_history_context`; do not write an automated summary into asserted
   `mem://` relations. A matched locator does not establish current task success.

For a check against newly observed source content, explicitly run native
`refresh` on that selected source before compression and review the resulting
revision. If export reports `index_revision_changed`, select evidence again
from the refreshed source. Do not replace the revision on old evidence to make
it pass. Saved or manually edited cases can still refer to an older snapshot;
`cases show` does not refresh their facts. An unchanged index is not proof that
the live recording has not changed.

The public AgentTraceMesh `materials` export now shares the existing
Linux/Windows store identity used by compression. Older public exports used a
`local` namespace, which remains the lower-level exporter's compatibility default.
The public identity fix is recorded in [AgentTraceMesh b9e1e73](https://github.com/qiaoqiao2521/AgentTraceMesh/commit/b9e1e739f64de8ce6918a96c2eebb436064723bc).
SpecMesh continues accepting an old packet with its original, exactly matching
reviewed binding as historical context. It does not translate namespaces or
rewrite case IDs. A new export needs a matching reviewed binding; mixing an old
binding with a new store identity must remain `unbound`. Do not edit native
packet identities or hashes to bypass that mismatch.

The native integration regression is optional and runs only against an
explicit local checkout, using synthetic recordings in temporary directories:

```sh
AGENTTRACEMESH_CHECKOUT=/path/to/AgentTraceMesh \
  python3 -B -m unittest discover -s tests -p test_retrieve_evidence.py -v
```

Without that variable the test is skipped. This adds no runtime dependency or
joint release requirement. The CLI exit status only describes query execution;
consumers must still inspect each source's `status` and verification fields.

This is a separate, optional CLI in the source tree. No changes to the versioned standard or existing machine interfaces. No vector index or RAG service is needed to run it; measure real paraphrase misses before adding one.
