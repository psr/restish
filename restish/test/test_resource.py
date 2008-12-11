"""
Test resource behaviour.
"""

import unittest

from restish import app, http, resource
from restish.test.util import wsgi_out


class TestResource(unittest.TestCase):

    def test_no_method_handler(self):
        res = resource.Resource()
        environ = http.Request.blank('/').environ
        response = res(http.Request(environ))
        assert response.status.startswith("405")

    def test_methods(self):
        class Resource(resource.Resource):
            @resource.GET()
            def GET(self, request):
                return http.ok([], 'GET')
            @resource.POST()
            def POST(self, request):
                return http.ok([], 'POST')
            @resource.PUT()
            def PUT(self, request):
                return http.ok([], 'PUT')
            @resource.DELETE()
            def DELETE(self, request):
                return http.ok([], 'DELETE')
        for method in ['GET', 'POST', 'PUT', 'DELETE']:
            print "*", method
            environ = http.Request.blank('/',
                    environ={'REQUEST_METHOD': method},
                    headers={'Accept': 'text/html'}).environ
            response = Resource()(http.Request(environ))
            print response.status, response.body
            assert response.status == "200 OK"
            assert response.body == method


class TestChildLookup(unittest.TestCase):

    def test_404(self):
        class Resource(resource.Resource):
            pass
        A = app.RestishApp(Resource())
        R = wsgi_out(A, http.Request.blank('/404').environ)
        assert R['status'].startswith('404')

    def test_implicitly_named(self):
        class Resource(resource.Resource):
            def __init__(self, segments=[]):
                self.segments = segments
            @resource.child()
            def implicitly_named_child(self, request, segments):
                return self.__class__(self.segments + ['implicitly_named_child'])
            def __call__(self, request):
                return http.ok([('Content-Type', 'text/plain')], '/'.join(self.segments))
        A = app.RestishApp(Resource())
        R = wsgi_out(A, http.Request.blank('/implicitly_named_child').environ)
        assert R['status'].startswith('200')
        assert R['body'] == 'implicitly_named_child'

    def test_explicitly_named(self):
        class Resource(resource.Resource):
            def __init__(self, segments=[]):
                self.segments = segments
            @resource.child('explicitly_named_child')
            def find_me_a_child(self, request, segments):
                return self.__class__(self.segments + ['explicitly_named_child'])
            def __call__(self, request):
                return http.ok([('Content-Type', 'text/plain')], '/'.join(self.segments))
        A = app.RestishApp(Resource())
        R = wsgi_out(A, http.Request.blank('/explicitly_named_child').environ)
        assert R['status'].startswith('200')
        assert R['body'] == 'explicitly_named_child'

    def test_segment_consumption(self):
        class Resource(resource.Resource):
            def __init__(self, segments=[]):
                self.segments = segments
            @resource.child()
            def first(self, request, segments):
                return self.__class__(self.segments + ['first'] + segments), []
            def __call__(self, request):
                return http.ok([('Content-Type', 'text/plain')], '/'.join(self.segments))
        A = app.RestishApp(Resource())
        R = wsgi_out(A, http.Request.blank('/first').environ)
        assert R['status'].startswith('200')
        assert R['body'] == 'first'
        R = wsgi_out(A, http.Request.blank('/first/second').environ)
        assert R['status'].startswith('200')
        assert R['body'] == 'first/second'
        R = wsgi_out(A, http.Request.blank('/first/a/b/c/d/e').environ)
        assert R['status'].startswith('200')
        assert R['body'] == 'first/a/b/c/d/e'


class TestContentNegotiation(unittest.TestCase):

    def test_no_match(self):
        class Resource(resource.Resource):
            @resource.GET(accept='text/json')
            def html(self, request):
                return http.ok([], '<p>Hello!</p>')
        res = Resource()
        environ = http.Request.blank('/', headers={'Accept': 'text/plain'}).environ
        response = res(http.Request(environ))
        print response.status
        assert response.status.startswith("406")

    def test_implicit_content_type(self):
        """
        Test that the content type is added automatically.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='text/html')
            def html(self, request):
                return http.ok([], '<p>Hello!</p>')
        res = Resource()
        environ = http.Request.blank('/').environ
        response = res(http.Request(environ))
        assert response.headers['Content-Type'] == 'text/html'

    def test_implicit_content_type_not_on_partial_mimetype(self):
        """
        Test that a match on mime type group, e.g. */*, text/*, etc does not
        automatically add the content type.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='text/*')
            def html(self, request):
                return http.ok([], '<p>Hello!</p>')
        res = Resource()
        environ = http.Request.blank('/').environ
        response = res(http.Request(environ))
        print response.headers.get('Content-Type')
        assert response.headers.get('Content-Type') is None

    def test_explicit_content_type(self):
        """
        Test that the content type is not added automatically if the resource
        sets it.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='text/html')
            def html(self, request):
                return http.ok([('Content-Type', 'text/plain')], '<p>Hello!</p>')
        res = Resource()
        environ = http.Request.blank('/').environ
        response = res(http.Request(environ))
        assert response.headers['Content-Type'] == 'text/plain'

    def test_no_accept(self):
        """
        Test generic GET matches request from client that does not send an
        Accept header.
        """
        class Resource(resource.Resource):
            @resource.GET()
            def html(self, request):
                return http.ok([('Content-Type', 'text/html')], "<html />")
        res = Resource()
        environ = http.Request.blank('/').environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/html'

    def test_accept_match(self):
        """
        Test that an accept'ing request is matched even if there's a generic
        handler.
        """
        class Resource(resource.Resource):
            @resource.GET()
            def html(self, request):
                return http.ok([('Content-Type', 'text/html')], "<html />")
            @resource.GET(accept='application/json')
            def json(self, request):
                return http.ok([('Content-Type', 'application/json')], "{}")
        res = Resource()
        environ = http.Request.blank('/', headers=[('Accept', 'application/json')]).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"

    def test_accept_non_match(self):
        """
        Test that a non-accept'ing request is matched when there's an
        accept-ing handler too.
        """
        class Resource(resource.Resource):
            @resource.GET()
            def html(self, request):
                return http.ok([('Content-Type', 'text/html')], "<html />")
            @resource.GET(accept='application/json')
            def json(self, request):
                return http.ok([('Content-Type', 'application/json')], "{}")
        res = Resource()
        environ = http.Request.blank('/', headers=[('Accept', 'text/html')]).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/html'

    def test_default_match(self):
        """
        Test that a client that does not send an Accept header gets a
        consistent response.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='html')
            def html(self, request):
                return http.ok([], '<p>Hello!</p>')
            @resource.GET(accept='json')
            def json(self, request):
                return http.ok([], '"Hello!"')
        res = Resource()
        environ = http.Request.blank('/').environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/html'

    def test_no_subtype_match(self):
        """
        Test that something/* accept matches are found.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='text/*')
            def html(self, request):
                return http.ok([('Content-Type', 'text/plain')], 'Hello!')
        res = Resource()
        environ = http.Request.blank('/', headers={'Accept': 'text/plain'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/plain'

    def test_quality(self):
        """
        Test that a client's accept quality is honoured.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='text/html')
            def html(self, request):
                return http.ok([('Content-Type', 'text/html')], '<p>Hello!</p>')
            @resource.GET(accept='text/plain')
            def plain(self, request):
                return http.ok([('Content-Type', 'text/plain')], 'Hello!')
        res = Resource()
        environ = http.Request.blank('/', headers={'Accept': 'text/html;q=0.9,text/plain'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/plain'
        environ = http.Request.blank('/', headers={'Accept': 'text/plain,text/html;q=0.9'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/plain'
        environ = http.Request.blank('/', headers={'Accept': 'text/html;q=0.4,text/plain;q=0.5'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/plain'
        environ = http.Request.blank('/', headers={'Accept': 'text/html;q=0.5,text/plain;q=0.4'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/html'

    def test_specificity(self):
        """
        Check that more specific mime types are matched in preference to *
        matches.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='html')
            def bbb(self, request):
                return http.ok([('Content-Type', 'text/html')], '')
            @resource.GET(accept='json')
            def aaa(self, request):
                return http.ok([('Content-Type', 'application/json')], '')
        res = Resource()
        environ = http.Request.blank('/', headers={'Accept': '*/*, application/json, text/javascript'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        print response.headers['Content-Type']
        assert response.headers['Content-Type'] == 'application/json'

    def test_no_subtype_match_2(self):
        """
        Test that something/* accept matches are found, when there's also a
        '*/*' match,
        """
        class Resource(resource.Resource):
            @resource.GET()
            def anything(self, request):
                return http.ok([('Content-Type', 'text/html')], '<p>Hello!</p>')
            @resource.GET(accept='text/*')
            def html(self, request):
                return http.ok([('Content-Type', 'text/plain')], 'Hello!')
        res = Resource()
        environ = http.Request.blank('/', headers={'Accept': 'text/plain'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/plain'


class TestAcceptLists(unittest.TestCase):

    def test_match(self):
        class Resource(resource.Resource):
            @resource.GET(accept=['text/html', 'application/xhtml+xml'])
            def html(self, request):
                return http.ok([], '<html />')
        res = Resource()
        environ = http.Request.blank('/', headers={'Accept': 'text/html'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"
        environ = http.Request.blank('/', headers={'Accept': 'application/xhtml+xml'}).environ
        response = res(http.Request(environ))
        assert response.status == "200 OK"

    def test_auto_content_type(self):
        class Resource(resource.Resource):
            @resource.GET(accept=['text/html', 'application/xhtml+xml'])
            def html(self, request):
                return http.ok([], '<html />')
        # Check specific accept type.
        environ = http.Request.blank('/', headers={'Accept': 'text/html'}).environ
        response = Resource()(http.Request(environ))
        assert response.headers['content-type'] == 'text/html'
        # Check other specific accept type.
        environ = http.Request.blank('/', headers={'Accept': 'application/xhtml+xml'}).environ
        response = Resource()(http.Request(environ))
        assert response.headers['content-type'] == 'application/xhtml+xml'
        # Check the server's first accept match type is used if the client has
        # no strong preference whatever order the accept header lists types.
        environ = http.Request.blank('/', headers={'Accept': 'text/html,application/xhtml+xml'}).environ
        response = Resource()(http.Request(environ))
        assert response.headers['content-type'] == 'text/html'
        environ = http.Request.blank('/', headers={'Accept': 'application/xhtml+xml,text/html'}).environ
        response = Resource()(http.Request(environ))
        assert response.headers['content-type'] == 'text/html'
        # Client accepts both but prefers one.
        environ = http.Request.blank('/', headers={'Accept': 'text/html,application/xhtml+xml;q=0.9'}).environ
        response = Resource()(http.Request(environ))
        assert response.headers['content-type'] == 'text/html'
        # Client accepts both but prefers other.
        environ = http.Request.blank('/', headers={'Accept': 'text/html;q=0.9,application/xhtml+xml'}).environ
        response = Resource()(http.Request(environ))
        assert response.headers['content-type'] == 'application/xhtml+xml'


class TestShortAccepts(unittest.TestCase):

    def test_single(self):
        """
        Check that short types known to Python's mimetypes module are expanded.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='html')
            def html(self, request):
                return http.ok([], "<html />")
        res = Resource()
        environ = http.Request.blank('/', headers=[('Accept', 'text/html')]).environ
        response = res(http.Request(environ))
        print response.status
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'text/html'

    def test_extra(self):
        """
        Check that short types added by restish are expanded.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='json')
            def json(self, request):
                return http.ok([], "{}")
        res = Resource()
        environ = http.Request.blank('/', headers=[('Accept', 'application/json')]).environ
        response = res(http.Request(environ))
        print response.status
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'application/json'

    def test_unknown(self):
        """
        Check that unknown short types are not expanded and are still used.
        """
        class Resource(resource.Resource):
            @resource.GET(accept='unknown')
            def unknown(self, request):
                return http.ok([], "{}")
        res = Resource()
        environ = http.Request.blank('/').environ
        response = res(http.Request(environ))
        print response.status
        assert response.status == "200 OK"
        assert response.headers['Content-Type'] == 'unknown'


if __name__ == '__main__':
    unittest.main()

