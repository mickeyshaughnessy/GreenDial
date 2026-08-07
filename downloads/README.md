# App downloads

Place release binaries here for the site download CTA:

- `GreenDial.apk` — Android install (served at `/download/android`)

These files are **gitignored**. `deploy.sh` copies a local
`mobile/dist/GreenDial-1.0.0.apk` (or `downloads/GreenDial.apk`) to the
server webroot when present.
