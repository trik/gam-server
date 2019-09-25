from marshmallow import fields, Schema
from marshmallow_sqlalchemy import ModelSchema

from .models import Change


class ChangeSchema(ModelSchema):
    class Meta:
        model = Change
        fields = (
            'id', 'table_name', 'object_id', 'entry_type'
        )

class UpwardChangeSchema(Schema):
    sequence = fields.Int()
    table_name = fields.String()
    object_id = fields.Int()
    entry_type = fields.String()
    object = fields.Dict()
