# Smart Corridor security notes

This is a local college-project MVP, not a production identity system.

- Start FastAPI with `--host 127.0.0.1`; this keeps the API on the laptop.
- Keep `data/smart_corridor.db` and `assets/unknown_snapshots` out of Git.
- Do not publish real student names, face embeddings, or snapshots.
- The API limits camera payload size and sends browser security headers.
- CORS is limited to local development origins.
- Unknown and low-confidence results are sent for manual review and never mark attendance.
- Face matching is probabilistic; always provide a manual correction process at school.
