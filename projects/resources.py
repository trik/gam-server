from gam.resources import ModelResource
from .models import Project
from .schemas import ProjectSchema

class ProjectResource(ModelResource):
    model_class = Project
    schema_class = ProjectSchema
