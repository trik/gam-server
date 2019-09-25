from gam.resources import ModelResource
from .models import Epic, Task, UserStory
from .schemas import EpicSchema, TaskSchema, UserStorySchema

class EpicResource(ModelResource):
    model_class = Epic
    schema_class = EpicSchema

class UserStoryResource(ModelResource):
    model_class = UserStory
    schema_class = UserStorySchema

class TaskResource(ModelResource):
    model_class = Task
    schema_class = TaskSchema
