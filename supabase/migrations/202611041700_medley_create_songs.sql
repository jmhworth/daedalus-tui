CREATE TABLE IF NOT EXISTS medley.songs (
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  name text NOT NULL,
  artist text NOT NULL,
  musical_attributes text[] NOT NULL DEFAULT '{}',
  personal_attributes text[] NOT NULL DEFAULT '{}',
  CONSTRAINT songs_user_name_artist_key UNIQUE (user_id, name, artist)
);

ALTER TABLE medley.songs ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON medley.songs TO authenticated;

CREATE POLICY "Users can read their own songs"
  ON medley.songs FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own songs"
  ON medley.songs FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own songs"
  ON medley.songs FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own songs"
  ON medley.songs FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);
