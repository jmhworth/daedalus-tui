# {{PROJECT_NAME}}

This is a Daedalus-compatible project with task-mode instructions, feature and parameter directories, optional `topic_files/` for shared task umbrellas, a `.daedalus` worktree config scaffold, and Graphify integrations.

If personal Supabase registration is enabled, keep shared Supabase URL,
publishable/secret keys, and one database access method in the Daedalus
launch-root `.env`. Daedalus
syncs this project's ignored `.env` and prepares its registered schema at launch;
do not commit credentials or put them in feature or parameter files.
