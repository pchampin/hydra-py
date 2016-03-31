from httplib2 import Http, HttpLib2ErrorWithResponse
import json
import logging
from rdflib import BNode, ConjunctiveGraph, Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD
from rdflib.resource import Resource as RdflibResource
from rdflib.parser import StringInputSource
from rdflib.plugin import register, Parser, Serializer
from re import compile as regex
from uritemplate import expand
from warnings import warn

register('application/ld+json', Parser, 'rdflib_jsonld.parser', 'JsonLDParser')
register('application/ld+json', Serializer, 'rdflib_jsonld.serializer', 'JsonLDSerializer')
LOG = logging.getLogger(__name__)



__version__ = "0.1"



HYDRA = Namespace('http://www.w3.org/ns/hydra/core#')
SCHEMA = Namespace('http://schema.org/')

class NullLiteral(object):
    def toPython(self):
        return None
NULL = NullLiteral()

# the following is useful in classes that define an attribute named 'property'
_py_property = property


class Resource(RdflibResource):

    @classmethod
    def from_iri(cls, iri, headers=None, http=None):
        ret = cls(None, URIRef(iri))
        del ret._graph # graph will be lazily loaded (see property _graph below)
        ret._headers = headers
        ret._http = http
        return ret

    @classmethod
    def from_peer(cls, identifier, resource, headers=None, http=None):
        """
        I build an instance of this class for one of its peer resources.

        If identifier is a BNode or has the same base IRI as resource,
        then I reuse resource's graph instead of downloading it.

        I also reuse resource's graph if it contains at least one out-goind triple with identifier as subject.
        This is a (somewhat daring) heuristic,
        but is required in many cases where a class or a property is described directly in the API Documentation.
        """
        if type(identifier) is BNode \
        or resource.identifier.split('#', 1)[0] == identifier.split('#', 1)[0] \
        or (identifier, None, None) in resource.graph:
            return cls(resource.graph, identifier)
        else:
            return cls.from_iri(identifier, headers, http)


    @property
    def _graph(self):
        """Lazy loading of the _graph attribute

        This property getter will be called only when the instance attribute self._graph has been deleted.
        In that case, it will load the graph from self.identifier.

        This is used by the `from_iri`:meth: class method,
        to ensure that graphs are only loaded when required...
        """
        if '_graph' in self.__dict__:
            return self.__dict__['_graph']

        headers = self.__dict__.pop('_headers')
        http = self.__dict__.pop('_http')
        base_iri = self._identifier.split('#', 1)[0]
        effective_headers = dict(DEFAULT_REQUEST_HEADERS)
        if headers:
            effective_headers.update(headers)
        http = http or DEFAULT_HTTP_CLIENT

        LOG.info('downloading <%s>', base_iri)
        response, content = http.request(base_iri, "GET", headers=effective_headers)
        LOG.debug('got %s %s %s', response.status, response['content-type'], response.fromcache)
        if response.status // 100 != 2:
            raise HttpLib2ErrorWithResponse(response.reason, response, content)

        source = StringInputSource(content)
        ctype = response['content-type'].split(';',1)[0]
        g = ConjunctiveGraph(identifier=base_iri)
        g.addN(BACKGROUND_KNOWLEDGE.quads())
        g.parse(source, base_iri, ctype)
        _fix_default_graph(g)

        # if available, load API Documentation in a separate graph
        links = response.get('link')
        if links:
            if type(links) != list:
                links = [links]
            for link in links:
                match = APIDOC_RE.match(link)
                if match:
                    self._api_doc = apidoc_iri = URIRef(match.groups()[0])
                    if apidoc_iri != self.identifier:
                        apidoc = ApiDocumentation.from_iri(apidoc_iri, headers, http)
                        g.addN(apidoc.graph.quads())
                    break

        self.__dict__['_graph'] = g
        return g
    @_graph.setter
    def _graph(self, value):
        """Ensures that the instance attribute self._graph can still be set."""
        self.__dict__['_graph'] = value
    @_graph.deleter
    def _graph(self):
        """Ensures that the instance attribute self._graph can still be deleted."""
        del self.__dict__['_graph']



    def get_api_documentation(self):
        graph = self._graph # ensures that graph is loaded
        if self._api_doc:
            return ApiDocumentation(graph, self._api_doc)
        else:
            return None
    api_documentation = property(get_api_documentation)
    _api_doc = None

    def get_title(self):
        return self.graph \
            .value(self.identifier, HYDRA.title, default=NULL).toPython()
    title = property(get_title)

    def get_description(self):
        return self.graph \
            .value(self.identifier, HYDRA.description, default=NULL).toPython()
    description = property(get_description)

    def iter_types(self):
        return self.graph.objects(self.identifier, RDF.type)
    types = property(iter_types)

    def iter_operations(self, headers=None, http=None):
        self_identifier = self.identifier
        for obj in self.graph.objects(self.identifier, HYDRA.operation):
            yield Operation.from_peer(obj, self, headers, http).bound(self_identifier)
    operations = property(iter_operations)

    def iter_all_operations(self, headers=None, http=None):
        for op in self.iter_operations(headers, http):
            yield op

        graph = self.graph
        identifier = self.identifier

        for op in graph.objects(identifier, TYPE_OP):
            yield Operation.from_peer(op, self).bound(identifier)

        for prop, target in graph.predicate_objects (identifier):
            for op in graph.objects(prop, LINK_OP):
                yield Operation.from_peer(op, self).bound(target)
            for op in graph.objects(prop, RANGE_OP):
                yield Operation.from_peer(op, self).bound(target)

    all_operations = property(iter_all_operations)

    def iter_suitable_operations(self, operation_type=None,
                                 input_type=None, output_type=None,
                                 headers=None, http=None):
        for op in self.iter_all_operations(headers, http):
            if op.is_suitable_for(operation_type, input_type, output_type):
                yield op

    def find_suitable_operation(self, operation_type=None,
                                input_type=None, output_type=None,
                                headers=None, http=None):
        for op in self.iter_suitable_operations(operation_type, input_type, output_type, headers, http):
            return op
        return None

    def iter_iri_templates(self, templated_link=HYDRA.search, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, templated_link):
            yield IriTemplate.from_peer(obj, self, headers, http)
    iri_templates = property(iter_iri_templates)

    def iter_suitable_template(self, properties, templated_link=HYDRA.search, headers=None, http=None):
        graph = self.graph
        for iri_template in self.iter_iri_templates(templated_link, headers, http):
            if iri_template.is_suitable_for(properties):
                yield iri_template

    def find_suitable_template(self, properties, templated_link=HYDRA.search, headers=None, http=None):
        for iri_template in self.iter_suitable_template(properties, templated_link, headers, http):
            return iri_template
        return None

    def freetext_query(self, query, templated_link=HYDRA.search, headers=None, http=None):
        fulltext_search_template = self.find_suitable_template([HYDRA.freetextQuery], templated_link, headers, http)
        result_iri = fulltext_search_template.generate_iri({HYDRA.freetextQuery: query})
        return Collection.from_iri(result_iri, headers, http)



class ApiDocumentation(Resource):

    def iter_supported_classes(self, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, HYDRA.supportedClass):
            yield Class.from_peer(obj, self, headers, http)
    supported_classes = property(iter_supported_classes)

    def iter_possible_status(self, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, HYDRA.possibleStatus):
            yield Status.from_peer(obj, self, headers, http)
    possible_status = property(iter_possible_status)

    def get_entrypoint(self, headers=None, http=None):
        uri = self.graph.value(self.identifier, HYDRA.entrypoint)
        if uri is None:
            return None
        else:
            return Resource.from_peer(uri, self, headers, None)
    entrypoint = property(get_entrypoint)



class Class(Resource):

    def iter_supported_properties(self, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, HYDRA.supportedProperty):
            yield SupportedProperty.from_peer(obj, self, headers, http)
    supported_properties = property(iter_supported_properties)

    def iter_supported_operations(self, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, HYDRA.supportedOperation):
            yield Operation.from_peer(obj, self, headers, http)
    supported_operations = property(iter_supported_operations)


class Status(Resource):

    def get_status_code(self):
        return self.graph \
            .value(self.identifier, HYDRA.statusCode, NULL).toPython()
    status_code = property(get_status_code)


class Operation(Resource):

    def get_method(self):
        return self.graph \
            .value(self.identifier, HYDRA.method, default=NULL).toPython()
    method = property(get_method)

    def get_expected_class(self, headers=None, http=None):
        uri = self.graph.value(self.identifier, HYDRA.expects)
        if uri is None:
            return None
        else:
            return Class.from_peer(uri, self, headers, http)
    expected_class = property(get_expected_class)

    def get_returned_class(self, headers=None, http=None):
        uri = self.graph.value(self.identifier, HYDRA.returns)
        if uri is None:
            return None
        else:
            return Class.from_peer(uri, self, headers, http)
    returned_class = property(get_returned_class)

    def iter_possible_status(self, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, HYDRA.possibleStatus):
            yield Status.from_peer(obj, self, headers, http)
    possible_status = property(iter_possible_status)

    def is_suitable_for(self, operation_type=None, input_type=None, output_type=None):
        if operation_type is not None:
            if (self.identifier, TYPE, operation_type) not in self.graph:
                return False
        if input_type is not None:
            if self.expected_class is None \
            or (input_type, SUBCLASS, self.expected_class.identifier) not in self.graph:
                return False
        if output_type is not None:
            if self.returned_class is None \
            or (self.returned_class.identifier, SUBCLASS, output_type) not in self.graph:
                return False
        return True

    def bound(self, target_iri):
        return BoundOperation(self, target_iri)


class BoundOperation(Operation):

    def __init__(self, unbound, target_iri):
        Operation.__init__(self, unbound.graph, unbound.identifier)
        self.target_iri = target_iri

    def _new(self, identifier):
        """Required as __init__ breaks compatibility with superclass"""
        return Resource(self._graph, identifier)

    def perform(self, body=None, headers=None, http=None):
        LOG.debug("perform: %s <%s>", self.method, self.target_iri)
        effective_headers = dict(DEFAULT_REQUEST_HEADERS)
        if headers:
            effective_headers.update(headers)
        http = http or DEFAULT_HTTP_CLIENT

        if type(body) is dict:
            body = json.dumps(body)
            effective_headers['content-type'] = 'application/ld+json'
        elif isinstance(body, Graph):
            ctype = effective_headers.setdefault('content-type', 'application/ld+json')
            body = body.serialize(format=ctype)

        return http.request(unicode(self.target_iri),
                            self.method,
                            body,
                            effective_headers)
        # TODO should we provide a higher abstraction level for perform()

    def __call__(self, *args, **kw):
        return self.perform(*args, **kw)


class SupportedProperty(Resource):

    def get_property(self, headers=None, http=None):
        prop = self.graph.value(self.identifier, HYDRA.property)
        if prop is not None:
            return Property.from_peer(prop, self, headers, http)
        else:
            return None
    property = _py_property(get_property)

    def get_required(self):
        return self.graph \
            .value(self.identifier, HYDRA.required, default=NULL).toPython()
    required = _py_property(get_required)

    def get_readable(self):
        return self.graph \
            .value(self.identifier, HYDRA.readable, default=NULL).toPython()
    readable = _py_property(get_readable)

    def get_writeable(self):
        return self.graph \
            .value(self.identifier, HYDRA.writeable, default=NULL).toPython()
    writeable = _py_property(get_writeable)

    # those seem to be deprecated from the spec, but are still used in the spec

    def get_readonly(self):
        return self.graph \
            .value(self.identifier, HYDRA.readonly, default=NULL).toPython()
    readonly = _py_property(get_readonly)

    def get_writeonly(self):
        return self.graph \
            .value(self.identifier, HYDRA.writeonly, default=NULL).toPython()
    writeonly = _py_property(get_writeonly)


class Property(Resource):

    def is_link(self):
        the_triple = (self.identifier, RDF.type, HYDRA.Link)
        return (the_triple in self.graph)
    link = property(is_link)

    def iter_supported_operations(self, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, HYDRA.supportedOperation):
            yield Operation.from_peer(obj, self, headers, http)
    supported_operations = property(iter_supported_operations)


class Collection(Resource):

    def get_total_items(self):
        return self.graph \
            .value(self.identifier, HYDRA.totalItems, default=NULL).toPython()
    total_items = _py_property(get_total_items)

    def iter_members(self, member_class=Resource, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, HYDRA.member):
            yield member_class.from_peer(obj, self, headers, http)
    members = property(iter_members)

    def is_paged(self):
        the_triple = (self.identifier, RDF.type, HYDRA.PagedCollection)
        return (the_triple in self.graph)
    paged = property(is_paged)

    def get_items_per_page(self):
        return self.graph \
            .value(self.identifier, HYDRA.itemsPerPage, default=NULL).toPython()
    items_per_page = _py_property(get_items_per_page)

    def get_first_page(self, headers=None, http=None):
        warn("get_first_page/first_page is deprecated; "
             "use get_first/first instead", stacklevel=2)
        obj = self.graph.value(self.identifier, HYDRA.firstPage)
        if obj:
            return Collection.from_iri(obj, headers, http)
        else:
            return None
    first_page = _py_property(get_first_page)

    def get_first(self, headers=None, http=None):
        obj = self.graph.value(self.identifier, HYDRA.first)
        if obj:
            return Collection.from_iri(obj, headers, http)
        else:
            return None
    first = _py_property(get_first)

    def get_last_page(self, headers=None, http=None):
        warn("get_last_page/last_page is deprecated; "
             "use get_last/last instead", stacklevel=2)
        obj = self.graph.value(self.identifier, HYDRA.lastPage)
        if obj:
            return Collection.from_iri(obj, headers, http)
        else:
            return None
    last_page = _py_property(get_last_page)

    def get_last(self, headers=None, http=None):
        obj = self.graph.value(self.identifier, HYDRA.last)
        if obj:
            return Collection.from_iri(obj, headers, http)
        else:
            return None
    last = _py_property(get_last)

    def get_next_page(self, headers=None, http=None):
        warn("get_next_page/next_page is deprecated; "
             "use get_next/next instead", stacklevel=2)
        obj = self.graph.value(self.identifier, HYDRA.nextPage)
        if obj:
            return Collection.from_iri(obj, headers, http)
        else:
            return None
    next_page = _py_property(get_next_page)

    def get_next(self, headers=None, http=None):
        obj = self.graph.value(self.identifier, HYDRA.next)
        if obj:
            return Collection.from_iri(obj, headers, http)
        else:
            return None
    next = _py_property(get_next)

    def get_previous_page(self, headers=None, http=None):
        warn("get_previous_page/previous_page is deprecated; "
             "use get_previous/previous instead", stacklevel=2)
        obj = self.graph.value(self.identifier, HYDRA.previousPage)
        if obj:
            return Collection.from_iri(obj, headers, http)
        else:
            return None
    previous_page = _py_property(get_previous_page)

    def get_previous(self, headers=None, http=None):
        obj = self.graph.value(self.identifier, HYDRA.previous)
        if obj:
            return Collection.from_iri(obj, headers, http)
        else:
            return None
    previous = _py_property(get_previous)

    def iter_pages(self):
        i = self
        while i is not None:
            yield i
            i = i.next
    pages = property(iter_pages)



class IriTemplate(Resource):

    def get_template(self):
        return self.graph \
            .value(self.identifier, HYDRA.template, default=NULL).toPython()
    template = property(get_template)

    def get_template_type(self):
        lit = self.graph.value(self.identifier, HYDRA.template)
        if lit is None  or  lit.datatype == XSD.String:
                return HYDRA.Rfc6570Template
        else:
            return lit.datatype
    template_type = property(get_template_type)

    def iter_mappings(self, headers=None, http=None):
        for obj in self.graph.objects(self.identifier, HYDRA.mapping):
            yield IriTemplateMapping.from_peer(obj, self, headers, http)
    mappings = property(iter_mappings)

    def get_variable_representation(self, default=HYDRA.BasicRepresentation):
        return self.graph \
            .value(self.identifier, HYDRA.variableRepresentation, default=HYDRA.BasicRepresentation)
    variable_representation = property(get_variable_representation)

    def is_suitable_for(self, properties):
        graph = self.graph
        values = { URIRef(prop): 1 for prop in properties }
        map, _ = self._map_properties(values)
        return (map is not None)

    def generate_iri(self, values, default_representation=HYDRA.BasicRepresentation):
        """
        Generate an IRI according to this template.

        This method takes care of formatting the provided values according to the template's variableRepresentation.

        :param values: a dict whose keys are properties, and values are RDF terms
        :return: the IRI as a string

        NB: if required properties are missing from `values`, a ValueError is raised.
        """
        # ensure that keys are URIRefs in values
        graph = self.graph
        values = { URIRef(key):value for key, value in values.items() }
        representation = self.get_variable_representation(default=default_representation)
        mode = 0 if representation is HYDRA.BasicRepresentation else 1
        data, msg = self._map_properties(values)
        if data is None:
            raise ValueError(msg)
        data = { key: _format_variable(value, mode)
                 for key, value in data.items() }
        return expand(self.template, data)

    def _map_properties(self, values):
        graph = self.graph
        data = {}
        for mapping in self.mappings:
            for prop, value in values.iteritems():
                if (prop, SUBPROP, mapping.property) in graph:
                    values.pop(prop)
                    if value is not None:
                        data[mapping.variable] = value
                    break
            else: # for-else: we didn't break out of the loop
                if mapping.required:
                    return None, "Required property <%s> is missing" % property
        if values:
            return None, "Service does not support properties %s" % values.keys()
        return data, None



def _format_variable(term, mode):
    if mode == 0: # Basic
        return unicode(term)
    else: # explicit
        if type(term) is Literal:
            ret = u'"%s"' % term
            if term.datatype and term.datatype != XSD.String:
                ret = u'%s^^%s' % (ret, term.datatype)
            elif term.language:
                ret = u'%s@%s' % (ret, term.language)
            return ret.encode('utf-8')
        else:
            return unicode(term).encode('utf-8')


class IriTemplateMapping(Resource):

    def get_variable(self):
        return self.graph \
            .value(self.identifier, HYDRA.variable, default=NULL).toPython()
    variable = _py_property(get_variable)

    def get_property(self):
        return self.graph \
            .value(self.identifier, HYDRA.property)
    property = _py_property(get_property)

    def get_required(self):
        return self.graph \
            .value(self.identifier, HYDRA.required, default=NULL).toPython()
    required = _py_property(get_required)




def _fix_default_graph(cg):
    """
    Find the *real* default graph of a ConjunctiveGraph.

    This is a workaround required by a bug in the JSON-LD parser.
    """
    if len(cg.default_context) > 0:
        if len(list(cg.contexts())) > 1:
            LOG.warn("It seems that _fix_default_graph is not needed anymore...")
        return cg.default_context
    for g in cg.contexts():
        if type(g.identifier) is BNode:
            cg.default_context = g

class _MemCache(dict):

    def __nonzero__(self):
        # even if empty, a _MemCache is True
        return True

    def set(self, key, value):
        self[key] = value

    def delete(self, key):
        if key in self:
            del self[key]

DEFAULT_HTTP_CLIENT = Http(_MemCache())
DEFAULT_REQUEST_HEADERS =  {
    # NB: the spaces and line-breaks in 'accept' below are a hack
    #     to work around a problem in httplib2:
    #     the cache does not work with arbibtrary long lines
    "accept": "application/ld+json, application/n-quads;q=0.9,\r\n application/turtle;q=0.8, application/n-triples;q=0.7,\r\n application/rdf+xml;q=0.6, text/html;q=0.5, */*;q=0.1",
    "user-agent": "hydra-py-v" + __version__,
}

BACKGROUND_KNOWLEDGE = ConjunctiveGraph(identifier=URIRef("urn:x-hydra-py:background-knowledge"))

SUBCLASS = RDFS.subClassOf * "*"
SUBPROP = RDFS.subPropertyOf * "*"
LINK_OP = SUBPROP / HYDRA.supportedOperation
RANGE = RDFS.range / SUBCLASS
RANGE_OP = RANGE / HYDRA.supportedOperation
TYPE = RDF.type / SUBCLASS
TYPE_OP = TYPE / HYDRA.supportedOperation

APIDOC_RE = regex(r'^<([^>]*)>; rel="http://www.w3.org/ns/hydra/core#apiDocumentation"$')
