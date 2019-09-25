from gam.database import Base, scoped_session, Session, SoftDelete
from .models import Change

def __create_change_entry_creation_function(session: Session):
    change_table_name = Change.__tablename__
    sql = """
    DO $dobody$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'sync_create_change_entry') THEN
            CREATE FUNCTION sync_create_change_entry() RETURNS TRIGGER AS $funcbody$
            DECLARE
                args_num INT;
                p_table_name VARCHAR;
                p_object_id INT;
                p_entry_type VARCHAR;
                soft_delete BOOL;
                do_insert BOOL;
            BEGIN
                args_num := array_length(TG_ARGV, 1);
                IF args_num <> 2 AND args_num <> 3 THEN
                    RAISE EXCEPTION 'Invalid arguments';
                END IF;
                p_table_name := TG_ARGV[0];
                p_entry_type := TG_ARGV[1];
                IF p_entry_type = 'delete' THEN
                    p_object_id := OLD.id;
                ELSE
                    p_object_id := NEW.id;
                END IF;
                IF args_num = 3 THEN
                    soft_delete := TG_ARGV[2];
                ELSE
                    soft_delete := FALSE;
                END IF;
                IF p_entry_type <> 'insert' AND p_entry_type <> 'update' AND p_entry_type <> 'delete' THEN
                    RAISE EXCEPTION 'Invalid change entry type';
                END IF;
                IF p_entry_type = 'update' AND soft_delete THEN
                    IF OLD.deleted = FALSE AND NEW.deleted = TRUE THEN
                        p_entry_type := 'delete';
                    END IF;
                END IF;

                do_insert := TRUE;
                IF p_entry_type = 'delete' AND EXISTS (
                    SELECT 1 FROM {change_table_name} WHERE table_name = p_table_name AND object_id = p_object_id AND entry_type = 'delete'
                ) THEN
                    do_insert := FALSE;
                END IF;
                IF do_insert THEN
                    INSERT INTO {change_table_name} (table_name, object_id, entry_type) VALUES (p_table_name, p_object_id, p_entry_type);
                END IF;
                RETURN NEW;
            END;
            $funcbody$ LANGUAGE PLPGSQL;
        END IF;
    END
    $dobody$;
    """.format(change_table_name=change_table_name)
    session.execute(sql)

def __create_after_insert_trigger(session: Session, model_cls: Base):
    table_name = model_cls.__tablename__
    trigger_name = 'sync_change_after_insert_{table_name}_trigger'.format(table_name=table_name)

    sql = """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')
        AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = '{trigger_name}') THEN
            CREATE TRIGGER {trigger_name}
            AFTER INSERT ON {table_name}
            FOR EACH ROW EXECUTE PROCEDURE sync_create_change_entry('{table_name}', 'insert');
        END IF;
    END
    $$;
    """.format(trigger_name=trigger_name, table_name=table_name)
    session.execute(sql)

def __create_after_update_trigger(session: Session, model_cls: Base, soft_delete: bool):
    table_name = model_cls.__tablename__
    trigger_name = 'sync_change_after_update_{table_name}_trigger'.format(table_name=table_name)

    sql = """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')
        AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = '{trigger_name}') THEN
            CREATE TRIGGER {trigger_name}
            AFTER UPDATE ON {table_name}
            FOR EACH ROW EXECUTE PROCEDURE sync_create_change_entry('{table_name}', 'update', {soft_delete});
        END IF;
    END
    $$;
    """.format(trigger_name=trigger_name, table_name=table_name, soft_delete='TRUE' if soft_delete else 'FALSE')
    session.execute(sql)

def __create_after_delete_trigger(session: Session, model_cls: Base):
    table_name = model_cls.__tablename__
    trigger_name = 'sync_change_after_delete_{table_name}_trigger'.format(table_name=table_name)

    sql = """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')
        AND NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = '{trigger_name}') THEN
            CREATE TRIGGER {trigger_name}
            AFTER DELETE ON {table_name}
            FOR EACH ROW EXECUTE PROCEDURE sync_create_change_entry('{table_name}', 'delete');
        END IF;
    END
    $$;
    """.format(trigger_name=trigger_name, table_name=table_name)
    session.execute(sql)

def check_triggers(model_cls):
    with scoped_session() as session:
        __create_change_entry_creation_function(session)
        __create_after_insert_trigger(session, model_cls)
        __create_after_update_trigger(session, model_cls, issubclass(model_cls, SoftDelete))
        __create_after_delete_trigger(session, model_cls)
