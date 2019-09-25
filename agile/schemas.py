from marshmallow_sqlalchemy import ModelSchema

from sync.decorators import sync_model
from .models import (Epic, Task, UserStory, )

item_fields = ('id', 'project_id', 'name', 'description', 'order', )

@sync_model()
class EpicSchema(ModelSchema):
    class Meta:
        model = Epic
        fields = item_fields

@sync_model()
class UserStorySchema(ModelSchema):
    class Meta:
        model = UserStory
        fields = item_fields + ('epic_id', )

@sync_model()
class TaskSchema(ModelSchema):
    class Meta:
        model = Task
        fields = item_fields + ('user_story_id', )
