import ujson as json

class InvalidSyncEntry(Exception):
    def __init__(self, table_name, sync_entry):
        super().__init__()

        self.__table_name = table_name
        self.__sync_entry = sync_entry

    def __str__(self):
        return 'Invalid sync entry {} {}'.format(self.__table_name, json.dumps(self.__sync_entry))

class InvalidSyncEntryType(Exception):
    def __init__(self, entry_type):
        super().__init__()

        self.__entry_type = entry_type

    def __str__(self):
        return 'Invalid sync entry type {}'.format(self.__entry_type)

class InvalidSyncModel(Exception):
    def __init__(self, table_name):
        super().__init__()

        self.__table_name = table_name

    def __str__(self):
        return 'Invalid sync model {}'.format(self.__table_name)

class ModelNotFound(Exception):
    def __init__(self, table_name, object_id):
        super().__init__()

        self.__table_name = table_name
        self.__object_id = object_id

    def __str__(self):
        return 'Model not found for sync entry {} {}'.format(self.__table_name, self.__object_id)

class FixedModel(Exception):
    def __init__(self, table_name, object_id):
        super().__init__()

        self.__table_name = table_name
        self.__object_id = object_id

    def __str__(self):
        return 'Model {} {} is fixed and can\'t be deleted'.format(self.__table_name, self.__object_id)
