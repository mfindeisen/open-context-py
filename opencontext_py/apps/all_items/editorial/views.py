import copy
import json
import uuid as GenUUID

from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponse, Http404

from django.db.models import Q

from django.template import RequestContext, loader
from opencontext_py.libs.general import LastUpdatedOrderedDict
from opencontext_py.libs.rootpath import RootPath
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
from opencontext_py.apps.all_items.legacy_all import update_old_id
from opencontext_py.apps.all_items.editorial import api as editorial_api

from django.views.decorators.cache import cache_control
from django.views.decorators.cache import never_cache
from django.views.decorators.cache import cache_page
from django.utils.cache import patch_vary_headers



@never_cache
@cache_control(no_cache=True)
def item_children_json(request, identifier):
    """ API for getting an item and immediate children items """
    api_result = editorial_api.get_item_children(identifier)
    if not api_result:
        return HttpResponse(
            json.dumps([]),
            content_type="application/json; charset=utf8",
            status=404
        )

    json_output = json.dumps(
        api_result,
        indent=4,
        ensure_ascii=False
    )
    return HttpResponse(
        json_output,
        content_type="application/json; charset=utf8"
    )


@never_cache
@cache_control(no_cache=True)
def item_look_up_json(request):
    """API for looking up an item based on a wide range of search criteria"""
    request_dict = {}
    for key, key_val in request.GET.items():
        request_dict[key] = request.GET.get(key)

    api_result, total_count = editorial_api.lookup_manifest_dicts(request_dict)
    output = {
        'totalResults': total_count,
        'results': api_result,
    }
    json_output = json.dumps(
        output,
        indent=4,
        ensure_ascii=False
    )
    return HttpResponse(
        json_output,
        content_type="application/json; charset=utf8"
    )


@never_cache
@cache_control(no_cache=True)
def item_meta_look_up_json(request):
    """API for looking up contextual metadata (project, item_class, context) for item lookups"""
    request_dict = {}
    for key, key_val in request.GET.items():
        request_dict[key] = request.GET.get(key)

    api_result = editorial_api.lookup_up_and_group_general_distinct_metadata(request_dict)
    json_output = json.dumps(
        api_result,
        indent=4,
        ensure_ascii=False
    )
    return HttpResponse(
        json_output,
        content_type="application/json; charset=utf8"
    )