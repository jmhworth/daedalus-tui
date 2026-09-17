# {{PROJECT_NAME}}

This is a Daedalus-compatible project with task-mode instructions, feature and parameter directories, optional `topic_files/` for shared task umbrellas, a `.daedalus` worktree config scaffold, and Graphify integrations.

If personal Supabase registration is enabled, keep shared Supabase URL,
publishable/secret keys, and one database access method in this project's
ignored `.env`. Register/Activate reads that project-local file and does not
copy credentials between projects. Do not commit credentials or put them in
feature or parameter files.
