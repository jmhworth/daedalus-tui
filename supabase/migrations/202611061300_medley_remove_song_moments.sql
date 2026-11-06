ALTER TABLE medley.songs
  ADD COLUMN notes text NOT NULL DEFAULT '';

DROP TABLE medley.song_moments;

DROP FUNCTION IF EXISTS medley.search_my_songs(text);

CREATE FUNCTION medley.search_my_songs(p_keyword text)
RETURNS TABLE (
  user_id uuid,
  name text,
  artist text,
  notes text,
  musical_attributes text[],
  personal_attributes text[]
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
  SELECT songs.user_id, songs.name, songs.artist, songs.notes,
         songs.musical_attributes, songs.personal_attributes
  FROM medley.songs AS songs
  WHERE songs.user_id = auth.uid()
    AND NULLIF(btrim(p_keyword), '') IS NOT NULL
    AND (
      songs.name ILIKE '%' || btrim(p_keyword) || '%'
      OR songs.artist ILIKE '%' || btrim(p_keyword) || '%'
      OR EXISTS (
        SELECT 1
        FROM unnest(songs.musical_attributes || songs.personal_attributes) AS attrs(value)
        WHERE attrs.value ILIKE '%' || btrim(p_keyword) || '%'
      )
    );
$$;

GRANT EXECUTE ON FUNCTION medley.search_my_songs(text) TO authenticated;
