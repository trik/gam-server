from gam.database import Base
import gam.schemas # noqa

from sync.utils import get_registered_sync_models

def __clean_unlinked_models(models: dict):
    cleaned = []
    keys = [k for k in models.keys()]
    for model in keys:
        related_num = len(models[model])
        if related_num == 0:
            cleaned.append(model)
            del models[model]
    keys = models.keys()
    for model in keys:
        for cleaned_model in cleaned:
            if cleaned_model in models[model]:
                models[model].remove(cleaned_model)
    return cleaned

def get_ordered_sync_models():
    models = get_registered_sync_models()
    tables = Base.metadata.tables
    parsed_models = {}
    ordered_tables = []

    models_names = models.keys()
    for table in models_names:
        if table not in tables:
            continue
        parsed_models[table] = {fk.column.table.name for fk in tables[table].foreign_keys}
    
    models_num = len(parsed_models)
    iters_limit = 500
    i = 0
    while models_num > 0 and i < iters_limit:
        ordered_tables = ordered_tables + __clean_unlinked_models(parsed_models)
        i += 1
        models_num = len(parsed_models)
    
    models_num = len(parsed_models)
    if models_num > 0:
        raise Exception('Unable to determine ordered models list')
    
    return ordered_tables
