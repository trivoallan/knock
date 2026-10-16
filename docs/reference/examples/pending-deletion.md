# Pending-deletion (soft delete)

When a tag leaves the selection, `deletionMode: mark` attaches a `pending-deletion` OCI referrer instead of deleting it — the image stays pullable until an external reaper (e.g. `knock purge`) acts. Marks auto-clear if the tag re-enters the selection. See [Deletion & retention](../../explanation/deletion-and-retention.md) for the full model.

[`docs/examples/pending-deletion/pending-deletion.yml`](../../examples/pending-deletion/pending-deletion.yml)

Run it: `uv run knock reconcile docs/examples/pending-deletion`
