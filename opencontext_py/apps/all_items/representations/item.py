
import copy
import hashlib
import uuid as GenUUID

from django.db.models import OuterRef, Subquery

from opencontext_py.libs.general import LastUpdatedOrderedDict

from opencontext_py.apps.all_items import configs
from opencontext_py.apps.all_items.models import (
    AllManifest,
    AllAssertion,
    AllHistory,
    AllResource,
    AllIdentifier,
    AllSpaceTime,
)
from opencontext_py.apps.all_items import utilities
from opencontext_py.apps.all_items.representations import geojson
from opencontext_py.apps.all_items.representations import metadata
from opencontext_py.apps.all_items.representations import rep_utils



def add_select_related_contexts_to_qs(qs, context_prefix='', depth=10, more_related_objs=['item_class']):
    """Adds select_related contexts to a queryset"""
    # NOTE: This is all about reducing the number of queries we send to the 
    # database. This most important use case for this is to look up parent
    # context paths of manifest "subjects" item_types. 
    act_path = context_prefix
    next_context = 'context'
    for _ in range(depth):
        act_path += next_context
        next_context = '__context'
        qs = qs.select_related(act_path)
        for rel_obj in more_related_objs:
            qs = qs.select_related(f'{act_path}__{rel_obj}')
    return qs


def make_grouped_by_dict_from_queryset(qs, index_list):
    """Makes a dictionary, grouped by attributes of query set objects"""
    keyed_objects = LastUpdatedOrderedDict()
    for obj in qs:
        key = tuple(getattr(obj, act_attrib) for act_attrib in index_list)
        keyed_objects.setdefault(key, []).append(obj)
    return keyed_objects


def get_dict_path_value(path_keys_list, dict_obj, default=None):
    """Get a value from a dictionary object by a list of keys """
    if not isinstance(dict_obj, dict):
        return None
    act_obj = copy.deepcopy(dict_obj)
    for key in path_keys_list:
        act_obj = act_obj.get(key, default)
        if not isinstance(act_obj, dict):
            return act_obj
    return act_obj


def make_tree_dict_from_grouped_qs(qs, index_list):
    """Groups a queryset according to index list of attributes to
    make hierarchically organized lists of dicts
    """
    # NOTE: This works because it relies on mutating a dictionary
    # tree_dict. It's a little hard to understand, which is why
    # there's a debugging function _print_tree_dict to show the
    # outputs.
    grouped_qs_objs = make_grouped_by_dict_from_queryset(qs, index_list)
    tree_dict = LastUpdatedOrderedDict()
    for group_tup_key, obj_list in grouped_qs_objs.items():
        level_dict = tree_dict
        for key in group_tup_key:
            if key != group_tup_key[-1]:
                level_dict.setdefault(key, LastUpdatedOrderedDict())
                level_dict = level_dict[key]
            else:
                level_dict[key] = obj_list
    return tree_dict


def _print_tree_dict(tree_dict, level=0):
    """Debugging print of a tree dict for assertions"""
    indent = level * 4
    for key, vals in tree_dict.items():
        print(
            '-'*indent +
            f'Key: {key.uuid} {key.label}'
        )
        if isinstance(vals, dict):
            _print_tree_dict(vals, level=(level + 1))
        else:
            for ass_obj in vals:
                obj_str = ass_obj.obj_string
                if obj_str is None:
                    obj_str = ''
                obj_str = obj_str[:20]
                print(
                    '-'*indent +
                    '----' +
                    f'Assertion {ass_obj.uuid}: '
                    f'is {ass_obj.subject.label} [{ass_obj.subject.uuid}]'
                    f'-> {ass_obj.predicate.label} [{ass_obj.predicate.uuid}]'
                    f'-> {ass_obj.object.label} [{ass_obj.object.uuid}] '
                    f'Str: {obj_str} '
                    f'Bool: {ass_obj.obj_boolean} '
                    f'Int: {ass_obj.obj_integer} '
                    f'Double: {ass_obj.obj_double} '
                    f'Date: {ass_obj.obj_datetime}'
                )


def get_item_assertions(subject_id, select_related_object_contexts=False):
    """Gets an assertion queryset about an item"""

    # Limit this subquery to only 1 result, the first.
    thumbs_qs = AllResource.objects.filter(
        item=OuterRef('object'),
        resourcetype_id=configs.OC_RESOURCE_THUMBNAIL_UUID,
    ).values('uri')[:1]

    # DC-Creator equivalent predicate
    dc_creator_qs = AllAssertion.objects.filter(
        subject=OuterRef('predicate'),
        predicate_id__in=configs.PREDICATE_LIST_SBJ_EQUIV_OBJ,
        object_id=configs.PREDICATE_DCTERMS_CREATOR_UUID,
        visible=True,
    ).values('object')[:1]

    # DC-Contributor equivalent predicate
    dc_contributor_qs = AllAssertion.objects.filter(
        subject=OuterRef('predicate'),
        predicate_id__in=configs.PREDICATE_LIST_SBJ_EQUIV_OBJ,
        object_id=configs.PREDICATE_DCTERMS_CONTRIBUTOR_UUID,
        visible=True,
    ).values('object')[:1]

    qs = AllAssertion.objects.filter(
        subject_id=subject_id,
        visible=True,
    ).select_related(
        'observation'
    ).select_related(
        'event'
    ).select_related( 
        'attribute_group'
    ).select_related(
        'predicate'
    ).select_related(
        'language'
    ).select_related( 
        'object'
    ).select_related( 
        'object__item_class'
    ).annotate(
        object_thumbnail=Subquery(thumbs_qs)
    ).annotate(
        # This will indicate if a predicate is equivalent to a
        # dublin core creator.
        predicate_dc_creator=Subquery(dc_creator_qs)
    ).annotate(
        # This will indicate if a predicate is equivalent to a
        # dublin core contributor.
        predicate_dc_contributor=Subquery(dc_contributor_qs)
    )
    if select_related_object_contexts:
        # Get the context hierarchy for related objects. We typically
        # only do this for media and documents.
        qs =  add_select_related_contexts_to_qs(
            qs, 
            context_prefix='object__'
        )
    return qs


def get_related_subjects_item_from_object_id(object_id):
    """Gets a Query Set of subjects items related to an assertion object_id"""
    # NOTE: Some media and documents items are only related to 
    # an item_type subject via an assertion where the media and
    # documents items is the object of a assertion relationship.
    # Since an item_type = 'subjects' is needed to establish the
    # full context of a media or document item, and we won't necessarily
    # get a relationship to an item_type = 'subjects' item from
    # the get_item_assertions function, we will often need to
    # do this additional query.
    rel_subj_item_assetion_qs = AllAssertion.objects.filter(
        object_id=object_id,
        subject__item_type='subjects',
        visible=True,
    ).select_related(
        'subject'
    ).select_related(
        'subject__item_class'
    )
    rel_subj_item_assetion_qs = add_select_related_contexts_to_qs(
        rel_subj_item_assetion_qs, 
        context_prefix='subject__'
    )
    return rel_subj_item_assetion_qs.first()


def get_related_subjects_item_assertion(item_man_obj, assert_qs):
    """Gets the related subject item for a media or documents subject item"""
    if item_man_obj.item_type not in ['media', 'documents']:
        return None
    
    for assert_obj in assert_qs:
        if assert_obj.object.item_type == 'subjects':
            return assert_obj.object
    
    # An manifest item_type='subjects' is not the object of any of
    # the assert_qs assertions, so we need to do another database pull
    # to check for manifest item_type 'subjects' items that are the
    # subject of an assertion.
    rel_subj_item_assetion = get_related_subjects_item_from_object_id(
        object_id=item_man_obj.uuid
    )
    if not rel_subj_item_assetion:
        return None
    return rel_subj_item_assetion.subject


def get_observations_attributes_from_assertion_qs(assert_qs):
    """Gets observations and attributes in observations"""
    grp_index_attribs = ['observation', 'event', 'attribute_group', 'predicate']
    grouped_asserts = make_tree_dict_from_grouped_qs(
        qs=assert_qs, 
        index_list=grp_index_attribs
    )
    observations = []
    for observation, events in grouped_asserts.items():
        act_obs = LastUpdatedOrderedDict()
        act_obs['id'] = f'#-obs-{observation.slug}'
        act_obs['label'] = observation.label
        # NOTE: we've added act_obs to the observations list, but
        # we are continuing to modify it, even though it is part this
        # observations list already. 
        observations.append(act_obs)
        for event, attrib_groups in events.items():
            if str(event.uuid) == configs.DEFAULT_EVENT_UUID:
                # NOTE: No event node is specified here, so all the
                # attribute groups and predicates will just be added
                # directly to the act_obs dictionary.
                #
                # How? The beauty of mutable dicts! Below, this will
                # mean that act_obs gets updated as act_event gets
                # updated, since they refer to the same object.
                act_event = act_obs
            else:
                # Make a new act_event dictionary, because we're
                # specifying a new node within this observation.
                act_event = LastUpdatedOrderedDict()
                act_event['id'] = f'#-event-{event.slug}'
                act_event['label'] = event.label
                act_event['type'] = 'oc-gen:events'
                act_obs.setdefault('oc-gen:has-events', [])
                act_obs['oc-gen:has-events'].append(act_event)
            for attrib_group, preds in attrib_groups.items():
                if str(attrib_group.uuid) == configs.DEFAULT_ATTRIBUTE_GROUP_UUID:
                    # NOTE: no attribute group node is specified here, so all
                    # the predicates will be added to the act_event dictionary.
                    #
                    # How? The beauty of mutable dicts! Again, the act_attrib_grp 
                    # will be the same object as the act_event.
                    act_attrib_grp = act_event
                else:
                    act_attrib_grp = LastUpdatedOrderedDict()
                    act_attrib_grp['id'] = f'#-attribute-group-{attrib_group.slug}'
                    act_attrib_grp['label'] = attrib_group.label
                    act_attrib_grp['type'] = 'oc-gen:attribute-groups'
                    act_event.setdefault('oc-gen:has-attribute-groups', [])
                    act_event['oc-gen:has-attribute-groups'].append(act_attrib_grp)
                # Now add the predicate keys and their assertion objects to
                # the act_attrib_grp
                act_attrib_grp = rep_utils.add_predicates_assertions_to_dict(
                    pred_keyed_assert_objs=preds, 
                    act_dict=act_attrib_grp
                )

    return observations


def get_related_media_resources(item_man_obj):
    """Gets related media resources for a media subject"""
    if item_man_obj.item_type not in ['media', 'projects']:
        return None
    resource_qs = AllResource.objects.filter(
        item=item_man_obj,
    ).select_related(
        'resourcetype'
    ).select_related(
        'mediatype'
    )
    return resource_qs


def add_related_media_files_dicts(item_man_obj, act_dict=None):
    resource_qs = get_related_media_resources(item_man_obj)
    if not resource_qs:
        return act_dict
    if not act_dict:
        act_dict = LastUpdatedOrderedDict()
    act_dict["oc-gen:has-files"] = []
    for res_obj in resource_qs:
        res_dict = LastUpdatedOrderedDict()
        res_dict['id'] = f'https://{res_obj.uri}'
        res_dict['type'] = rep_utils.get_item_key_or_uri_value(res_obj.resourcetype)
        res_dict['dc-terms:hasFormat'] = f'https://{res_obj.mediatype.uri}'
        if res_obj.filesize > 1:
            res_dict['dcat:size'] = int(res_obj.filesize)
        act_dict["oc-gen:has-files"].append(res_dict)
    return act_dict


def add_to_parent_context_list(manifest_obj, context_list=None):
    if context_list is None:
        context_list = []
    if manifest_obj.item_type != 'subjects':
        return context_list
    item_dict = LastUpdatedOrderedDict()
    item_dict['id'] = f'https://{manifest_obj.uri}'
    item_dict['slug'] = manifest_obj.slug
    item_dict['label'] = manifest_obj.label
    item_dict['type'] = rep_utils.get_item_key_or_uri_value(manifest_obj.item_class)
    context_list.append(item_dict)
    if (manifest_obj.context.item_type == 'subjects' 
       and str(manifest_obj.context.uuid) != configs.DEFAULT_SUBJECTS_ROOT_UUID):
        context_list = add_to_parent_context_list(manifest_obj.context, context_list=context_list)
    return context_list


def start_item_representation_dict(item_man_obj):
    """Start making an item representation dictionary object"""
    rep_dict = LastUpdatedOrderedDict()
    rep_dict['uuid'] = str(item_man_obj.uuid)
    rep_dict['slug'] = item_man_obj.slug
    rep_dict['label'] = item_man_obj.label
    if item_man_obj.item_class and str(item_man_obj.item_class.uuid) != configs.DEFAULT_CLASS_UUID:
        if item_man_obj.item_class.item_key:
            rep_dict['category'] = item_man_obj.item_class.item_key
        else:
            rep_dict['category'] = f'https://{item_man_obj.item_class.uri}'
    return rep_dict


def make_representation_dict(subject_id):
    """Makes a representation dict for a subject id"""
    # This will most likely get all the context hierarchy in 1 query, thereby
    # limiting the number of times we hit the database.
    item_man_obj_qs = AllManifest.objects.filter(
        uuid=subject_id
    ).select_related(
        'project'
    ).select_related(
        'item_class'
    )
    item_man_obj_qs = add_select_related_contexts_to_qs(
        item_man_obj_qs
    )
    item_man_obj = item_man_obj_qs.first()
    if not item_man_obj:
        return None
    rep_dict = start_item_representation_dict(item_man_obj)

    select_related_object_contexts = False
    if item_man_obj.item_type in ['media', 'documents']:
        # We'll want to include the selection of related
        # object contexts to get the spatial hierarchy of related
        # item_type subjects.
        select_related_object_contexts = True
    # Get the assertion query set for this item
    assert_qs = get_item_assertions(
        subject_id=item_man_obj.uuid,
        select_related_object_contexts=select_related_object_contexts
    )
    # Get the related subjects item (for media and documents)
    # NOTE: rel_subjects_man_obj will be None for all other item types.
    rel_subjects_man_obj = get_related_subjects_item_assertion(
        item_man_obj, 
        assert_qs
    )

    # Adds geojson features. This will involve a database query to fetch
    # spacetime objects.
    rep_dict = geojson.add_geojson_features(
        item_man_obj, 
        rel_subjects_man_obj=rel_subjects_man_obj, 
        act_dict=rep_dict
    )

    # Add the list of media resources associated with this item if
    # the item has the appropriate item_type.
    rep_dict = add_related_media_files_dicts(item_man_obj, act_dict=rep_dict)

    if item_man_obj.item_type == 'subjects':
        parent_list = add_to_parent_context_list(item_man_obj.context)
        if parent_list:
            # The parent order needs to be reversed to make the most
            # general first, followed by the most specific.
            parent_list.reverse()
            rep_dict['oc-gen:has-contexts'] = parent_list
    elif rel_subjects_man_obj:
        parent_list = add_to_parent_context_list(rel_subjects_man_obj)
        if parent_list:
            # The parent order needs to be reversed to make the most
            # general first, followed by the most specific.
            parent_list.reverse()
            rep_dict['oc-gen:has-linked-contexts'] = parent_list

    if item_man_obj.item_type in ['subjects', 'media', 'documents', 'persons', 'projects']:
        # These types of items have nested nodes of observations, 
        # events, and attribute-groups
        observations = get_observations_attributes_from_assertion_qs(assert_qs)
        rep_dict['oc-gen:has-obs'] = observations
    else:
        # The following is for other types of items that don't have lots
        # of nested observation, event, and attribute nodes.
        pred_keyed_assert_objs = make_tree_dict_from_grouped_qs(
            qs=assert_qs, 
            index_list=['predicate']
        )
        rep_dict = rep_utils.add_predicates_assertions_to_dict(
            pred_keyed_assert_objs, 
            act_dict=rep_dict
        )
    
    # NOTE: This adds Dublin Core metadata
    rep_dict = metadata.add_dublin_core_literal_metadata(
        item_man_obj, 
        rel_subjects_man_obj=rel_subjects_man_obj, 
        act_dict=rep_dict
    )
    # First add item-specific Dublin Core creators, contributors.
    rep_dict = metadata.add_dc_creator_contributor_equiv_metadata(
        assert_qs, 
        act_dict=rep_dict
    )
    # NOTE: This add project Dublin Core metadata.
    proj_metadata_qs = metadata.get_project_metadata_qs(
        project=item_man_obj.project
    )
    pred_keyed_assert_objs = make_tree_dict_from_grouped_qs(
        qs=proj_metadata_qs, 
        index_list=['predicate']
    )
    # Add project metadata, but only for those predicates that
    # don't already have item-specific object values.
    rep_dict = rep_utils.add_predicates_assertions_to_dict(
        pred_keyed_assert_objs, 
        act_dict=rep_dict,
        add_objs_to_existing_pred=False,
    )
    return rep_dict