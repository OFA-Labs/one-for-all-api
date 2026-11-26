"""History: owner-scoped, read-only task history (read model).

The future task engine writes immutable task snapshots through the service-only ingest
endpoint; the UI only reads them. See HISTORY_IMPLEMENTATION_PLAN.md.
"""
