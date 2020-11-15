import hashlib
import pytz
import time
import re

import uuid as GenUUID

from datetime import datetime
from math import pow
from time import sleep
from unidecode import unidecode

from django.conf import settings
from django.core.cache import caches

from django.db import models
from django.db.models import Q

from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

# These are the "target schema" models.
from opencontext_py.apps.all_items import configs
from opencontext_py.apps.all_items.models import (
    AllManifest,
    AllAssertion,
    AllHistory,
    AllResource,
    AllIdentifier,
    AllSpaceTime,
)
from opencontext_py.apps.all_items.legacy_all import update_old_id



MAX_ANNOTATION_HIERARCHY_DEPTH = 20


# Records data sources for ETL (extract transform load)
# processes that ingest data into Open Context
class DataSource(models.Model):
    uuid = models.UUIDField(primary_key=True, editable=True)
    publisher = models.ForeignKey(
        AllManifest, 
        db_column='publisher_uuid',
        related_name='+', 
        on_delete=models.CASCADE, 
        default=configs.OPEN_CONTEXT_PUB_UUID,
    )
    project = models.ForeignKey(
        AllManifest, 
        db_column='project_uuid', 
        related_name='+', 
        on_delete=models.CASCADE, 
        default=configs.OPEN_CONTEXT_PROJ_UUID,
    )
    source_id = models.TextField(unique=True)
    label = models.TextField()
    field_count = models.IntegerField()
    row_count = models.IntegerField()
    source_type = models.TextField()
    is_current = models.BooleanField(default=True)
    status = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    meta_json = JSONField(default=dict)

    def primary_key_create(self, source_id):
        """Converts a source_id into a UUID deterministically"""
        _, uuid = update_old_id(source_id)
        return uuid
    
    def primary_key_create_for_self(self):
        """Makes a primary key using a prefix from the subject"""
        if self.uuid:
            # One is already defined, so skip this step.
            return self.uuid
        return self.primary_key_create(self.source_id)
    
    def save(self, *args, **kwargs):
        # Defaults the primary key uuid to value deterministically
        # generated.
        self.uuid = self.primary_key_create_for_self()
        super(DataSource, self).save(*args, **kwargs)
    
    class Meta:
        db_table = 'etl_sources'
        ordering = ['-updated']



# Records data source fields for ETL (extract transform load)
# processes that ingest data into Open Context
class DataSourceField(models.Model):
    uuid = models.UUIDField(primary_key=True, editable=True)
    data_source = models.ForeignKey(
        DataSource, 
        db_column='source_uuid', 
        related_name='+', 
        on_delete=models.CASCADE, 
    )
    field_num = models.IntegerField()
    label = models.TextField()
    ref_name = models.TextField(null=True)
    ref_orig_name = models.TextField(null=True)
    item_type = models.TextField(null=True)
    data_type = models.TextField(null=True)
    item_class = models.ForeignKey(
        AllManifest, 
        db_column='item_class_uuid', 
        related_name='+', 
        on_delete=models.CASCADE, 
        default=configs.DEFAULT_CLASS_UUID,
    )
    context = models.ForeignKey(
        AllManifest, 
        db_column='context_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    value_prefix = models.TextField(null=True)
    unique_count = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    meta_json = JSONField(default=dict)

    def primary_key_create(self, data_source_id, field_num):
        """Converts a source_id into a UUID deterministically"""
        data_source_id = str(data_source_id)
        source_field = f'{data_source_id }-{field_num}'
        _, uuid_from_field = update_old_id(source_field)
        
        # Now assemble a uuid that has the first part of the
        # data source id and the unique part generated from the
        # data source id and the field num
        id_prefix = data_source_id.split('-')[0]
        new_parts = uuid_from_field.split('-')
        uuid = '-'.join(
            ([id_prefix] + new_parts[1:])
        )
        return uuid
    
    def primary_key_create_for_self(self):
        """Makes a primary key using a prefix from the subject"""
        if self.uuid:
            # One is already defined, so skip this step.
            return self.uuid
        return self.primary_key_create(self.data_source.uuid, self.field_num)

    def save(self, *args, **kwargs):
        # Defaults the primary key uuid to value deterministically
        # generated.
        self.uuid = self.primary_key_create_for_self()
        super(DataSourceField, self).save(*args, **kwargs)

    class Meta:
        db_table = 'etl_fields'
        ordering = ['data_source', 'field_num']
        unique_together = ('data_source', 'field_num')



# ---------------------------------------------------------------------
# NOTE: The following functions are for validating spatial context
# containment annotations between fields with item_type="subjects".
# The point is to prevent circular hierarchies and to make sure that
# containment annotations are made only between item_type subjects
# fields.
# ---------------------------------------------------------------------
def get_immediate_context_parent_obj_db(child_field_obj):
    """Get the immediate (spatial) context parent of a child_obj"""
    p_annotation = DataSourceAnnotation.objects.filter(
        predicate_id=configs.PREDICATE_CONTAINS_UUID,
        object_field=child_field_obj
    ).first()
    if not p_annotation:
        return None
    return p_annotation.subject_field


def get_immediate_context_children_objs_db(parent_field_obj):
    """Get the immediate (spatial) context children of a parent_field_obj"""
    return [
        a.object_field 
        for a in DataSourceAnnotation.objects.filter(
            subject_field=parent_field_obj,
            predicate_id=configs.PREDICATE_CONTAINS_UUID,
        )
    ]


def validate_context_subject_objects(subject_field_obj, object_field_obj, raise_on_error=True):
    """Validates the correct item-types for subject and object fields."""
    tup_checks = [
        ('subject_field', subject_field_obj,),
        ('object_field', object_field_obj,),
    ]
    for field_name, field_obj in tup_checks:
        if field_obj.item_type == "subjects":
            # This is valid, so skip.
            continue
        if raise_on_error:
            raise ValueError(
                f'The {field_name} must be item_type="subjects", not '
                f'{field_obj.item_type} as found in field: {field_obj.label}'
                f'(field_num: {field_obj.field_num}) (uuid: {field_obj.uuid})'
            )
        else:
            return False
    return True


def validate_context_assertion(
    subject_field_obj, 
    object_field_obj,
    max_depth=MAX_ANNOTATION_HIERARCHY_DEPTH
):
    """Validates a spatial context annotation between subject and object fields"""
    validate_context_subject_objects(subject_field_obj, object_field_obj)

    obj_field_parent = get_immediate_context_parent_obj_db(
        object_field_obj
    )
    if obj_field_parent and obj_field_parent != subject_field_obj:
        # The child object already has a parent, and
        # we allow only 1 parent.
        raise ValueError(
            f'Object-field {object_field_obj.label} already contained in '
            f'{obj_field_parent.label} (field_num: {obj_field_parent.field_num})'
        )
    subj_parent = subject_field_obj
    i = 0
    while i <= max_depth and subj_parent is not None:
        i += 1
        subj_parent = get_immediate_context_parent_obj_db(
            subj_parent
        )
        if subj_parent == object_field_obj:
            raise ValueError(
                'Circular containment error. '
                f'(Child) object {object_field_obj.label} '
                f'(field_num: {object_field_obj.field_num}) is a parent field for '
                f'{subj_parent.label} (field_num: {subj_parent.field_num})'
            )
    if i > max_depth:
        raise ValueError(
            f'Parent field object {subject_field_obj.label} too deep in hierarchy'
        )
    return True


# Records data source annotations for modeling ETL (extract transform load)
# processes that ingest data into Open Context
class DataSourceAnnotation(models.Model):

    uuid = models.UUIDField(primary_key=True, editable=True)
    data_source = models.ForeignKey(
        DataSource, 
        db_column='source_uuid', 
        related_name='+', 
        on_delete=models.CASCADE, 
    )
    # The data source field that is the subject of this annotation.
    subject_field = models.ForeignKey(
        DataSourceField, 
        db_column='subject_field_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
    )
    # A predicate (attribute or relation) used in this annotation.
    predicate = models.ForeignKey(
        AllManifest, 
        db_column='predicate_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    # The data source field who's values provide the predicate 
    # (attribute or relation) used in this annotation.
    predicate_field = models.ForeignKey(
        DataSourceField,
        db_column='predicate_field_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    # A named entity object of the predicate for this annotation.
    object = models.ForeignKey(
        AllManifest, 
        db_column='object_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    # The data source field who's values provide the objects 
    # used in this annotation.
    object_field = models.ForeignKey(
        DataSourceField,
        db_column='object_field_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    # A constant string object value. For example, if you want to add the exact
    # same note to multiple items in subject_field, obj_sting will have a value.
    # NOTE: The obj_string_hash only exists to determine uniqueness.
    obj_string_hash = models.TextField(null=True)
    obj_string = models.TextField(null=True)
    # A constant boolean object value.
    obj_boolean = models.BooleanField(null=True)
    # A constant integer object value.
    obj_integer = models.BigIntegerField(null=True)
    # A constant double object value.
    obj_double = models.DecimalField(max_digits=19, decimal_places=10, null=True)
     # A constant datetime object value.
    obj_datetime = models.DateTimeField(null=True)
    # Observations are nodes for grouping related assertions.
    observation = models.ForeignKey(
        AllManifest,  
        db_column='observation_uuid', 
        related_name='+', 
        on_delete=models.PROTECT,
        default=configs.DEFAULT_OBS_UUID,
        null=True,
    )
    observation_field = models.ForeignKey(
        DataSourceField,
        db_column='observation_field_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    # Events are nodes for identifying specific space-time grouped
    # assertions.
    event = models.ForeignKey(
        AllManifest,  
        db_column='event_uuid', 
        related_name='+', 
        on_delete=models.PROTECT,
        default=configs.DEFAULT_EVENT_UUID,
        null=True,
    )
    event_field = models.ForeignKey(
        DataSourceField,
        db_column='event_field_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    # Attribute groups are for modeling predicate and object values
    # that need to be understood as a group. For example, a ratio
    # with a numerator and a denominator are 3 grouped assertions that
    # would make sense together in an attribute group.
    attribute_group = models.ForeignKey(
        AllManifest, 
        db_column='attribute_group_uuid', 
        related_name='+', 
        on_delete=models.PROTECT,
        default=configs.DEFAULT_ATTRIBUTE_GROUP_UUID,
        null=True,
    )
    attribute_group_field = models.ForeignKey(
        DataSourceField,
        db_column='attribute_group_field_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    # Language for text in xsd:string objects.
    language =  models.ForeignKey(
        AllManifest,
        db_column='language_uuid', 
        related_name='+', 
        on_delete=models.PROTECT, 
        default=configs.DEFAULT_LANG_UUID,
        null=True,
    )
    language_field =  models.ForeignKey(
        DataSourceField,
        db_column='language_field_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    meta_json = JSONField(default=dict)

    # List of attributes that take DataSourceFields items.
    FIELD_ATTRIBUTE_LIST = [
        'subject_field',
        'predicate_field',
        'object_field',
        'observation_field',
        'event_field',
        'attribute_group_field',
        'language_field',
    ]

    PREDICATE_OK_ITEM_TYPES = ['predicates', 'property', 'class', 'variables']

    def validate_fields_data_sources(self):
        """Validates that field references are in the same data source"""
        field_attributes = [
            ('subjects', self.subject_field,),
            ('predicates', self.predicate_field,),
            ('objects', self.object_field,),
            ('observations', self.observation_field,),
            ('events', self.event_field,),
            ('attribute_groups', self.attribute_group_field,),
            ('languages', self.language_field,),
        ]
        for field_name, attribute_field in field_attributes:
            if attribute_field is None:
                # This is a null, so generally OK.
                continue
            if str(attribute_field.data_source.uuid) == str(self.data_source.uuid):
                # The field is in the same data_source as data_source.
                continue
            raise ValueError(
                f'The {field_name} field {attribute_field.label} (field_num: {attribute_field.field_num}) '
                f'is from data source {attribute_field.data_source.source_id} not {self.data_source.source_id}'
            )


    def validate_attribute_groups(self):
        """Certain groups of attributes should have 1 and only 1 not null value"""
        attribute_groups = [
            (
                'predicates', 
                [
                    self.predicate, 
                    self.predicate_field,
                ],
            ),
            (
                'objects',
                [
                    self.object, 
                    self.object_field,
                    self.obj_string,
                    self.obj_boolean,
                    self.obj_integer,
                    self.obj_double,
                    self.obj_datetime,
                ],
            ),
            (
                'observations',
                [
                    self.observation, 
                    self.observation_field,
                ],
            ),
            (
                'events',
                [
                    self.event,
                    self.event_field,
                ],
            ),
            (
                'attribute_groups',
                [
                    self.attribute_group,
                    self.attribute_group_field
                ],
            ),
            (
                'languages',
                [
                    self.language,
                    self.language_field,
                ],
            ),
        ]
        for group_name, attribute_group in attribute_groups:
            count_not_null = 0
            for attribute in attribute_group:
                if attribute is None:
                    continue
                count_not_null += 1
            if count_not_null != 1:
                raise ValueError(
                    f'Need 1 not null field in the {group_name} group, '
                    f'but {count_not_null} are not null.'
                )
    

    def validate_predicate_item_type(self):
        """validate the item type for the predicate, or predicate_field"""
        if self.predicate and self.predicate.item_type not in self.PREDICATE_OK_ITEM_TYPES:
            raise ValueError(
                f'The object {self.predicate.label}; {self.predicate.item_type} '
                f'cannot be used as a predicate. It must be a {str(self.PREDICATE_OK_ITEM_TYPES)}'
            )
        if self.predicate_field and self.predicate_field.item_type not in self.PREDICATE_OK_ITEM_TYPES:
            raise ValueError(
                f'The field {self.predicate_field.label}; {self.predicate_field.item_type} '
                f'cannot be used for predicates. It must be a {str(self.PREDICATE_OK_ITEM_TYPES)}'
            )


    def make_obj_string_hash(self, obj_string):
        """Makes an object string hash value"""
        if obj_string:
            obj_string = obj_string.strip()
            hash_obj = hashlib.sha1()
            hash_obj.update(str(obj_string).encode('utf-8'))
            return hash_obj.hexdigest()
        else:
            # No string value to hash, so return something
            # small to be nice to our index.
            return '0'


    def primary_key_create(
        self,
        data_source_id,
        subject_field_id,
        predicate_id=None,
        predicate_field_id=None,
        object_id=None,
        object_field_id=None,
        obj_string=None,
        obj_boolean=None,
        obj_integer=None,
        obj_double=None,
        obj_datetime=None,
        observation_id=None,
        observation_field_id=None,
        event_id=None,
        event_field_id=None,
        attribute_group_id=None,
        attribute_group_field_id=None,
        language_id=None,
        language_field_id=None, 
    ):
        """Deterministically make the primary key based on attribute values"""
        data_source_id = str(data_source_id)
        uuid_prefix = data_source_id.split('-')[0]

        if obj_string:
            obj_string = obj_string.strip()

        hash_obj = hashlib.sha1()
        concat_string = " ".join(
            [
                str(data_source_id),
                str(subject_field_id),
                str(predicate_id),
                str(predicate_field_id),
                str(object_id),
                str(object_field_id),
                str(obj_string),
                str(obj_boolean),
                str(obj_integer),
                str(obj_double),
                str(obj_datetime),
                str(observation_id),
                str(observation_field_id),
                str(event_id),
                str(event_field_id),
                str(attribute_group_id),
                str(attribute_group_field_id),
                str(language_id),
                str(language_field_id),
            ]
        )
        hash_obj.update(concat_string.encode('utf-8'))
        hash_id = hash_obj.hexdigest()
        uuid_from_hash_id = str(
            GenUUID.UUID(hex=hash_id[:32])
        )
        new_parts = uuid_from_hash_id.split('-')
        uuid = '-'.join(
            ([uuid_prefix] + new_parts[1:])
        )
        return uuid


    def primary_key_create_for_self(self):
        """Makes a primary key using a prefix from the subject"""
        if self.uuid:
            # One is already defined, so skip this step.
            return self.uuid
        
        entity_fields = [
            (self.data_source, 'data_source_id',),
            (self.subject_field, 'subject_field_id',),
            (self.predicate, 'predicate_id',),
            (self.predicate_field, 'predicate_field_id',),
            (self.object, 'object_id',),
            (self.object_field, 'object_field_id',),
            (self.observation, 'observation_id', ),
            (self.observation_field, 'observation_field_id', ),
            (self.event, 'event_id', ),
            (self.event_field, 'event_field_id', ),
            (self.attribute_group, 'attribute_group_id',),
            (self.attribute_group_field, 'attribute_group_field_id',),
            (self.language, 'language_id',),
            (self.language_field, 'language_field_id',),
        ]
        literal_fields = [
            (self.obj_string, 'obj_string',),
            (self.obj_boolean, 'obj_boolean',),
            (self.obj_integer, 'obj_integer', ),
            (self.obj_double, 'obj_double', ),
            (self.obj_datetime, 'obj_datetime', ),
        ]
        kwargs = {key:val for val, key in literal_fields if val is not None}
        for entity_val, key in entity_fields:
            if entity_val is None:
                continue
            kwargs[key] = entity_val.uuid
        return self.primary_key_create(**kwargs)
    

    def save(self, *args, **kwargs):
        if self.obj_string:
            self.obj_string = self.obj_string.strip()
        
        self.obj_string_hash = self.make_obj_string_hash(self.obj_string)
        self.validate_fields_data_sources()
        self.validate_attribute_groups()

        if self.predicate and str(self.predicate.uuid) == configs.PREDICATE_CONTAINS_UUID:
            # We're attempting to save a containment annotation, so check it.
            validate_context_assertion(self.subject_field, self.object_field)
        
        # Validate that the predicate or predicate_field attributes have an
        # allowed item_type.
        self.validate_predicate_item_type()

        self.uuid = self.primary_key_create_for_self()
        super(DataSourceAnnotation, self).save(*args, **kwargs)


    class Meta:
        db_table = 'etl_annotations'
        ordering = ['data_source', 'subject_field']
        unique_together = (
            "data_source",
            "subject_field",
            "predicate", 
            "predicate_field",
            "object",
            "object_field",
            "obj_string_hash",
            "obj_boolean",
            "obj_integer",
            "obj_double",
            "obj_datetime",
            "language",
            "language_field",
        )


# Records data source individual records for ETL (extract transform load)
# processes that ingest data into Open Context
class DataSourceRecord(models.Model):
    uuid = models.UUIDField(primary_key=True, editable=True)
    data_source = models.ForeignKey(
        DataSource, 
        db_column='source_uuid', 
        related_name='+', 
        on_delete=models.CASCADE, 
    )
    row_num = models.IntegerField()
    field_num = models.IntegerField()
    context = models.ForeignKey(
        AllManifest, 
        db_column='context_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    item = models.ForeignKey(
        AllManifest, 
        db_column='item_uuid', 
        related_name='+', 
        on_delete=models.CASCADE,
        null=True,
    )
    record = models.TextField(default='')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def primary_key_create(self, data_source_id, row_num, field_num):
        """Converts a source_id into a UUID deterministically"""
        data_source_id = str(data_source_id)
        source_row_field = f'{data_source_id }-{row_num}-{field_num}'
        _, uuid_from_field = update_old_id(source_row_field)
        
        # Now assemble a uuid that has the first part of the
        # data source id and the unique part generated from the
        # data source id and the field num
        id_prefix = data_source_id.split('-')[0]
        new_parts = uuid_from_field.split('-')
        uuid = '-'.join(
            ([id_prefix] + new_parts[1:])
        )
        return uuid
    
    def primary_key_create_for_self(self):
        """Makes a primary key using a prefix from the subject"""
        if self.uuid:
            # One is already defined, so skip this step.
            return self.uuid
        return self.primary_key_create(
            self.data_source.uuid, 
            self.row_num, 
            self.field_num
        )
    
    def save(self, *args, **kwargs):
        # Defaults the primary key uuid to value deterministically
        # generated.
        self.uuid = self.primary_key_create_for_self()
        super(DataSourceRecord, self).save(*args, **kwargs)

    class Meta:
        db_table = 'etl_records'
        ordering = ['data_source', 'row_num', 'field_num']
        unique_together = ('data_source', 'row_num', 'field_num')