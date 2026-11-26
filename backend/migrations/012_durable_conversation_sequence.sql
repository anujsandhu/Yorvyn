-- Allocate message order under the conversation row lock, including across API workers.
BEGIN;
CREATE OR REPLACE FUNCTION public.yorvyn_order_ai_message() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM id FROM public.yorvyn_ai_sessions
      WHERE id = NEW.session_id AND user_id = NEW.user_id AND status = 'active' FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Conversation unavailable';
    END IF;
    SELECT COALESCE(MAX(sequence_number), 0) + 1 INTO NEW.sequence_number
      FROM public.yorvyn_ai_messages WHERE session_id = NEW.session_id;
    RETURN NEW;
END;
$$;
CREATE INDEX IF NOT EXISTS idx_ai_messages_session_sequence
    ON public.yorvyn_ai_messages(session_id, sequence_number, id);
CREATE OR REPLACE TRIGGER yorvyn_order_ai_message BEFORE INSERT ON public.yorvyn_ai_messages
    FOR EACH ROW EXECUTE FUNCTION public.yorvyn_order_ai_message();

CREATE OR REPLACE FUNCTION public.yorvyn_count_ai_message() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE public.yorvyn_ai_sessions SET message_count = message_count + 1,
        last_message_at = NEW.created_at, updated_at = NOW()
      WHERE id = NEW.session_id;
    RETURN NULL;
END;
$$;
CREATE OR REPLACE TRIGGER yorvyn_count_ai_message AFTER INSERT ON public.yorvyn_ai_messages
    FOR EACH ROW EXECUTE FUNCTION public.yorvyn_count_ai_message();
UPDATE public.yorvyn_ai_sessions s SET message_count = actual.n FROM (
    SELECT session_id, COUNT(*) AS n FROM public.yorvyn_ai_messages GROUP BY session_id
) actual WHERE s.id = actual.session_id AND s.message_count <> actual.n;
COMMIT;
