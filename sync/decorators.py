import logging

from marshmallow_sqlalchemy import ModelSchema

from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.inspection import inspect

from .triggers import check_triggers
from .utils import register_sync_model
logger = logging.getLogger()


def _sync_model(cls, permissions=()):
    try:
        if not issubclass(cls, ModelSchema):
            logger.info('Class %s is not a valid model schema', cls.__name__)
            return cls
        
        model_class = cls.Meta.model

        mapper = inspect(model_class)
        tables_num = len(mapper.tables)
        if tables_num > 0:
            table = mapper.tables[0]
            check_triggers(model_class)
            register_sync_model(table.name, model_class, cls, permissions)
            logger.info('Class %s registered as sync model', model_class.__name__)
        return cls
    except NoInspectionAvailable:
        logger.warning('Class %s is not a valid model', cls.__name__)

    return cls

def sync_model(cls=None, permissions=()):
    if cls is None:
        def wrapper(cls):
            return _sync_model(cls, permissions=permissions)
        return wrapper
    return _sync_model(cls)
