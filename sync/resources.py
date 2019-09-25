import ujson as json

from falcon import (
    HTTP_BAD_REQUEST, HTTP_CONFLICT, HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_FOUND, HTTP_OK, Request, Response
)

from sqlalchemy import false, Sequence

from gam.database import Fixed, scoped_session, SoftDelete
from users.utils import get_user_roles_map
from . import exceptions as exc
from .models import Change
from .schemas import ChangeSchema, UpwardChangeSchema
from .utils import get_sync_model

class SyncResource:
    def __can_read_change(self, req, item):
        model_cls, _, permissions = get_sync_model(item['table_name'])
        ctx = {
            'model': model_cls,
            'roles': get_user_roles_map(req.context.user.id, extended=True),
            'user': req.context.user
        }
        for perm in permissions:
            if not perm.can_read_change(ctx, item):
                return False
        return True

    def on_get_changes(self, req: Request, resp: Response):
        since = req.get_param_as_int('since', required=False, default=0)
        batch_size = req.get_param_as_int('batch_size', required=False, default=50)

        i = 0
        end = False
        items = []
        with scoped_session() as session:
            while i < batch_size and not end:
                obj = session.query(Change).filter(Change.id > since).first()
                if obj is None:
                    end = True
                    break
                item, errors = ChangeSchema().dump(obj)
                
                if errors is not None:
                    errors_num = len(errors)
                    if errors_num > 0:
                        resp.status = HTTP_BAD_REQUEST
                        resp.body = json.dumps({'errors': errors})
                        return
                
                if self.__can_read_change(req, item):
                    items.append(item)
                
                since = since + 1
                i = i + 1
        
        resp.status = HTTP_OK
        resp.body = json.dumps(items)
    
    def on_post_change(self, req: Request, resp: Response):
        try:
            input_data = json.loads(req.stream.read(req.content_length or 0))
        except (ValueError, KeyError):
            resp.status = HTTP_BAD_REQUEST
            return
        
        changes, errors = UpwardChangeSchema().load(input_data, many=True)
        if errors is not None:
            errors_num = len(errors)
            if errors_num > 0:
                resp.status = HTTP_BAD_REQUEST
                resp.body = json.dumps({'errors': errors})
                return
        
        results = []
        for change in changes:
            try:
                res, conflict = self.__process_upward_change(change)
            except (exc.FixedModel, exc.InvalidSyncEntry, exc.InvalidSyncEntryType, exc.InvalidSyncModel, exc.ModelNotFound):
                resp.status = HTTP_BAD_REQUEST
                resp.body = json.dumps({'errors': errors})
                return
            
            results.append(res)
            if conflict:
                resp.status = HTTP_CONFLICT
                resp.body = json.dumps(results)
        
        resp.status = HTTP_OK
        resp.body = json.dumps(results)


    def on_get_doc(self, resp: Response, obj_id=None):
        if obj_id is None:
            resp.status = HTTP_METHOD_NOT_ALLOWED
            return
        
        try:
            cid = int(obj_id)
        except (TypeError, ValueError):
            resp.status = HTTP_BAD_REQUEST
            resp.body = '{"message": "Invalid id"}'
            return
        
        with scoped_session() as session:
            change = session.query(Change).filter(Change.id == cid).first()
            if change is None:
                resp.status = HTTP_NOT_FOUND
                return
            
            obj = self.__get_object_dump_by_change(session, change)

            if obj is None:
                resp.status = HTTP_NOT_FOUND
                return
            
        resp.status = HTTP_OK
        resp.body = json.dumps(obj)

    def on_post_docs(self, req: Request, resp: Response):
        try:
            input_data = json.loads(req.stream.read(req.content_length or 0))
            changes_ids = [int(c) for c in input_data['changes']]
        except (ValueError, KeyError):
            resp.status = HTTP_BAD_REQUEST
            return

        if changes_ids is None:
            resp.status = HTTP_BAD_REQUEST
            return
        
        results = []
        with scoped_session() as session:
            changes = session.query(Change).filter(Change.id.in_(changes_ids)).all()

            for change in changes:
                obj = self.__get_object_dump_by_change(session, change)
                if obj is None:
                    continue
                
                change_dump, _ = ChangeSchema().dump(change)
                change_dump.update({'object': obj})
                results.append(change_dump)
        
        resp.status = HTTP_OK
        resp.body = json.dumps(results)
    
    def __process_upward_change(self, change):
        model_cls, schema_cls, _ = get_sync_model(change.table_name)
        if model_cls is None or schema_cls is None:
            raise exc.InvalidSyncModel(change.table_name)
        
        entry_type = change.entry_type
        if entry_type == 'insert':
            return self.__process_upward_insert_change(change)
        if entry_type == 'update':
            return self.__process_upward_update_change(change)
        if entry_type == 'delete':
            return self.__process_upward_delete_change(change)
        raise exc.InvalidSyncEntryType(entry_type)
    
    def __process_upward_delete_change(self, change):
        with scoped_session() as session:
            instance, schema_cls = self.__get_object_by_change(session, change)

            if instance is None:
                raise exc.ModelNotFound(change.table_name, change.object_id)
            
            model_cls = schema_cls.Meta.model
            
            if issubclass(model_cls, Fixed) and instance.fixed:
                raise exc.FixedModel(change.table_name, change.object_id)
            
            if issubclass(model_cls, SoftDelete):
                instance.deleted = True
                session.add(instance)
            else:
                session.delete(instance)
            
            return {
                'sequence': change.sequence,
                'ok': True
            }
    
    def __process_upward_update_change(self, change):
        with scoped_session() as session:
            instance, schema_cls = self.__get_object_by_change(session, change)

            if instance is None:
                raise exc.ModelNotFound(change.table_name, change.object_id)
            
            update, err = schema_cls().load(change.object, session=session, instance=instance)
            if err is not None:
                err_num = len(err)
                if err_num > 0:
                    raise exc.InvalidSyncEntry(change.table_name, change.object)
            
            session.add(update)

            return {
                'sequence': change.sequence,
                'ok': True
            }
    
    def __process_upward_insert_change(self, change):
        with scoped_session() as session:
            existing, schema_cls = self.__get_object_by_change(session, change)
            if existing is not None:
                return {
                    'sequence': change.sequence,
                    'ok': False,
                    'error': 'conflict',
                    'extra': {
                        'next_id': self.__reserve_id(change.table_name)
                    }
                }
            
            instance, err = schema_cls().load(change.object)
            if err is not None:
                err_num = len(err)
                if err_num > 0:
                    raise exc.InvalidSyncEntry(change.table_name, change.object)
            
            session.add(instance)
            
            return {
                'sequence': change.sequence,
                'ok': True
            }
    
    def __reserve_id(self, change):
        sequence_name = '{}_id_seq'.format(change.table_name)
        with scoped_session() as session:
            return session.execute(Sequence(sequence_name).next_value()).scalar() # noqa

    def __get_object_by_change(self, session, change):
        model_cls, schema_cls, _ = get_sync_model(change.table_name)
        if model_cls is None or schema_cls is None:
            return None
        
        qf = [model_cls.id == change.object_id, ]
        if issubclass(model_cls, SoftDelete):
            qf.append(model_cls.deleted == false())
        return session.query(model_cls).filter(*qf).first(), schema_cls

    def __get_object_dump_by_change(self, session, change):
        obj, schema_cls = self.__get_object_by_change(session, change)

        if obj is None:
            return None
        obj_dump, _ = schema_cls().dump(obj)

        return obj_dump
