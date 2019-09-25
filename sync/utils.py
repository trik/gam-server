import copy

__registered_sync_models = {}

def register_sync_model(table_name, model_class, schema_class, permissions):
    if table_name not in __registered_sync_models:
        __registered_sync_models[table_name] = (model_class, schema_class, permissions, )

def get_sync_model(table_name):
    return __registered_sync_models[table_name] if table_name in __registered_sync_models else (None, None, None, )

def get_registered_sync_models():
    return copy.deepcopy(__registered_sync_models)
