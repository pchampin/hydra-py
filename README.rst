Hydra library for Python
========================

The primary goal is to provide a lib for easily writing Hydra-enabled clients [1].

A secondary goal is to provide a client for Triple Patterns Fragments [2],
and an RDFlib [3] Store backed on any TPF service.

[1] http://www.hydra-cg.com/
[2] http://www.hydra-cg.com/spec/latest/triple-pattern-fragments/
[3] https://rdflib.readthedocs.org/

Installation
++++++++++++

To install this library, from the projet directory, type::

    pip install .

NB: developers might want to add the ``-e`` option to the command line above,
so that modifications to the source are automatically taken into account.

Quick start
+++++++++++

To create a Hydra-enabled resource, use:

.. code:: python

    from hydra import Resource, SCHEMA
    res = Resource.from_iri(the_iri_of_the_resource)

If the resource has an API documentation associated with it,
it will be available as an attribute.
The API documentation provides access to the supported class,
their supported properties and operations.

.. code:: python

    print("Api documentation:")
    for supcls in res.api_documentation.supported_classes:
        print("  %s" % supcls.identifier)
        for supop in supcls.supported_operations:
            print("    %s" % supop.identifier)

Alternatively,
you can query the resource directly for available operations.
For example, the following searches for a suitable operation for creating a new event,
and performs it.

.. code:: python

    create_event = res.find_suitable_operation(SCHEMA.AddAction, SCHEMA.Event)
    resp, body = create_event({
        "@context": "http://schema.org/",
        "@type": "http://schema.org/Event",
        "name": "Halloween",
        "description": "This is halloween, this is halloween",
        "startDate": "2015-10-31T00:00:00Z",
        "endDate": "2015-10-31T23:59:59Z",
    })
    assert resp.status == 201, "%s %s" % (resp.status, resp.reason)
    new_event = Resource.from_iri(resp['location'])

And you can go on with the new event you just created...