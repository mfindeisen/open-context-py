import time
import json
import django.utils.http as http
from datetime import datetime
from django.conf import settings
from opencontext_py.libs.general import LastUpdatedOrderedDict
from opencontext_py.apps.entities.entity.models import Entity
from opencontext_py.apps.ocitems.assertions.containment import Containment
from opencontext_py.apps.indexer.solrdocument import SolrDocument
from opencontext_py.apps.ocitems.namespaces.models import ItemNamespaces
from opencontext_py.apps.searcher.solrsearcher.responsetypes import SolrResponseTypes
from opencontext_py.apps.searcher.solrsearcher.filterlinks import FilterLinks
from opencontext_py.apps.searcher.solrsearcher.querymaker import QueryMaker
from opencontext_py.apps.searcher.solrsearcher.regions import JsonLDregions
from opencontext_py.apps.searcher.solrsearcher.records import JsonLDrecords
from opencontext_py.apps.searcher.solrsearcher.uuids import SolrUUIDs


class MakeJsonLd():

    def __init__(self, request_dict):
        self.hierarchy_delim = '---'
        self.request_dict = request_dict
        self.request_dict_json = json.dumps(request_dict,
                                            ensure_ascii=False,
                                            indent=4)
        self.request_full_path = False
        self.spatial_context = False
        # ---------------
        # get the type of responses requested
        # ---------------
        self.act_responses = SolrResponseTypes(self.request_dict).responses
        self.id = False
        self.entities = {}
        self.label = settings.CANONICAL_SITENAME + ' API'
        self.json_ld = LastUpdatedOrderedDict()
        item_ns = ItemNamespaces()
        context = item_ns.namespaces
        self.namespaces = context
        context['opensearch'] = 'http://a9.com/-/spec/opensearch/1.1/'
        context['totalResults'] = {'@id': 'opensearch:totalResults', '@type': 'xsd:integer'}
        context['startIndex'] = {'@id': 'opensearch:startIndex', '@type': 'xsd:integer'}
        context['itemsPerPage'] = {'@id': 'opensearch:itemsPerPage', '@type': 'xsd:integer'}
        context['oc-gen'] = 'http://opencontext.org/vocabularies/oc-general/'
        context['oc-api'] = 'http://opencontext.org/vocabularies/oc-api/'
        context['first'] = {'@id': 'oc-api:first', '@type': '@id'}
        context['previous'] = {'@id': 'oc-api:previous', '@type': '@id'}
        context['next'] = {'@id': 'oc-api:next', '@type': '@id'}
        context['last'] = {'@id': 'oc-api:last', '@type': '@id'}
        context['first-json'] = {'@id': 'oc-api:first', '@type': '@id'}
        context['previous-json'] = {'@id': 'oc-api:previous', '@type': '@id'}
        context['next-json'] = {'@id': 'oc-api:next', '@type': '@id'}
        context['last-json'] = {'@id': 'oc-api:last', '@type': '@id'}
        context['count'] = {'@id': 'oc-api:count', '@type': 'xsd:integer'}
        context['json'] = {'@id': 'oc-api:count', '@type': '@id'}
        context['id'] = '@id'
        context['label'] = 'rdfs:label'
        context['uuid'] = 'dc-terms:identifier'
        context['slug'] = 'oc-gen:slug'
        context['type'] = '@type'
        context['category'] = {'@id': 'oc-gen:category', '@type': '@id'}
        context['Feature'] = 'geojson:Feature'
        context['FeatureCollection'] = 'geojson:FeatureCollection'
        context['GeometryCollection'] = 'geojson:GeometryCollection'
        context['Instant'] = 'http://www.w3.org/2006/time#Instant'
        context['Interval'] = 'http://www.w3.org/2006/time#Interval'
        context['LineString'] = 'geojson:LineString'
        context['MultiLineString'] = 'geojson:MultiLineString'
        context['MultiPoint'] = 'geojson:MultiPoint'
        context['MultiPolygon'] = 'geojson:MultiPolygon'
        context['Point'] = 'geojson:Point'
        context['Polygon'] = 'geojson:Polygon'
        context['bbox'] = {'@id': 'geojson:bbox', '@container': '@list'}
        context['circa'] = 'geojson:circa'
        context['coordinates'] = 'geojson:coordinates'
        context['datetime'] = 'http://www.w3.org/2006/time#inXSDDateTime'
        context['description'] = 'dc-terms:description'
        context['features'] = {'@id': 'geojson:features', '@container': '@set'}
        context['geometry'] = 'geojson:geometry'
        context['properties'] = 'geojson:properties'
        context['start'] = 'http://www.w3.org/2006/time#hasBeginning'
        context['stop'] = 'http://www.w3.org/2006/time#hasEnding'
        context['title'] = 'dc-terms:title'
        context['when'] = 'geojson:when'
        self.base_context = context

    def convert_solr_json(self, solr_json):
        """ Converst the solr jsont """
        ok_show_debug = True
        if 'context' in self.act_responses:
            self.json_ld['@context'] = self.base_context
        if 'metadata' in self.act_responses:
            self.json_ld['id'] = self.make_id()
            self.json_ld['label'] = self.label
            self.json_ld['dcmi:modified'] = self.get_modified_datetime(solr_json)
            self.json_ld['dcmi:created'] = self.get_created_datetime(solr_json)
            self.add_paging_json(solr_json)
            self.add_filters_json()
            self.add_text_fields()
        if 'facet' in self.act_responses:
            self.add_numeric_fields(solr_json)
            self.add_date_fields(solr_json)
        if 'geo-facet' in self.act_responses:
            #now check for discovery geotiles
            self.make_discovery_geotiles(solr_json)
        if 'facet' in self.act_responses:
            # now make the regular facets
            self.make_facets(solr_json)
        if 'geo-record' in self.act_responses:
            # now add the result information
            json_recs_obj = JsonLDrecords()
            json_recs_obj.make_records_from_solr(solr_json)
            if len(json_recs_obj.geojson_recs) > 0:
                self.json_ld['type'] = 'FeatureCollection'
                if 'features' not in self.json_ld:
                    self.json_ld['features'] = []
                self.json_ld['features'] += json_recs_obj.geojson_recs
        if 'uuid' in self.act_responses:
            solr_uuids = SolrUUIDs()
            uuids = solr_uuids.make_uuids_from_solr(solr_json)
            if len(self.act_responses) > 1:
                # return a list inside a key
                self.json_ld['oc-api:uuids'] = uuids
            else:
                # just return a simple list
                self.json_ld = uuids
                ok_show_debug = False
        if 'uri' in self.act_responses:
            solr_uuids = SolrUUIDs()
            uris = solr_uuids.make_uris_from_solr(solr_json)
            if len(self.act_responses) > 1:
                # return a list inside a key
                self.json_ld['oc-api:has-results'] = uris
            else:
                # just return a simple list
                self.json_ld = uris
                ok_show_debug = False
        elif 'uri-meta' in self.act_responses:
            solr_uuids = SolrUUIDs()
            uris = solr_uuids.make_uris_from_solr(solr_json,
                                                  False)
            if len(self.act_responses) > 1:
                # return a list inside a key
                self.json_ld['oc-api:has-results'] = uris
            else:
                # just return a simple list
                self.json_ld = uris
                ok_show_debug = False
        if settings.DEBUG and ok_show_debug:
            self.json_ld['request'] = self.request_dict
            # self.json_ld['request'] = self.request_dict
            self.json_ld['solr'] = solr_json
        return self.json_ld

    def add_paging_json(self, solr_json):
        """ adds JSON for paging through results """
        total_found = self.get_path_in_dict(['response',
                                            'numFound'],
                                            solr_json)
        start = self.get_path_in_dict(['responseHeader',
                                       'params',
                                       'start'],
                                      solr_json)
        rows = self.get_path_in_dict(['responseHeader',
                                      'params',
                                      'rows'],
                                     solr_json)
        if start is not False \
           and rows is not False \
           and total_found is not False:
            # add numeric information about this search
            total_found = int(float(total_found))
            start = int(float(start))
            rows = int(float(rows))
            self.json_ld['totalResults'] = total_found
            self.json_ld['startIndex'] = start
            self.json_ld['itemsPerPage'] = rows
            # start off with a the request dict, then
            # remove 'start' and 'rows' parameters
            ini_request_dict = self.request_dict
            if 'start' in ini_request_dict:
                ini_request_dict.pop('start', None)
            if 'rows' in ini_request_dict:
                ini_request_dict.pop('rows', None)
            # do this stupid crap so as not to get a memory
            # error with FilterLinks()
            ini_request_dict_json = json.dumps(ini_request_dict,
                                               ensure_ascii=False,
                                               indent=4)
            # add a first page link
            links = self.make_paging_links(0,
                                           rows,
                                           ini_request_dict_json)
            self.json_ld['first'] = links['html']
            self.json_ld['first-json'] = links['json']
            if start > rows:
                # add a previous page link
                links = self.make_paging_links(start - rows,
                                               rows,
                                               ini_request_dict_json)
                self.json_ld['previous'] = links['html']
                self.json_ld['previous-json'] = links['json']
            if start + rows < total_found:
                # add a next page link
                links = self.make_paging_links(start + rows,
                                               rows,
                                               ini_request_dict_json)
                self.json_ld['next'] = links['html']
                self.json_ld['next-json'] = links['json']
            num_pages = round(total_found / rows, 0)
            if num_pages * rows >= total_found:
                num_pages -= 1
            # add a last page link
            links = self.make_paging_links(num_pages * rows,
                                           rows,
                                           ini_request_dict_json)
            self.json_ld['last'] = links['html']
            self.json_ld['last-json'] = links['json']

    def make_paging_links(self, start, rows, ini_request_dict_json):
        """ makes links for paging for start, rows, with
            an initial request dict json string

            a big of a hassle to avoid memory errors with FilterLinks()
        """
        start = int(start)
        start = str(start)
        rows = str(rows)
        fl = FilterLinks()
        fl.base_request_json = ini_request_dict_json
        fl.spatial_context = self.spatial_context
        start_rparams = fl.add_to_request('start',
                                          start)
        start_rparams_json = json.dumps(start_rparams,
                                        ensure_ascii=False,
                                        indent=4)
        fl.base_request_json = start_rparams_json
        new_rparams = fl.add_to_request('rows',
                                        rows)
        return fl.make_request_urls(new_rparams)

    def add_filters_json(self):
        """ adds JSON describing search filters """
        fl = FilterLinks()
        filters = []
        string_fields = []  # so we have an interface for string searches
        i = 0
        for param_key, param_vals in self.request_dict.items():
            if param_key == 'path':
                if param_vals is not False and param_vals is not None:
                    i += 1
                    f_entity = self.get_entity(param_vals, True)
                    label = http.urlunquote_plus(param_vals)
                    act_filter = LastUpdatedOrderedDict()
                    act_filter['id'] = '#filter-' + str(i)
                    act_filter['oc-api:filter'] = 'Context'
                    act_filter['label'] = label.replace('||', ' OR ')
                    if f_entity is not False:
                        act_filter['rdfs:isDefinedBy'] = f_entity.uri
                    # generate a request dict without the context filter
                    rem_request = fl.make_request_sub(self.request_dict,
                                                      param_key,
                                                      param_vals)
                    act_filter['oc-api:remove'] = fl.make_request_url(rem_request)
                    act_filter['oc-api:remove-json'] = fl.make_request_url(rem_request, '.json')
                    filters.append(act_filter)
            else:
                for param_val in param_vals:
                    i += 1
                    act_filter = LastUpdatedOrderedDict()
                    act_filter['id'] = '#filter-' + str(i)
                    if self.hierarchy_delim in param_val:
                        all_vals = param_val.split(self.hierarchy_delim)
                    else:
                        all_vals = [param_val]
                    if param_key == 'proj':
                        # projects, only care about the last item in the parameter value
                        act_filter['oc-api:filter'] = 'Project'
                        label_dict = self.make_filter_label_dict(all_vals[-1])
                        act_filter['label'] = label_dict['label']
                        if len(label_dict['entities']) == 1:
                            act_filter['rdfs:isDefinedBy'] = label_dict['entities'][0].uri
                    elif param_key == 'prop':
                        # prop, the first item is the filter-label
                        # the last is the filter
                        act_filter['label'] = False
                        if len(all_vals) < 2:
                            act_filter['oc-api:filter'] = 'Description'
                        else:
                            filt_dict = self.make_filter_label_dict(all_vals[0])
                            act_filter['oc-api:filter'] = filt_dict['label']
                            if filt_dict['data-type'] == 'string':
                                act_filter['label'] = 'Search Term: \'' + all_vals[-1] + '\''
                        if act_filter['label'] is False:
                            label_dict = self.make_filter_label_dict(all_vals[-1])
                            act_filter['label'] = label_dict['label']
                    elif param_key == 'type':
                        act_filter['oc-api:filter'] = 'Open Context Type'
                        if all_vals[0] in QueryMaker.TYPE_MAPPINGS:
                            type_uri = QueryMaker.TYPE_MAPPINGS[all_vals[0]]
                            label_dict = self.make_filter_label_dict(type_uri)
                            act_filter['label'] = label_dict['label']
                        else:
                            act_filter['label'] = all_vals[0]
                    elif param_key == 'q':
                        act_filter['oc-api:filter'] = 'General Keyword Search'
                        act_filter['label'] = 'Search Term: \'' + all_vals[0] + '\''
                    rem_request = fl.make_request_sub(self.request_dict,
                                                      param_key,
                                                      param_val)
                    act_filter['oc-api:remove'] = fl.make_request_url(rem_request)
                    act_filter['oc-api:remove-json'] = fl.make_request_url(rem_request, '.json')
                    filters.append(act_filter)
        if len(filters) > 0:
            self.json_ld['oc-api:has-filters'] = filters

    def make_filter_label_dict(self, act_val):
        """ returns a dictionary object
            with a label and set of entities (in cases of OR
            searchs)
        """
        output = {'label': False,
                  'data-type': 'id',
                  'slug': False,
                  'entities': []}
        labels = []
        if '||' in act_val:
            vals = act_val.split('||')
        else:
            vals = [act_val]
        for val in vals:
            f_entity = self.get_entity(val)
            if f_entity is not False:
                qm = QueryMaker()
                # get the solr field data type
                ent_solr_data_type = qm.get_solr_field_type(f_entity.data_type)
                if ent_solr_data_type is not False \
                   and ent_solr_data_type != 'id':
                    output['data-type'] = ent_solr_data_type
                labels.append(f_entity.label)
                output['entities'].append(f_entity)
        output['label'] = ' OR '.join(labels)
        output['slug'] = '-or-'.join(vals)
        return output

    def get_entity(self, identifier, is_path=False):
        """ looks up an entity """
        output = False
        identifier = http.urlunquote_plus(identifier)
        if identifier in self.entities:
            # best case scenario, the entity is already looked up
            output = self.entities[identifier]
        else:
            found = False
            entity = Entity()
            if is_path:
                found = entity.context_dereference(identifier)
            else:
                found = entity.dereference(identifier)
                if found is False:
                    # case of linked data slugs
                    found = entity.dereference(identifier, identifier)
            if found:
                output = entity
        return output

    def make_id(self):
        """ makes the ID for the document """
        if self.id is not False:
            output = self.id
        elif self.request_full_path is not False:
            output = settings.CANONICAL_HOST + self.request_full_path
        else:
            output = False
        return output

    def get_modified_datetime(self, solr_json):
        """ Makes the last modified time in ISO 8601 format
            Solr already defaults to that format
        """
        modified = self.get_path_in_dict(['stats',
                                          'stats_fields',
                                          'updated',
                                          'max'],
                                         solr_json)
        if modified is False:
            modified = time.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        return modified

    def get_created_datetime(self, solr_json):
        """ Makes the last modified time in ISO 8601 format
            Solr already defaults to that format
        """
        created = self.get_path_in_dict(['stats',
                                        'stats_fields',
                                        'published',
                                        'max'],
                                        solr_json)
        if created is False:
            created = time.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        return created

    def add_text_fields(self):
        """ adds text fields with query options """
        text_fields = []
        # first add a general key-word search option
        fl = FilterLinks()
        fl.base_request_json = self.request_dict_json
        fl.base_r_full_path = self.request_full_path
        fl.spatial_context = self.spatial_context
        q_request_dict = self.request_dict
        if 'q' not in q_request_dict:
            q_request_dict['q'] = []
        param_vals = q_request_dict['q']
        if len(param_vals) < 1:
            search_term = None
        else:
            search_term = param_vals[0]
        field = LastUpdatedOrderedDict()
        field['id'] = '#textfield-keyword-search'
        field['label'] = 'General Keyword Search'
        field['oc-api:search-term'] = search_term
        if search_term is False or search_term is None:
            new_rparams = fl.add_to_request_by_solr_field('q',
                                                          '{SearchTerm}')
            field['oc-api:template'] = fl.make_request_url(new_rparams)
            field['oc-api:template-json'] = fl.make_request_url(new_rparams, '.json')
        else:
            param_search = param_vals[0].replace(search_term, '{SearchTerm}')
            rem_request = fl.make_request_sub(q_request_dict,
                                              'q',
                                              search_term,
                                              '{SearchTerm}')
            field['oc-api:template'] = fl.make_request_url(rem_request)
            field['oc-api:template-json'] = fl.make_request_url(rem_request, '.json')
        text_fields.append(field)
        # now add an option looking in properties
        if 'prop' in self.request_dict:
            param_vals = self.request_dict['prop']
            for param_val in param_vals:
                if self.hierarchy_delim in param_val:
                    all_vals = param_val.split(self.hierarchy_delim)
                else:
                    all_vals = [param_val]
                if len(all_vals) < 2:
                    check_field = all_vals[0]
                    search_term = None  # no search term
                else:
                    check_field = all_vals[-2]  # penultimate value is the field
                    search_term = all_vals[-1]  # last value is search term
                check_dict = self.make_filter_label_dict(check_field)
                if check_dict['data-type'] == 'string':
                    fl = FilterLinks()
                    fl.base_request_json = self.request_dict_json
                    fl.base_r_full_path = self.request_full_path
                    fl.spatial_context = self.spatial_context
                    field = LastUpdatedOrderedDict()
                    field['id'] = '#textfield-' + check_dict['slug']
                    field['label'] = check_dict['label']
                    field['oc-api:search-term'] = search_term
                    if len(check_dict['entities']) == 1:
                        field['rdfs:isDefinedBy'] = check_dict['entities'][0].uri
                    if search_term is False or search_term is None:
                        param_search = param_val + self.hierarchy_delim + '{SearchTerm}'
                        new_rparams = fl.add_to_request_by_solr_field('prop',
                                                                      param_search)
                        field['oc-api:template'] = fl.make_request_url(new_rparams)
                        field['oc-api:template-json'] = fl.make_request_url(new_rparams, '.json')
                    else:
                        param_search = param_val.replace(search_term, '{SearchTerm}')
                        rem_request = fl.make_request_sub(self.request_dict,
                                                          'prop',
                                                          param_val,
                                                          param_search)
                        field['oc-api:template'] = fl.make_request_url(rem_request)
                        field['oc-api:template-json'] = fl.make_request_url(rem_request, '.json')
                    text_fields.append(field)
        if len(text_fields) > 0:
            self.json_ld['oc-api:has-text-search'] = text_fields

    def get_solr_ranges(self, solr_json, data_type):
        """ gets solr ranges of a specific data-type """
        output = LastUpdatedOrderedDict()
        facet_ranges = self.get_path_in_dict(['facet_counts',
                                              'facet_ranges'],
                                             solr_json)
        if isinstance(facet_ranges, dict):
            for solr_field_key, ranges in facet_ranges.items():
                facet_key_list = solr_field_key.split('___')
                slug = facet_key_list[0].replace('_', '-')
                fdata_type = facet_key_list[-1].replace('pred_', '')
                # print('Check: ' + fdata_type + ' on ' + data_type)
                if fdata_type == data_type:
                    output[solr_field_key] = ranges
        if len(output) < 1:
            output = False
        return output

    def add_numeric_fields(self, solr_json):
        """ adds numeric fields with query options """
        num_fields = []
        num_facet_ranges = self.get_solr_ranges(solr_json, 'numeric')
        if num_facet_ranges is not False:
            for solr_field_key, ranges in num_facet_ranges.items():
                facet_key_list = solr_field_key.split('___')
                slug = facet_key_list[0].replace('_', '-')
                # check to see if the field is a linkded data field
                # if so, it needs some help with making Filter Links
                linked_field = False
                field_entity = self.get_entity(slug)
                if field_entity is not False:
                    if field_entity.item_type == 'uri':
                        linked_field = True
                field = self.get_facet_meta(solr_field_key)
                field['oc-api:min'] = float(ranges['start'])
                field['oc-api:max'] = float(ranges['end'])
                gap = float(ranges['gap'])
                field['oc-api:gap'] = gap
                field['oc-api:has-range-options'] = []
                i = -1
                for range_min_key in ranges['counts'][::2]:
                    i += 2
                    solr_count = ranges['counts'][i]
                    fl = FilterLinks()
                    fl.base_request_json = self.request_dict_json
                    fl.base_r_full_path = self.request_full_path
                    fl.spatial_context = self.spatial_context
                    fl.partial_param_val_match = linked_field
                    range_start = float(range_min_key)
                    range_end = range_start + gap
                    solr_range = '[' + str(range_start) + ' TO ' + str(range_end) + ' ]'
                    new_rparams = fl.add_to_request('prop',
                                                    solr_range,
                                                    slug)
                    range_dict = LastUpdatedOrderedDict()
                    range_dict['id'] = fl.make_request_url(new_rparams)
                    range_dict['json'] = fl.make_request_url(new_rparams, '.json')
                    range_dict['label'] = str(round(range_start,3))
                    range_dict['count'] = solr_count
                    range_dict['oc-api:min'] = range_start
                    range_dict['oc-api:max'] = range_end
                    field['oc-api:has-range-options'].append(range_dict)
                num_fields.append(field)
        if len(num_fields) > 0:
            self.json_ld['oc-api:has-numeric-facets'] = num_fields

    def add_date_fields(self, solr_json):
        """ adds numeric fields with query options """
        date_fields = []
        date_facet_ranges = self.get_solr_ranges(solr_json, 'date')
        if date_facet_ranges is not False:
            for solr_field_key, ranges in date_facet_ranges.items():
                facet_key_list = solr_field_key.split('___')
                slug = facet_key_list[0].replace('_', '-')
                # check to see if the field is a linkded data field
                # if so, it needs some help with making Filter Links
                linked_field = False
                field_entity = self.get_entity(slug)
                if field_entity is not False:
                    if field_entity.item_type == 'uri':
                        linked_field = True
                field = self.get_facet_meta(solr_field_key)
                field['oc-api:min-date'] = ranges['start']
                field['oc-api:max-date'] = ranges['end']
                field['oc-api:gap-date'] = ranges['gap']
                field['oc-api:has-range-options'] = []
                i = -1
                qm = QueryMaker()
                for range_min_key in ranges['counts'][::2]:
                    i += 2
                    solr_count = ranges['counts'][i]
                    fl = FilterLinks()
                    fl.base_request_json = self.request_dict_json
                    fl.base_r_full_path = self.request_full_path
                    fl.spatial_context = self.spatial_context
                    fl.partial_param_val_match = linked_field
                    dt_end = qm.add_solr_gap_to_date(range_min_key, ranges['gap'])
                    range_end = qm.convert_date_to_solr_date(dt_end)
                    solr_range = '[' + range_min_key + ' TO ' + range_end + ' ]'
                    new_rparams = fl.add_to_request('prop',
                                                    solr_range,
                                                    slug)
                    range_dict = LastUpdatedOrderedDict()
                    range_dict['id'] = fl.make_request_url(new_rparams)
                    range_dict['json'] = fl.make_request_url(new_rparams, '.json')
                    range_dict['label'] = qm.make_human_readable_date(range_min_key) + ' to ' + qm.make_human_readable_date(range_end)
                    range_dict['count'] = solr_count
                    range_dict['oc-api:min-date'] = range_min_key
                    range_dict['oc-api:max-date'] = range_end
                    field['oc-api:has-range-options'].append(range_dict)
                date_fields.append(field)
        if len(date_fields) > 0:
            self.json_ld['oc-api:has-date-facets'] = date_fields

    def make_discovery_geotiles(self, solr_json):
        """ discovery geotiles need
            special handling.
            This finds any geodiscovery tiles
            and removes them from the other list
            of facets
        """
        solr_disc_geotile_facets = self.get_path_in_dict(['facet_counts',
                                                         'facet_fields',
                                                         'discovery_geotile'],
                                                         solr_json)
        if solr_disc_geotile_facets is not False:
            geo_regions = JsonLDregions(solr_json)
            geo_regions.spatial_context = self.spatial_context
            geo_regions.set_aggregation_depth(self.request_dict)  # also needed for making filter links
            geo_regions.process_solr_tiles(solr_disc_geotile_facets)
            if len(geo_regions.geojson_regions) > 0:
                self.json_ld['type'] = 'FeatureCollection'
                self.json_ld['features'] = geo_regions.geojson_regions

    def make_facets(self, solr_json):
        """ Makes a list of facets """
        solr_facet_fields = self.get_path_in_dict(['facet_counts',
                                                  'facet_fields'],
                                                  solr_json)
        if solr_facet_fields is not False:
            pre_sort_facets = {}
            json_ld_facets = []
            if 'discovery_geotile' in solr_facet_fields:
                # remove the geotile field
                solr_facet_fields.pop('discovery_geotile', None)
            for solr_facet_key, solr_facet_values in solr_facet_fields.items():
                facet = self.get_facet_meta(solr_facet_key)
                count_raw_values = len(solr_facet_values)
                id_options = []
                num_options = []
                date_options = []
                string_options = []
                i = -1
                if facet['data-type'] == 'id':
                    for solr_facet_value_key in solr_facet_values[::2]:
                        i += 2
                        solr_facet_count = solr_facet_values[i]
                        facet_val_obj = self.make_facet_value_obj(solr_facet_key,
                                                                  solr_facet_value_key,
                                                                  solr_facet_count)
                        val_obj_data_type = facet_val_obj['data-type']
                        facet_val_obj.pop('data-type', None)
                        if val_obj_data_type == 'id':
                            id_options.append(facet_val_obj)
                        elif val_obj_data_type == 'numeric':
                            num_options.append(facet_val_obj)
                        elif val_obj_data_type == 'date':
                            date_options.append(facet_val_obj)
                        elif val_obj_data_type == 'string':
                            string_options.append(facet_val_obj)
                    if len(id_options) > 0:
                        facet['oc-api:has-id-options'] = id_options
                    if len(num_options) > 0:
                        facet['oc-api:has-numeric-options'] = num_options
                    if len(date_options) > 0:
                        facet['oc-api:has-date-options'] = date_options
                    if len(string_options) > 0:
                        facet['oc-api:has-text-options'] = string_options
                    if count_raw_values > 0:
                        # check so facets without options are not presented
                        pre_sort_facets[facet['id']] = facet
                else:
                    pre_sort_facets[facet['id']] = facet
            # now make a sorted list of facets
            json_ld_facets = self.make_sorted_facet_list(pre_sort_facets)
            if len(json_ld_facets) > 0:
                self.json_ld['oc-api:has-facets'] = json_ld_facets

    def make_sorted_facet_list(self, pre_sort_facets):
        """ makes a list of sorted facets based on 
            a dictionary oject of pre_sort_facets
        """
        json_ld_facets = []
        used_keys = []
        if 'prop' in self.request_dict:
            # first check for 'prop' related facets
            # these get promoted to the first positions in the list
            raw_plist = self.request_dict['prop']
            plist = raw_plist[::-1]  # reverse the list, so last props first
            qm = QueryMaker()
            for param_val in plist:
                param_paths = qm.expand_hierarchy_options(param_val)
                for id_key, facet in pre_sort_facets.items():
                    for param_slugs in param_paths:
                        last_slug = param_slugs[-1]
                        if last_slug in id_key \
                           and id_key not in used_keys:
                            # the facet id has the last slug id!
                            # so add to the ordered list of facets
                            json_ld_facets.append(facet)
                            used_keys.append(id_key)
        # now add facet for context
        for id_key, facet in pre_sort_facets.items():
            if '#facet-context' in id_key \
               and id_key not in used_keys:
                json_ld_facets.append(facet)
                used_keys.append(id_key)
        # now add facet for item-types
        if '#facet-item-type' in pre_sort_facets \
           and '#facet-item-type' not in used_keys:
                json_ld_facets.append(pre_sort_facets['#facet-item-type'])
                used_keys.append('#facet-item-type')
        # now add item categories
        for id_key, facet in pre_sort_facets.items():
            if '#facet-prop-oc-gen-' in id_key \
               and id_key not in used_keys:
                json_ld_facets.append(facet)
                used_keys.append(id_key)
        # now add facet for projects
        for id_key, facet in pre_sort_facets.items():
            if '#facet-project' in id_key \
               and id_key not in used_keys:
                json_ld_facets.append(facet)
                used_keys.append(id_key)
        # now add facet for root linked data
        if '#facet-prop-ld' in pre_sort_facets \
           and '#facet-prop-ld' not in used_keys:
                json_ld_facets.append(pre_sort_facets['#facet-prop-ld'])
                used_keys.append('#facet-prop-ld')
        # now add facet for root properties
        if '#facet-prop-var' in pre_sort_facets \
           and '#facet-prop-var' not in used_keys:
                json_ld_facets.append(pre_sort_facets['#facet-prop-var'])
                used_keys.append('#facet-prop-var')
        for id_key in used_keys:
            # delete all the used facets by key
            pre_sort_facets.pop(id_key, None)
        for id_key, facet in pre_sort_facets.items():
            # add remaining (unsorted) facets
            json_ld_facets.append(facet)
        return json_ld_facets

    def get_facet_meta(self, solr_facet_key):
        facet = LastUpdatedOrderedDict()
        # facet['solr'] = solr_facet_key
        id_prefix = '#' + solr_facet_key
        if '___project_id' in solr_facet_key:
            id_prefix = '#facet-project'
            ftype = 'oc-api:facet-project'
        elif '___context_id' in solr_facet_key:
            id_prefix = '#facet-context'
            ftype = 'oc-api:facet-context'
        elif '___pred_' in solr_facet_key:
            id_prefix = '#facet-prop'
            ftype = 'oc-api:facet-prop'
        elif 'item_type' in solr_facet_key:
            id_prefix = '#facet-item-type'
            ftype = 'oc-api:item-type'
        if solr_facet_key == SolrDocument.ROOT_CONTEXT_SOLR:
            facet['id'] = id_prefix
            facet['rdfs:isDefinedBy'] = 'oc-api:facet-context'
            facet['label'] = 'Context'
            facet['data-type'] = 'id'
        if solr_facet_key == SolrDocument.ROOT_PROJECT_SOLR:
            facet['id'] = id_prefix
            facet['rdfs:isDefinedBy'] = 'oc-api:facet-project'
            facet['label'] = 'Project'
            facet['data-type'] = 'id'
        elif solr_facet_key == SolrDocument.ROOT_LINK_DATA_SOLR:
            facet['id'] = id_prefix + '-ld'
            facet['rdfs:isDefinedBy'] = 'oc-api:facet-prop-ld'
            facet['label'] = 'Linked Data (Common Standards)'
            facet['data-type'] = 'id'
        elif solr_facet_key == SolrDocument.ROOT_PREDICATE_SOLR:
            facet['id'] = id_prefix + '-var'
            facet['rdfs:isDefinedBy'] = 'oc-api:facet-prop-var'
            facet['label'] = 'Descriptive Properties (Project Defined)'
            facet['data-type'] = 'id'
        elif solr_facet_key == 'item_type':
            facet['id'] = id_prefix
            facet['rdfs:isDefinedBy'] = 'oc-api:facet-item-type'
            facet['label'] = 'Open Context Type'
            facet['data-type'] = 'id'
        else:
            # ------------------------
            # Facet is not at the root
            # ------------------------
            facet['id'] = id_prefix
            facet['label'] = ''
            facet_key_list = solr_facet_key.split('___')
            fdtype_list = facet_key_list[1].split('_')
            fsuffix_list = facet_key_list[-1].split('_')
            slug = facet_key_list[0].replace('_', '-')
            entity = self.get_entity(slug)
            if entity is not False:
                facet['id'] = id_prefix + '-' + entity.slug
                facet['rdfs:isDefinedBy'] = entity.uri
                facet['label'] = entity.label
            facet['data-type'] = fsuffix_list[-1]
        facet['type'] = ftype
        return facet

    def make_facet_value_obj(self,
                             solr_facet_key,
                             solr_facet_value_key,
                             solr_facet_count):
        """ Makes an last-ordered-dict for a facet """
        facet_key_list = solr_facet_value_key.split('___')
        if len(facet_key_list) == 4:
            # ----------------------------
            # Case where facet values are encoded as:
            # slug___data-type___/uri-item-type/uuid___label
            # ----------------------------
            data_type = facet_key_list[1]
            if 'http://' in facet_key_list[2] or 'https://' in facet_key_list[2]:
                is_linked_data = True
            else:
                is_linked_data = False
            fl = FilterLinks()
            fl.base_request_json = self.request_dict_json
            fl.base_r_full_path = self.request_full_path
            fl.spatial_context = self.spatial_context
            fl.partial_param_val_match = is_linked_data  # allow partial matches of parameters.
            output = LastUpdatedOrderedDict()
            slug = facet_key_list[0]
            new_rparams = fl.add_to_request_by_solr_field(solr_facet_key,
                                                          slug)
            output['id'] = fl.make_request_url(new_rparams)
            output['json'] = fl.make_request_url(new_rparams, '.json')
            if is_linked_data:
                output['rdfs:isDefinedBy'] = facet_key_list[2]
            else:
                output['rdfs:isDefinedBy'] = settings.CANONICAL_HOST + facet_key_list[2]
            output['label'] = facet_key_list[3]
            output['count'] = solr_facet_count
            output['slug'] = slug
            output['data-type'] = data_type
        else:
            # ----------------------------
            # Sepcilized cases of non-encoded facet values
            # ----------------------------
            output = self.make_specialized_facet_value_obj(solr_facet_key,
                                                           solr_facet_value_key,
                                                           solr_facet_count)
        return output

    def make_specialized_facet_value_obj(self,
                                         solr_facet_key,
                                         solr_facet_value_key,
                                         solr_facet_count):
        """ makes a facet_value obj for specialzied solr faccets """
        fl = FilterLinks()
        fl.base_request_json = self.request_dict_json
        fl.base_r_full_path = self.request_full_path
        fl.spatial_context = self.spatial_context
        new_rparams = fl.add_to_request_by_solr_field(solr_facet_key,
                                                      solr_facet_value_key)
        output = LastUpdatedOrderedDict()
        output['id'] = fl.make_request_url(new_rparams)
        output['json'] = fl.make_request_url(new_rparams, '.json')
        output['label'] = False
        if solr_facet_key == 'item_type':
            if solr_facet_value_key in QueryMaker.TYPE_URIS:
                output['rdfs:isDefinedBy'] = QueryMaker.TYPE_URIS[solr_facet_value_key]
                entity = self.get_entity(output['rdfs:isDefinedBy'])
                if entity is not False:
                    output['label'] = entity.label
        output['count'] = solr_facet_count
        output['slug'] = solr_facet_value_key
        output['data-type'] = 'id'
        return output

    def get_path_in_dict(self, key_path_list, dict_obj, default=False):
        """ get part of a dictionary object by a list of keys """
        act_dict_obj = dict_obj
        for key in key_path_list:
            if isinstance(act_dict_obj, dict): 
                if key in act_dict_obj:
                    act_dict_obj = act_dict_obj[key]
                    output = act_dict_obj
                else:
                    output = default
                    break
            else:
                output = default
                break
        return output
