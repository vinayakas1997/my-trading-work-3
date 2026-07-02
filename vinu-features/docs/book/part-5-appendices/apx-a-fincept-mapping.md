# Appendix A — Fincept Mapping

| Fincept step | vinu-features |
|--------------|---------------|
| Step 3 — indicators | Presets + compute engine |
| Step 4 — conditions | Stored as `conditions` text in manifest only (evaluation in vinu-strategy) |

vinu-features does **not** evaluate rules; it materializes feature columns for downstream strategy code.
