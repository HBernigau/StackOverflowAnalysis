"""
contains a typed json decoder and encoder

Author: `HBernigau <https://github.com/HBernigau>`_
Date: 01.2022
"""


import json
from dataclasses import dataclass, is_dataclass, field
import marshmallow_dataclass as mmdc
from collections import defaultdict
import marshmallow
from typing import Any, List
from datetime import datetime, date
import uuid
import pickle

import so_ana_util.common_types as common_types


def _is_sub_class(first, second):
    try:
        return issubclass(first, second)
    except:
        return False


class _PickleLambdaFix:

    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def get_col_type(data):
    cond = True
    if isinstance(data, list):
        type_name = type(data[0]).__name__
        for item in data:
            cond = cond and type(item).__name__==type_name and is_dataclass(item)
            if not cond:
                type_name = None
                break
        type_name = f'List[{type_name}]'
    elif isinstance(data, dict):
        type_name = type(list(data.values())[0]).__name__
        for key, value in data.items():
            cond = cond and type(value).__name__==type_name and is_dataclass(value) and isinstance(key, str)
            if not cond:
                type_name = None
                break
        type_name = f'Dict[str,{type_name}]'
    else:
        type_name = None
    return type_name


def dc_encoder(obj):
    @dataclass
    class Helper:
        _type: str
        _value: type(obj)

    class_schema = mmdc.class_schema(Helper)()
    return class_schema.dump(Helper(_type=type(obj).__name__, _value=obj))


class DC_Decoder:

    def __init__(self, DC):
        self.DC = DC

    def __call__(self, json_dict):
        class_schema = mmdc.class_schema(self.DC)()
        return class_schema.loads(json.dumps(json_dict))


class WrapperEncoder:

    def __init__(self, wrapped_type):
        self.wrapped_type = wrapped_type

    def __call__(self, obj):
        wrapped_type = self.wrapped_type
        @dataclass
        class Helper:
            _type: str
            _value: wrapped_type

        class_schema = mmdc.class_schema(Helper)()
        return class_schema.dump(Helper(_type=type(obj).__name__, _value=obj))


class WrapperDecoder:

    def __init__(self, wrapped_type):
        self.wrapped_type = wrapped_type

    def __call__(self, json_dict):
        wrapped_type = self.wrapped_type
        @dataclass
        class Helper:
            _value: wrapped_type

        class_schema = mmdc.class_schema(Helper)()
        return class_schema.loads(json.dumps({'_value': json_dict}))._value


class MMEncoder:

    def __init__(self, MMSchema):
        self.MMSchema = MMSchema

    def __call__(self, obj):
        key = self.MMSchema.__name__
        class Helper(marshmallow.Schema):
            _type = marshmallow.fields.Str(default=_PickleLambdaFix(key), missing=_PickleLambdaFix(key))
            _value = marshmallow.fields.Nested(self.MMSchema)

        return Helper().dumps({'_type': key, '_value': obj})


class MMDecoder:

    def __init__(self, MMSchema):
        self.MMSchema = MMSchema

    def __call__(self, json_dict):
        return self.MMSchema().loads(json.dumps(json_dict))


class JSONRegistry:

    def __init__(self):

        self._registry = defaultdict(_PickleLambdaFix(None))
        self._encoders = defaultdict(_PickleLambdaFix(json.dumps))
        self._decoders = defaultdict(_PickleLambdaFix(json.loads))
        for cls in [int, float, str, datetime, date, uuid.UUID]:
            self.register_schema(cls, )

    @property
    def checker_dict(self):
        return {'dc': lambda x: is_dataclass(x),
                'mm': lambda x: _is_sub_class(x, marshmallow.Schema),
                'int': lambda x: _is_sub_class(x, int),
                'float': lambda x: _is_sub_class(x, float),
                'str': lambda x: _is_sub_class(x, str),
                'datetime': lambda x: _is_sub_class(x, datetime),
                'date': lambda x: _is_sub_class(x, date),
                'UUID': lambda x: _is_sub_class(x, uuid.UUID)
                }

    def register_schema(self, cls):  #dc: dataclass or mm-schema
        key = cls.__name__
        for type_key, type_checker in self.checker_dict.items():
            if type_checker(cls):
                self._registry[key] = cls
                if type_key == 'dc':
                    encoder = dc_encoder
                    decoder = DC_Decoder(cls)
                elif type_key == 'mm':
                    encoder =MMEncoder(cls)
                    decoder = MMDecoder(cls)
                else:
                    encoder = WrapperEncoder(cls)
                    decoder = WrapperDecoder(cls)
                self._decoders[key] = decoder
                self._encoders[key] = encoder
                break
        else:
            raise TypeError(f'cannot register "{key}": {cls}')


def get_typed_json_encoder(registry_):
    class TypedJsonEncoder(json.JSONEncoder):
        registry = registry_

        def default(self, obj):
            key = type(obj).__name__
            if key in TypedJsonEncoder.registry._encoders.keys():
                return TypedJsonEncoder.registry._encoders[key](obj)
            return super().default(obj)
    return TypedJsonEncoder


class TypedJsonDecoder(json.JSONDecoder):

    def __init__(self, registry):
        self.registry = registry
        super().__init__(object_hook=self._obj_hook)

    def _obj_hook(self, val):
        if '_type' in val.keys() and '_value' in val.keys() and len(val.keys()) == 2:
            return self.registry._decoders[val['_type']](val['_value'])
        return val


class TypedJsonSerializer(JSONRegistry):

    def __init__(self):
        super().__init__()

    def serialize(self, value, type_hint=None, as_bytes=True):
        if type_hint is not None:
            value_str = json.dumps(self._encoders[type_hint](value))
        else:
            Encoder = get_typed_json_encoder(self)
            value_str = json.dumps(value, cls=Encoder)
        if as_bytes:
            return value_str.encode('utf-8')
        else:
            return value_str

    def deserialize(self, value_serialized, as_bytes = True):
        decoder = TypedJsonDecoder(self)
        if as_bytes:
            value_serialized = value_serialized.decode('utf-8')
        return decoder.decode(value_serialized)


class TypedJsonSerializer_OLD:

    def __init__(self):
        self.checker_dict = {   'dc': lambda x: is_dataclass(x),
                                'mm': lambda x: _is_sub_class(x, marshmallow.Schema),
                                'int': lambda x: _is_sub_class(x, int),
                                'float': lambda x: _is_sub_class(x, float),
                                'str': lambda x: _is_sub_class(x, str),
                                'datetime': lambda x: _is_sub_class(x, datetime),
                                'date': lambda x: _is_sub_class(x, date),
                                'UUID': lambda x: _is_sub_class(x, uuid.UUID)
                }

        self._registry = defaultdict(lambda: None)
        for cls in [int, float, str, datetime, date, uuid.UUID]:
            self.register_schema(cls)

    def register_schema(self, cls):  #dc: dataclass or mm-schema
        key = cls.__name__
        for type_key, type_checker in self.checker_dict.items():
            if type_checker(cls):
                self._registry[key] = cls
                break
        else:
            raise TypeError(f'cannot register "{key}": {cls}')

    def _get_schema(self, key):
        reg_obj = self._registry[key]
        reg_obj_type = self._type_map[key]
        if reg_obj_type == 'dc' :
            @dataclass
            class ExtSchema:
                _value: reg_obj
                _type: str = field(default=key)
            return mmdc.class_schema(ExtSchema)()
        elif reg_obj_type == 'List[dc]':
            @dataclass
            class ExtSchema:
                _value: List[reg_obj]
                _type: str = field(default=key)
            return mmdc.class_schema(ExtSchema)()
        elif reg_obj_type ==  'Dict[str,dc]':
            @dataclass
            class Entry:
                key: str
                value: reg_obj
            @dataclass
            class ExtSchema:
                _value: List[Entry]
                _type: str = field(default=key)
            return mmdc.class_schema(ExtSchema)()
        elif reg_obj_type in ['mm', 'int', 'str', 'float', 'datetime', 'date', 'UUID']:
            map_dict = {'mm': None,
                        'int': marshmallow.fields.Int(),
                        'str': marshmallow.fields.Str(),
                        'float': marshmallow.fields.Float(),
                        'datetime': marshmallow.fields.DateTime(),
                        'date': marshmallow.fields.Date(),
                        'UUID': marshmallow.fields.UUID()
                         }
            tar_field = map_dict[reg_obj_type] or marshmallow.fields.Nested(reg_obj())

            class ExtSchema(marshmallow.Schema):
                _value = tar_field
                _type = marshmallow.fields.Str(default=lambda:key, missing=lambda:key)
            return ExtSchema()
        else:
            @dataclass
            class PseudoSchema:
                def dump(self, value):
                    return {'_value': value['_value'], '_type': key}

                def load(self, value_dict):
                    return value_dict

            return PseudoSchema()

    def serialize(self, value, type_hint=None, as_bytes=True):
        key = type_hint or get_col_type(value) or type(value).__name__
        key_type = self._type_map[key]
        if key_type == '#unregistered#':
            key = '#unregistered#'
        schema = self._get_schema(key)
        if key_type in ['dc', 'List[dc]', 'Dict[str,dc]']:
            @dataclass
            class Wrapper:
                _value: Any
            if key_type in ['dc', 'List[dc]']:
                ext_value = schema.dump(Wrapper(value))
            else:
                @dataclass
                class ValueContainer:
                    key: str
                    value: Any
                ext_value = schema.dump(Wrapper([ValueContainer(key=key, value=value) for key, value in value.items()]))
        else:
            print(f'key="{key}", serializing "{value}"')
            ext_value = schema.dump({'_value': value})
        res = json.dumps(ext_value)
        if as_bytes:
            res = res.encode('utf-8')
        return res

    def deserialize(self, value_serialized, as_bytes = True):
        if as_bytes:
            value_serialized = value_serialized.decode('utf-8')
        json_type = json.loads(value_serialized)['_type']
        schema = self._get_schema(json_type)
        schema_data = schema.load(json.loads(value_serialized))
        if isinstance(schema_data, dict):
            return schema_data['_value']
        elif is_dataclass(schema_data):
            if self._type_map[json_type] == 'Dict[str,dc]':
                return {obj.key: obj.value for obj in schema_data._value}
            else:
                return schema_data._value
        else:
            raise RuntimeError(f'Could not deserialize "{value_serialized}"')


if __name__ == '__main__':

    @dataclass
    class SampleDC:
        value: int

    class MMSchema(marshmallow.Schema):
        value = marshmallow.fields.Int()

    registry = TypedJsonSerializer()

    print(registry.__dict__)
    for key, value in registry.__dict__.items():
        print(key)
        interm = pickle.dumps(value)
        print('done')
    registry.register_schema(SampleDC)
    registry.register_schema(MMSchema)

    print(registry._registry)

    print('Data class')
    json_str = registry.serialize(SampleDC(42), as_bytes=False)
    print(json_str)
    print(registry.deserialize(json_str, as_bytes=False))
    print()
    print('MM-Schema')
    json_str = registry.serialize({'value': 42}, type_hint='MMSchema')
    print(json_str)
    print(registry.deserialize(json_str))
    print()
    print('Plain-Vanilla')
    json_str = registry.serialize({'value': 42})
    print(json_str)
    print(registry.deserialize(json_str))
    print()
    print('Plain-Vanilla unregistered')
    json_str = registry.serialize({'value': 'no'}, type_hint='someting')
    print(json_str)
    print(registry.deserialize(json_str))
    print()
    print('Plain types')
    for item in (2, 'Hello world!', 3.24, datetime.now(), uuid.uuid4()):
        print(' ---> ', type(item), type(item).__name__)
        json_str = registry.serialize(item)
        print(json_str)
        erg = registry.deserialize(json_str)
        print(erg, type(erg))
    print()
    print('Plain type with type hint')
    json_str = registry.serialize(2, type_hint='int')
    print(json_str)
    erg = registry.deserialize(json_str)
    print(erg, type(erg))
    print()
    print('Collections')
    json_str = registry.serialize([SampleDC(42), SampleDC(17)])
    print(json_str)
    print(registry.deserialize(json_str))
    json_str = registry.serialize({'value_1': SampleDC(42), 'value_2': SampleDC(17)})
    print(json_str)
    print(registry.deserialize(json_str))
    print()