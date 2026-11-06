CREATE TABLE IF NOT EXISTS medley.song_moments (
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  listened_on date NOT NULL,
  song_name text NOT NULL,
  artist text NOT NULL,
  note text NOT NULL DEFAULT '',
  play_count integer NOT NULL DEFAULT 1,
  CONSTRAINT song_moments_user_day_song_key
    UNIQUE (user_id, listened_on, song_name, artist)
);

ALTER TABLE medley.song_moments ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON medley.song_moments TO authenticated;

CREATE POLICY "Users can read their own song moments"
  ON medley.song_moments FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own song moments"
  ON medley.song_moments FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own song moments"
  ON medley.song_moments FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own song moments"
  ON medley.song_moments FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);
