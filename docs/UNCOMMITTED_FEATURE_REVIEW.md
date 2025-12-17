# Uncommitted Feature Review (Event collection & Integrated daily report)

Purpose: capture review notes for the uncommitted design docs and implementation stubs before coding starts.

## Summary
- Event schema/prototype leaves migrations and privacy/classification details unresolved; the unified timeline view is misaligned with the current schema.
- Integrated report aggregator/prompt prototypes have data model mismatches that will raise errors once wired, plus missing repository methods/field-name gaps.
- Prompt helpers still return placeholder text, so LLM output would be low value until they are implemented.

## Event collection (EVENTVIEW)
- Schema not wired: `lifelog-system/src/lifelog/database/schema_extension_events.sql` defines tables/views but `lifelog-system/src/lifelog/database/schema.py` and migrations do not create them; any caller of planned APIs would fail until integrated.
- The unified timeline view in `docs/EVENT_COLLECTION_DESIGN.md` references a `windows` table that does not exist; the actual DB only stores `window_hash`, so the design for window title lookup needs revision or an added table.
- `schema_extension_events.sql` embeds `ORDER BY` inside the view; SQLite does not guarantee ordering for views, so consumers must `ORDER BY` explicitly.
- `SystemEvent.from_raw_event` (`lifelog-system/src/lifelog/collectors/event_collector_interface.py`:58-75) assumes ISO timestamp strings and defaults to `now()`. Windows/journald timestamps will need conversion to avoid `ValueError` or timezone drift.
- Privacy/classification hooks are stubs: the message is always stored raw and hashed (no config for hash-only), usernames are never hashed, and `EventClassifier.classify_event` currently ignores rules (`event_collector_interface.py`:94-111). Severity is unconstrained (0-100) and not clamped.
- Planned config knobs (`event_collection.yaml`) are not wired into collectors; log-level/facility filters are unused and there is no retention policy for `system_events`.

## Integrated daily report
- Missing dependencies: the aggregator expects `DatabaseManager.get_events_by_date_range` and `InfoCollectorRepository.fetch_reports_by_date` (`lifelog-system/src/info_collector/data_aggregator.py`:161, 231) which do not exist yet.
- Field-name mismatches will crash: deep-research rows expose `researched_at`, but the timeline builder reads `created_at` (`data_aggregator.py`:311). Blank or missing timestamps passed to `datetime.fromisoformat` (`data_aggregator.py`:263, 275, 287, 299, 311) will raise `ValueError`.
- Timeline type mismatch: the aggregator returns `UnifiedTimelineEntry` dataclasses (`data_aggregator.py`:235-323), while the prompt summarizer expects dicts and uses `.get` (`lifelog-system/src/info_collector/prompts/integrated_report_generation.py`:166-177). `generate_integrated_report.py` calls `build_integrated_prompt(date, data, detail_level)` (`lifelog-system/src/info_collector/jobs/generate_integrated_report.py`:56-64), but the function signature requires individual lists, so uncommenting would fail.
- Summaries are placeholders (`_summarize_lifelog`/`_summarize_browser` in `lifelog-system/src/info_collector/prompts/integrated_report_generation.py`:81-118), so the LLM would receive generic text even when data exists.
- Time handling is underspecified: no timezone normalization/user-facing format in the aggregator; mixed sources may order incorrectly without explicit normalization.

## Suggested next steps
- Decide the schema integration/migration plan for `system_events`, and clarify whether window titles are required; adjust views accordingly.
- Wire privacy/classification config into collector interfaces, clamp severity, and handle timestamp parsing with explicit timezone conversion.
- Align aggregator/prompt/job signatures and data shapes; add guards for missing timestamps/fields and implement missing repository methods or adjust expectations.
- Implement summarization helpers before relying on LLM output; add basic tests for timeline construction and prompt building once implemented.
