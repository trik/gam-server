#!/usr/bin/env python

import argparse
import ujson as json

from os import path

try:
    import __pypy__  # noqa
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass


def _get_alembic_config():
    from alembic.config import Config
    from gam.settings import DATABASE_URL
    config_file = path.join(path.dirname(path.abspath(__file__)), 'alembic.ini')
    config = Config(config_file)
    config.set_section_option('alembic', 'sqlalchemy.url', DATABASE_URL)
    return config

def make_migration(args):
    from alembic.command import revision
    revision(_get_alembic_config(), autogenerate=True, message=args.migration_name)

def migrate(args):
    from alembic.command import downgrade, upgrade
    if 'revision' not in args or args.revision == 'head':
        upgrade(_get_alembic_config(), 'head')
    else:
        downgrade(_get_alembic_config(), args.revision)

def debug_app(_args):
    import ptvsd
    from wsgiref import simple_server
    from gam.app import create_app
    print("Waiting for debugger attach")
    ptvsd.enable_attach(address=('localhost', 5678))
    ptvsd.wait_for_attach()
    print("Debug attached!")
    print("Starting server...")
    httpd = simple_server.make_server('127.0.0.1', 8000, create_app())
    httpd.serve_forever()

def run_app(_args):
    from gunicorn.app.wsgiapp import WSGIApplication
    wsgi_app = WSGIApplication("%(prog)s [OPTIONS] [APP_MODULE]")
    wsgi_app.app_uri = 'gam.app:create_app()'
    wsgi_app.cfg.set('reload', True)
    wsgi_app.run()

def test(args):
    import pytest
    import gam.models  # noqa
    from sqlalchemy.exc import ProgrammingError
    from gam.database import Base, scoped_session
    
    with scoped_session() as session:
        session.execute("""
            DO $$
            DECLARE
                record RECORD;
            BEGIN
                FOR record IN SELECT trigger_name, event_object_table FROM information_schema.triggers WHERE trigger_schema = 'public' LOOP
                    EXECUTE 'DROP TRIGGER ' || record.trigger_name || ' ON ' || record.event_object_table || ';';
                END LOOP;
                IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'sync_create_change_entry') THEN
                    DROP FUNCTION sync_create_change_entry();
                END IF;
            END $$;
        """)
        session.commit()
        for table in reversed(Base.metadata.sorted_tables):
            try:
                session.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}') THEN
                            DELETE FROM {table};
                            DROP TABLE {table} CASCADE;
                        END IF;
                    END $$;
                """.format(table=table))
                session.commit()
            except ProgrammingError:
                pass
        try:
            session.execute('DELETE FROM alembic_version')
            session.commit()
        except ProgrammingError:
            pass
    migrate(args)
    pytest.main(args=[])

def shell(_args):
    import sys
    from IPython import start_ipython
    sys.argv = ['ipython']
    start_ipython()

def import_labels(args):
    from gam.database import scoped_session
    from locales.models import LanguageLabel

    context = args.context
    labels_file = args.file

    if context not in ('WMS', 'WAPP', ):
        print('\nInvalid context. Use web or app.\n')
        return
    
    try:
        with open(labels_file, 'r') as f:
            cont = f.read()
        labels = json.loads(cont)
        with scoped_session() as session:
            for key in labels:
                exists = session.query(session.query(LanguageLabel).filter(
                    LanguageLabel.label == key
                ).exists()).scalar()
                if not exists:
                    session.add(LanguageLabel(context=context, label=key))
                    session.commit()
    except (FileNotFoundError, IsADirectoryError, TypeError, ValueError):
        print('\nInvalid labels file\n')
        return

def generate_translations(args):
    from locales.tasks import do_generate_translations
    lid = args.language
    do_generate_translations(lid)

def fix_sequences(_args):
    import gam.models  # noqa
    from gam.database import Base, scoped_session

    with scoped_session() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute("""
                DO $$
                DECLARE
                    cur_val INTEGER;
                    max_id INTEGER;
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_class where relname = '{table}_id_seq') THEN
                        SELECT last_value FROM {table}_id_seq INTO cur_val;
                        SELECT MAX(id) FROM {table} INTO max_id;
                        IF cur_val < max_id THEN
                            PERFORM setval('{table}_id_seq', max_id);
                        END IF;
                    END IF;
                END $$;
            """.format(table=table))

def __import_json_data(fixtures):
    from gam.database import scoped_session
    with scoped_session() as session:
        for fixture in fixtures:
            print('Importing {} json data'.format(fixture[0]))
            fixture_file = path.join('.', 'data', '{}.json'.format(fixture[0]))
            f = open(fixture_file, 'r')
            data = json.loads(f.read())
            f.close()
            for d in data:
                instance = fixture[1]().load(d, session=session)
                session.add(instance)
            print('Successfully imported {} json data'.format(fixture[0]))

def import_fixtures(_args):
    from users.schemas import RoleSchema
    fixtures = (
        ('roles', RoleSchema, ),
    )
    __import_json_data(fixtures)

def import_demo_data(_args):
    from users.schemas import UserRoleSchema, UserCreateSchema
    fixtures = (
        ('users', UserCreateSchema, ),
        ('user_roles', UserRoleSchema, ),
    )
    __import_json_data(fixtures)
    fix_sequences(_args)

def encpass(args):
    from users.hasher import make_password
    password = args.password
    print(make_password(password))

def manage():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_debug = subparsers.add_parser('debug')
    parser_debug.set_defaults(func=debug_app)

    parser_run = subparsers.add_parser('run')
    parser_run.set_defaults(func=run_app)

    parser_makemigration = subparsers.add_parser('makemigration')
    parser_makemigration.add_argument('migration_name')
    parser_makemigration.set_defaults(func=make_migration)

    parser_migrate = subparsers.add_parser('migrate')
    parser_migrate.add_argument('--revision', '-r', default='head', required=False)
    parser_migrate.set_defaults(func=migrate)

    parser_test = subparsers.add_parser('test')
    parser_test.set_defaults(func=test)

    parser_shell = subparsers.add_parser('shell')
    parser_shell.set_defaults(func=shell)
    
    parser_import_labels = subparsers.add_parser('import_labels')
    parser_import_labels.add_argument('context')
    parser_import_labels.add_argument('file')
    parser_import_labels.set_defaults(func=import_labels)
    
    parser_generate_translations = subparsers.add_parser('generate_translations')
    parser_generate_translations.add_argument('language')
    parser_generate_translations.set_defaults(func=generate_translations)
    
    parser_fixtures = subparsers.add_parser('fixtures')
    parser_fixtures.set_defaults(func=import_fixtures)
    
    parser_demo_data = subparsers.add_parser('demo_data')
    parser_demo_data.set_defaults(func=import_demo_data)
    
    parser_fix_sequences = subparsers.add_parser('fix_sequences')
    parser_fix_sequences.set_defaults(func=fix_sequences)

    parser_encpass = subparsers.add_parser('encpass')
    parser_encpass.add_argument('password')
    parser_encpass.set_defaults(func=encpass)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    manage()
