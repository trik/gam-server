import ujson as json

from falcon import (
    HTTP_BAD_REQUEST, HTTP_CONFLICT, HTTP_CREATED,
    HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_FOUND,
    HTTP_OK, MEDIA_JSON, Request, Response
)

from marshmallow_sqlalchemy import ModelSchema

from sqlalchemy import and_, false, or_, not_ as base_not_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import InstrumentedAttribute

from users.utils import get_user_roles_map
from .database import Base, Fixed, scoped_session, SoftDelete
from .errors import InvalidSelectorException

def not_(*args):
    return base_not_(and_(*args))

def nor_(*args):
    return base_not_(or_(*args))

class ModelBaseResource:
    model_class = Base
    permissions = ()

    def get_base_query(self, session):
        return session.query(self.model_class)

    def _can_create(self, req: Request, ctx, new_obj):
        perms_num = len(self.permissions)
        if perms_num == 0:
            return True
        ctx.update({
            'roles': self.__get_user_roles(req),
            'model': self.model_class,
            'user': req.context.user,
        })
        for perm in self.permissions:
            if not perm.can_create(ctx, new_obj):
                return False
        return True

    def _apply_permissions(self, req: Request, ctx, query):
        perms_num = len(self.permissions)
        if perms_num == 0:
            return query
        ctx.update({
            'roles': self.__get_user_roles(req),
            'model': self.model_class,
            'user': req.context.user,
        })
        for perm in self.permissions:
            query = perm.apply_filter(ctx, query)
        
        return query

    def __get_user_roles(self, req: Request):
        return get_user_roles_map(req.context.user.id)

class ModelListResource(ModelBaseResource):
    schema_class = ModelSchema
    schema_classes = {}

    def get_list_schema_class(self):
        raise NotImplementedError

    def _apply_limit(self, query, params):
        default_limit = 20
        try:
            limit = int(params.get('limit', default_limit))
        except TypeError:
            limit = default_limit
        if limit in (0, -1, ):
            return query
        return query.limit(limit)
    
    def _apply_offset(self, query, params):
        default_offset = 0
        try:
            offset = int(params.get('offset', default_offset))
        except TypeError:
            offset = default_offset
        return query.offset(offset)
    
    def _apply_sort(self, query, params):
        if 'sort' not in params:
            return query
        sort_arr = params['sort'] if isinstance(params['sort'], list) else [params['sort']]
        for sort_str in sort_arr:
            sorts = sort_str.split(',')
            for sort in sorts:
                if ':' not in sort:
                    continue
                parts = sort.split(':')
                parts_len = len(parts)
                if parts_len != 2:
                    continue
                attr = getattr(self.model_class, parts[0], None)
                if attr is None or not isinstance(attr, InstrumentedAttribute):
                    continue
                if parts[1] == 'asc':
                    query = query.order_by(attr)
                elif parts[1] == 'desc':
                    query = query.order_by(attr.desc())
        return query

class ModelDeleteAllResource(ModelBaseResource):
    def on_post(self, req: Request, resp: Response):
        try:
            params = json.loads(req.stream.read(req.content_length or 0))
            ids = params['ids']
        except (KeyError, TypeError, ValueError):
            resp.status = HTTP_BAD_REQUEST
            return
        
        with scoped_session() as session:
            query = self._apply_permissions(req, {'method': 'delete'}, self.get_base_query(session))
            qf = [self.model_class.id.in_(ids), ]
            is_soft_delete = issubclass(self.model_class, SoftDelete)
            if is_soft_delete:
                qf.append(self.model_class.deleted == false())
            query = query.filter(*qf)
            if is_soft_delete:
                query.update({'deleted': True})
            else:
                query.delete(synchronize_session=False)
        resp.status = HTTP_OK

class ModelQueryResource(ModelListResource):
    CONDITION_OPERATORS = {
        '$lt': lambda x,y: x < y,
        '$gt': lambda x,y: x > y,
        '$lte': lambda x,y: x <= y,
        '$gte': lambda x,y: x >= y,
        '$eq': lambda x,y: x == y,
        '$ne': lambda x,y: x != y,
        '$exists': lambda x,y: x is not None,
        # '$type': '',
        '$in': lambda x,y: getattr(x, 'in_')(y),
        '$nin': lambda x,y: base_not_(getattr(x, 'in_')(y)),
        # '$size': '',
        # '$mod': '',
        '$contains': lambda x,y: x.any(x.property.entity.class_.id == y),
        '$regex': lambda x,y: getattr(x, 'op')('~*')(y)
    }
    CONDITION_OPERATORS_KEYS = CONDITION_OPERATORS.keys()

    COMBINATION_OPERATORS = {
        '$and': and_,
        '$or': or_,
        '$not': not_,
        '$nor': nor_,
        # '$all': '',
        # '$elemMatch': ''
    }
    COMBINATION_OPERATORS_KEYS = COMBINATION_OPERATORS.keys()

    def __init__(self, model_class, schema_class):
        self.model_class = model_class
        self.list_schema_class = schema_class
    
    def get_list_schema_class(self):
        return self.list_schema_class
    
    def __decode_selector_condition(self, field, entry):
        condition = []
        for key in entry:
            if key in self.CONDITION_OPERATORS_KEYS:
                if not hasattr(self.model_class, field):
                    raise InvalidSelectorException('{} has no {} field'.format(self.model_class, field))
                condition.append(
                    self.CONDITION_OPERATORS[key](getattr(self.model_class, field), entry.get(key))
                )
        return condition
    
    def __decode_selector_entry(self, key, entry):
        if key in self.COMBINATION_OPERATORS_KEYS:
            sub_filter = list()
            if isinstance(entry, list):
                for sub_selector in entry:
                    for sub_entry_key in sub_selector:
                        sub_filter = sub_filter + self.__decode_selector_entry(
                            sub_entry_key,
                            sub_selector.get(sub_entry_key)
                        )
            return [self.COMBINATION_OPERATORS[key](*sub_filter)]
        if isinstance(entry, dict):
            return self.__decode_selector_condition(key, entry)
        return self.__decode_selector_entry(key, {'$eq': entry})
    
    def __apply_selector(self, query, params):
        if 'selector' not in params or not isinstance(params['selector'], dict):
            return query
        
        selector = params['selector']
        for key in selector:
            query = query.filter(*self.__decode_selector_entry(key.replace(".", "__"), selector[key]))
        
        return query

    def on_post(self, req: Request, resp: Response):
        try:
            params = json.loads(req.stream.read(req.content_length or 0))
        except (TypeError, ValueError):
            resp.status = HTTP_BAD_REQUEST
            return
        
        schema_class = self.get_list_schema_class()

        with scoped_session() as session:
            query = self._apply_permissions(req, {'method': 'list'}, self.get_base_query(session))
            count = query.count()
            if issubclass(self.model_class, SoftDelete):
                query = query.filter(self.model_class.deleted == false())
            try:
                query = self.__apply_selector(query, params)
            except InvalidSelectorException as e:
                resp.status = HTTP_BAD_REQUEST
                resp.body = json.dumps({
                    'error': e.message
                })
                return
            query = self._apply_sort(query, params)
            query = self._apply_limit(query, params)
            query = self._apply_offset(query, params)
            from sqlalchemy.dialects import postgresql
            print(str(query.statement.compile(dialect=postgresql.dialect())))
            items = schema_class().dump(
                query,
                many=True
            )
        resp.body = json.dumps({
            'count': count,
            'results': items.data
        })

class ModelResource(ModelListResource):
    uri = None

    @classmethod
    def register_endpoints(cls, base_url, app, resource):
        dah = ModelDeleteAllResource()
        dah.model_class = resource.model_class
        dah.permissions = cls.permissions
        qh = ModelQueryResource(resource.model_class, resource.get_list_schema_class())
        qh.model_class = resource.model_class
        qh.schema_class = cls.schema_class
        qh.schema_classes = cls.schema_classes
        qh.permissions = cls.permissions
        app.add_route(base_url, resource)
        app.add_route('{}/{{obj_id}}'.format(base_url), resource)
        app.add_route('{}/delete_all'.format(base_url), dah)
        app.add_route('{}/query'.format(base_url), qh)

    def on_get(self, req: Request, resp: Response, obj_id=None):
        """Generic GET endpoint.
        ---
        get:
            description: Lists existing objects
            consumes: ["json"]
            responses:
                200:
                    description: Returns objects on authorized requests
                    schema: {}
                401:
                    description: Denies unauthorized requests
        """
        if obj_id is None:
            self.__list_items(req, resp)
        else:
            self.__get_item(req, resp, obj_id)
    
    def on_post(self, req: Request, resp: Response, obj_id=None):
        """Generic POST endpoint.
        ---
        post:
            description: Adds an object
            consumes: ["json"]
            parameters:
            -   in: body
                name: object
                description: The object being added
                required: true
            responses:
                200:
                    description: Returns created object
                    schema: {}
                400:
                    description: Denies empty payload requests
                401:
                    description: Denies unauthorized requests
        """
        if obj_id is not None:
            resp.status = HTTP_METHOD_NOT_ALLOWED
            return
        
        schema_class = self.__get_schema_class('post')

        # try:
        with scoped_session() as session:
            input_data = json.loads(req.stream.read(req.content_length or 0))
            if not self._can_create(req, {'method': 'create'}, input_data):
                resp.status = HTTP_METHOD_NOT_ALLOWED
                return
            self._process_create_data(input_data)
            
            item, errors = schema_class().load(
                input_data,
                session=session
            )
            if errors is not None:
                errors_num = len(errors)
                if errors_num > 0:
                    resp.status = HTTP_BAD_REQUEST
                    resp.body = json.dumps({'errors': errors})
                    return
            session.add(item)
            session.commit()

            self._post_create(session, item)

            itm_id = item.id
            item_dump, _ = schema_class().dump(item)
        
        resp.status = HTTP_CREATED
        resp.append_header('Location', self.__get_item_url(req, itm_id))
        resp.body = json.dumps(item_dump)
        # except (TypeError, ValueError, IntegrityError):
        #     resp.status = HTTP_BAD_REQUEST
    
    def on_put(self, req: Request, resp: Response, obj_id=None):
        """Generic PUT endpoint.
        ---
        post:
            description: Adds an object
            consumes: ["json"]
            parameters:
            -   in: body
                name: object
                description: The object being added
                required: true
            responses:
                200:
                    description: Returns created object
                    schema: {}
                400:
                    description: Denies empty payload requests
                401:
                    description: Denies unauthorized requests
        """
        self.__update_item(req, resp, obj_id, 'put', False)
    
    def on_patch(self, req: Request, resp: Response, obj_id=None):
        self.__update_item(req, resp, obj_id, 'patch', True)

    def on_delete(self, req: Request, resp: Response, obj_id=None):
        if obj_id is None:
            resp.status = HTTP_METHOD_NOT_ALLOWED
            return
        
        schema_class = self.__get_schema_class('delete')
        
        try:
            nid = int(obj_id)
        except (TypeError, ValueError):
            resp.status = HTTP_BAD_REQUEST
            resp.body = '{"message": "Invalid id"}'
            return
        
        with scoped_session() as session:
            query = self._apply_permissions(req, {'method': 'delete'}, self.get_base_query(session))
            qf = [self.model_class.id == nid, ]
            is_soft_delete = issubclass(self.model_class, SoftDelete)
            if is_soft_delete:
                qf.append(self.model_class.deleted == false())
            item = query.filter(*qf).first()
            if item is None:
                resp.status = HTTP_NOT_FOUND
                return
            if issubclass(self.model_class, Fixed) and item.fixed:
                resp.status = HTTP_CONFLICT
                resp.body = '{"message": "the resource is marked as \'fixed\', hence it could not be deleted"}'
                return
            if is_soft_delete:
                item.deleted = True
                session.add(item)
            else:
                session.delete(item)
            item_dump, _ = schema_class().dump(item)
        
        resp.status = HTTP_OK
        resp.body = json.dumps(item_dump)
    
    def _process_update_data(self, data, input_data):
        pass
    
    def _post_update(self, session, instance):
        pass
    
    def _process_create_data(self, data):
        pass
    
    def _post_create(self, session, instance):
        pass
    
    def __update_item(self, req: Request, resp: Response, obj_id, method, partial): # pylint: disable=too-many-arguments,too-many-locals
        if obj_id is None:
            resp.status = HTTP_METHOD_NOT_ALLOWED
            return

        try:
            nid = int(obj_id)
        except (TypeError, ValueError):
            resp.status = HTTP_BAD_REQUEST
            resp.body = '{"message": "Invalid id"}'
            return
        
        schema_class = self.__get_schema_class(method)

        try:
            with scoped_session() as session:
                query = self._apply_permissions(req, {'method': 'update'}, self.get_base_query(session))
                qf = [self.model_class.id == nid, ]
                if issubclass(self.model_class, SoftDelete):
                    qf.append(self.model_class.deleted == false())
                item = query.filter(*qf).first()
                if item is None:
                    resp.status = HTTP_NOT_FOUND
                    return
                if item.id != nid:
                    resp.status = HTTP_BAD_REQUEST
                    return
                input_data = json.loads(req.stream.read(req.content_length or 0))
                self._process_update_data(item, input_data)
                upd, errors = schema_class().load(
                    input_data,
                    session=session,
                    instance=item,
                    partial=partial
                )
                if errors is not None:
                    errors_num = len(errors)
                    if errors_num > 0:
                        resp.status = HTTP_BAD_REQUEST
                        resp.body = json.dumps({'errors': errors})
                        return
                session.add(upd)

                self._post_update(session, upd)

                item_dump, _ = schema_class().dump(item)
            
            resp.status = HTTP_OK
            resp.body = json.dumps(item_dump)
        except (TypeError, ValueError, IntegrityError):
            resp.status = HTTP_BAD_REQUEST
    
    def __get_item_url(self, req: Request, obj_id):
        return '{}://{}{}/{}'.format(
            req.scheme,
            req.host,
            self.uri,
            obj_id
        )
    
    def __get_schema_class(self, method):
        if self.schema_classes is not None and method in self.schema_classes:
            return self.schema_classes[method]
        return self.schema_class
    
    def __get_item(self, req: Request, resp: Response, obj_id):
        resp.content_type = MEDIA_JSON

        try:
            nid = int(obj_id)
        except (TypeError, ValueError):
            resp.status = HTTP_BAD_REQUEST
            resp.body = '{"message": "Invalid id"}'
            return

        schema_class = self.__get_schema_class('get')

        with scoped_session() as session:
            query = self._apply_permissions(req, {'method': 'get'}, self.get_base_query(session))
            qf = [self.model_class.id == nid, ]
            if issubclass(self.model_class, SoftDelete):
                qf.append(self.model_class.deleted == false())
            q = query.filter(*qf)
            q = self._apply_permissions(req, {'method': 'get'}, q)
            instance = q.first()
            if instance is None:
                resp.status = HTTP_NOT_FOUND
                return
            item, _ = schema_class().dump(instance)
        resp.status = HTTP_OK
        resp.body = json.dumps(item)
    
    def get_list_schema_class(self):
        return self.__get_schema_class('list')
    
    def __list_items(self, req: Request, resp: Response):
        resp.content_type = MEDIA_JSON
        resp.status = HTTP_OK
        params = req.params

        schema_class = self.get_list_schema_class()

        with scoped_session() as session:
            query = self._apply_permissions(req, {'method': 'list'}, self.get_base_query(session))
            count = query.count()
            if issubclass(self.model_class, SoftDelete):
                query = query.filter(self.model_class.deleted == false())
            query = self._apply_sort(query, params)
            query = self._apply_limit(query, params)
            query = self._apply_offset(query, params)
            items = schema_class().dump(
                query,
                many=True
            )
        resp.body = json.dumps({
            'count': count,
            'results': items
        })
