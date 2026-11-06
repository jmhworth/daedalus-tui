CREATE TABLE IF NOT EXISTS medley.music_context (
  user_id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  context_text text NOT NULL DEFAULT '',
  feedback_count integer NOT NULL DEFAULT 0 CHECK (feedback_count >= 0),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE medley.music_context ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON medley.music_context TO authenticated;

CREATE POLICY "Users can read their own music context"
  ON medley.music_context FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own music context"
  ON medley.music_context FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own music context"
  ON medley.music_context FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION medley.increment_my_music_feedback_count()
RETURNS integer
LANGUAGE sql
SECURITY INVOKER
SET search_path = ''
AS $$
  INSERT INTO medley.music_context (user_id, feedback_count)
  VALUES (auth.uid(), 1)
  ON CONFLICT (user_id) DO UPDATE
    SET feedback_count = medley.music_context.feedback_count + 1,
        updated_at = now()
  RETURNING feedback_count;
$$;

GRANT EXECUTE ON FUNCTION medley.increment_my_music_feedback_count() TO authenticated;
