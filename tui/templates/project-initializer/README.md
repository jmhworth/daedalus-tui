# {{PROJECT_NAME}}

This is a Daedalus-compatible project with task-mode instructions, feature and parameter directories, optional `topic_files/` for shared task umbrellas, a `.daedalus` worktree config scaffold, and Graphify integrations.

If personal Supabase registration is enabled, Activate copies the shared
Supabase API URL and keys plus the registered schema into a managed block in
this project's ignored `.env`. The Daedalus TUI root `.env` remains the source
for credentials, including database access settings used for migrations. Store
application data in the registered schema (the project slug), not `public`.
Do not commit credentials or put them in feature or parameter files.
