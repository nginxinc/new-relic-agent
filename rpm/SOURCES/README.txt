
nginx web server plugin for New Relic
Copyright (C) Nginx, Inc.


1. Preface

Visualize nginx web server performance with this plugin provided
by the original authors of nginx.

Collect and display key load metrics to track your nginx instances behavior.

This plugin was created by the original authors of nginx web server.
It allows to collect and report various important counters from an nginx
web server instance such as:

 * Active client connections
 * Idle (keepalive) client connections
 * Client connections accept rate, drop rate
 * Request rate

NGINX Plus customers will be able to use additional set of metrics
related to upstream monitoring (a number of servers, breakdown by state;
upstream servers connections; bandwidth usage; backend response rate,
breakdown by HTTP status code; healthchecks status), virtual servers
summary stats (requests/responses rate, bandwidth usage), cache zone
stats (responses by cache status, traffic from cache).

Metrics will be charted in the New Relic User Interface and you will be able
to configure alerts based on the values reported by this plugin.

This plugin is distributed under 2-clause BSD-like license.


2. Requirements

In order to use this plugin, you must have an active New Relic account.

Plugin should work on any generic Unix environment with the following
software components installed:

  - Python (2.6, 2.7)
  - python-daemon
  - python-setproctitle (optional)


3. Installation

The best way to install this plugin is to use prebuilt binary packages
(rpm for CentOS/RedHat platforms, deb for Debian/Ubuntu platforms).
In case of preconfigured access to repository, installation should be
as easy as:

    $ yum install nginx-nr-agent

or

    $ apt-get install nginx-nr-agent


4. Configuration

4.1. Opensource nginx configuration

To configure this plugin to work with nginx OSS using ngx_http_stub_status
module (http://nginx.org/en/docs/http/ngx_http_stub_status_module.html),
you have to special location containing "stub_status" directive, e.g.:

  Example #1: listen on localhost, access from 127.0.0.1 only:

    server {
        listen 127.0.0.1:80;
        server_name localhost;

        location = /nginx_stub_status {
            stub_status on;
            allow 127.0.0.1;
            deny all;
        }
    }

  Example #2: listen on *:80, access limited by HTTP basic auth:

    server {
        listen 80;
        server_name example.com;

        location = /nginx_stub_status {
            stub_status on;
            auth_basic "nginx status";
            auth_basic_user_file /path/to/auth_file;
        }
    }

  Please follow this link to get more information about HTTP basic auth:
  http://nginx.org/en/docs/http/ngx_http_auth_basic_module.html


4.2. NGINX Plus configuration

To configure this plugin to work with NGINX Plus using enhanced status
module (http://nginx.org/en/docs/http/ngx_http_status_module.html),
you have to add special location containing "status" directive, e.g.:

  Example #1: for NGINX Plus status, listen on *:80, authorized access:

    server {
        listen 80;
        server_name example.com;

        location = /status {
            status;
            auth_basic "nginx status";
            auth_basic_user_file /path/to/auth_file;
        }
    }

  (see http://nginx.org/en/docs/http/ngx_http_status_module.html for details)

  Do not forget to reload nginx after changing the configuration.


4.3. Plugin configuration

Edit nginx-nr-agent.ini configuration file:

  a) insert your New Relic license key;

  b) configure data sources (your nginx instances) using the following parameters:
    - url (required): full URL pointing to stub_status (nginx OSS) or status (N+) output;
    - name (required): name of the instance as it will be shown in the New Relic UI;
    - http_user, http_pass (optional): credentials used for
      HTTP basic authorization.


4.4. Configuring HTTPS proxy to access New Relic API endpoint

In case when a host with nginx-nr-agent plugin is behind a proxy,
there is an ability to add proxy URL to the startup configuration script:
  - /etc/sysconfig/nginx-nr-agent in RHEL/CentOS;
  - /etc/default/nginx-nr-agent in Debian/Ubuntu.

It should be done in a form of exporting the HTTPS_PROXY variable, e.g.:
export HTTPS_PROXY="your-proxy-host.example.com:3128"


5. Running the plugin

Plugin can be started as a daemon (default) or in foreground mode.
In order to start it daemonized, use the following command under root:

    $ service nginx-nr-agent start

By default, plugin is running under "nobody" user, writing log
into /var/log/nginx-nr-agent.log.

Plugin status can be checked by running:

    $ service nginx-nr-agent status

To stop plugin, use:

    $ service nginx-nr-agent stop

For debugging purposes, you can launch the plugin in foreground mode,
with all output going to stdout:

    $ nginx-nr-agent.py -f start

Carefully check plugin's output for any possible error messages.
In case of success, collected data should appear in the New Relic
user interface shortly after starting.
