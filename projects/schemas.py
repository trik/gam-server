from marshmallow_sqlalchemy import ModelSchema

from sync.decorators import sync_model
from .models import Project

@sync_model()
class ProjectSchema(ModelSchema):
    class Meta:
        model = Project
        fields = ('id', 'name', )
