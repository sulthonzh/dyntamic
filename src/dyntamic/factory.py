from typing import Annotated, Union

import typing
from pydantic import create_model
from pydantic.fields import Field

Model = typing.TypeVar('Model', bound='BaseModel')


class DyntamicFactory:

    TYPES = {
        'string': str,
        'array': list,
        'boolean': bool,
        'integer': int,
        'float': float,
        'number': float,
    }

    def __init__(self,
                 json_schema: dict,
                 base_model: type[Model] | tuple[type[Model], ...] | None = None,
                 ref_template: str = "#/$defs/"
                 ) -> None:
        """
        Creates a dynamic pydantic model from a JSONSchema, dumped from and existing Pydantic model elsewhere.
            JSONSchema dump must be called with ref_template='{model}' like:

            SomeSampleModel.model_json_schema(ref_template='{model}')
            Use:
            >> _factory = DyntamicFactory(schema)
            >> _factory.make()
            >> _model = create_model(_factory.class_name, **_factory.model_fields)
            >> _instance = dynamic_model.model_validate(json_with_data)
            >> validated_data = model_instance.model_dump()
        """
        self.class_name = json_schema.get('title')
        self.class_type = json_schema.get('type')
        self.required = json_schema.get('required', False)
        self.raw_fields = json_schema.get('properties')
        self.ref_template = ref_template
        self.definitions = json_schema.get(ref_template)
        self.fields = {}
        self.model_fields = {}
        self._base_model = base_model

    def make(self) -> Model:
        """Factory method, dynamically creates a pydantic model from JSON Schema"""
        for field in self.raw_fields:
            if '$ref' in self.raw_fields[field]:
                model_name = self.raw_fields[field].get('$ref')
                self._make_nested(model_name, field)
            else:
                factory = self.TYPES.get(self.raw_fields[field].get('type'))
                if factory == list:
                    items = self.raw_fields[field].get('items')
                    if '$ref' in items:
                        model_name = items.get('$ref')
                        self._make_nested(model_name, field, True)
                else:
                    self._make_field(factory, field, self.raw_fields.get('title'))
        return create_model(self.class_name, __base__=self._base_model, **self.model_fields)

    def _make_nested(self, model_name: str, field, is_list:bool = False) -> None:
        """Create a nested model"""
        level = DyntamicFactory({self.ref_template: self.definitions} | self.definitions.get(model_name),
                                ref_template=self.ref_template)
        level.make()
        model = create_model(model_name, **level.model_fields)
        if is_list:
            self._make_field(list[model], field, field)
        else:
            self._make_field(model, field, field)

    def _make_field(self, factory, field, alias) -> None:
        """Create an annotated field"""
        if not self.required or field not in self.required:
            factory_annotation = Annotated[Union[factory | None], factory]
        else:
            factory_annotation = factory
        self.model_fields[field] = (
            Annotated[factory_annotation, Field(default_factory=factory, alias=alias)],
            ...)
