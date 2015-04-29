#!/usr/bin/env python

import json
import os
import subprocess
import sys
import urllib2

import yaml

sys.path.append('/nail/sys/srv-deploy/lib/')

SWAGGER_YAML_PATH = '/nail/srv/configs/swagger.yaml'

# TODO This will fail in case of system restart
NGINX_RELOAD_COMMAND = ['nginx', '-s', 'reload']

NGINX_CONF_PATH = '/usr/local/nginx/conf/nginx.conf'

NGINX_CONF_HEADER = '''
daemon off;
worker_processes  1;
events {
    worker_connections  1024;
}
http {
    include       mime.types;
    default_type  application/octet-stream;

    server {
        listen       80;
        server_name  localhost;

        location /internalapi/ {
            subs_filter_types application/json;
            subs_filter "\\"basePath\\": \\"[^\\"]*\\"" "\\"basePath\\": \\"http://localhost/internalapi\\"" r;
            rewrite  ^/internalapi/(.*)  /$1 break;
            proxy_set_header Host internalapi;
            proxy_set_header X-Source-ID billings;
            proxy_pass http://web1-uswest1cdevc:9077;
        }
'''  # noqa

NGINX_CONF_FOOTER = '''
        # redirect server error pages to the static page /50x.html
        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   /build/dist;
        }

        location / {
            root   /build/dist;
            index  index.html index.htm api-docs.json;
        }
    }
}
'''

API_DOCS_PATH = '/nail/home/billings/nginx/html/services/api-docs.json'

BLACKLIST = []


def main():
    # Step 1a: Find all official services
    swagger_services = {}
    for root, dirs, files in os.walk("/nail/etc/services"):
        for file_ in files:
            try:
                if file_ != 'smartstack.yaml':
                    continue
                path = os.path.join(root, file_)
                service = root.split('/')[-1]
                with open(path) as fd:
                    smartstack = yaml.load(fd)
                port = int(smartstack['main']['proxy_port'])
                mode = smartstack['main'].get('mode')
                if mode == 'tcp':
                    continue
                swagger_services[service] = {
                    'host': os.getenv('DOCKERHOST', '127.0.0.1'),
                    'port': port,
                }
            except:
                pass

    # Step 1b: Find all developer swagger services
    with open(SWAGGER_YAML_PATH) as fd:
        yaml_data = yaml.load(fd)
        if yaml_data is not None:
            swagger_services.update(yaml_data)

    # Step 1c: Filter out any services that aren't responding on the '/swagger'
    # endpoint.
    def healthy_new(service):
        try:
            url = 'http://%s:%d/api-docs' % (service['host'], service['port'])
            urllib2.urlopen(url, timeout=2)
            return True
        except:
            return False

    new_swagger_services = (dict(
        (k, v) for (k, v) in swagger_services.iteritems() if healthy_new(
            v) and not (k in BLACKLIST or k.startswith('lucy'))))

    # Step 2: Write out our nginx configuration
    with open(NGINX_CONF_PATH, 'w') as fd:
        print >>fd, NGINX_CONF_HEADER

        for service in sorted(new_swagger_services):
            host = swagger_services[service]['host']
            port = swagger_services[service]['port']

            print >>fd, "        location /%s/ {" % service
            # Set basePath to be http://localhost/service_name
            print >>fd, "            subs_filter_types application/json;"
            print >>fd, '            subs_filter "\\"basePath\\": \\"[^\\"]*\\"" "\\"basePath\\": \\"http://localhost/%s\\"" r;' % service  # noqa
            # /service_name/foo -> /foo
            print >>fd, "            rewrite  ^/%s/(.*)  /$1 break;" % service
            print >>fd, "            proxy_set_header Host $http_host;"
            print >>fd, "            proxy_pass http://%s:%d;" % (host, port)
            print >>fd, "        }\n"

        print >>fd, NGINX_CONF_FOOTER

    services = [{'name': 'internalapi', 'path': '/internalapi/api-docs'}]
    for service in sorted(new_swagger_services):
        services.append(
            {'name': service,
             'path': "/%s/api-docs" % service})
    with open('/build/dist/services.json', 'w') as fd:
        json.dump(services, fd, indent=4, separators=(',', ': '))

    # Step 4: Reload nginx
    subprocess.check_call(NGINX_RELOAD_COMMAND)


if __name__ == '__main__':
    main()
