# Copyright (c) 2013-2014 Rackspace, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys

from oslo.config import cfg
from paste import deploy
from paste import httpserver

from barbican.common import config


opt_devstack_group = cfg.OptGroup(name='devstack',
                                  title='DevStack Barbican Settings')

devstack_wsgi_opts = [
    cfg.StrOpt('admin_paste_config',
               default="config:/etc/barbican/barbican-admin-paste.ini",
               help="Configuration file for WSGI definition of Admin"
               ),
    cfg.StrOpt('bind_host',
               default='',
               help="Host address to bind to"
               ),
    cfg.IntOpt('admin_bind_port',
               default='9312',
               help="Port to bind the Admin server on"
               ),
]

CONF = cfg.CONF
CONF.register_group(opt_devstack_group)
CONF.register_opts(devstack_wsgi_opts, opt_devstack_group)


def fail(returncode, e):
    sys.stderr.write("ERROR: {0}\n".format(e))
    sys.exit(returncode)


if __name__ == '__main__':
    try:
        config.parse_args()

        admin_app = deploy.loadapp(CONF.devstack.admin_paste_config)
        httpserver.serve(admin_app,
                         host=CONF.devstack.bind_host,
                         port=CONF.devstack.admin_bind_port)
    except RuntimeError as e:
        fail(1, e)
