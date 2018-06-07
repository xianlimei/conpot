# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import logging
import socket

import gevent
from gevent.server import StreamServer
import conpot
import conpot.core as conpot_core
from conpot.protocols.kamstrup.management_protocol.command_responder import CommandResponder
from conpot.helpers import str_to_bytes

logger = logging.getLogger(__name__)


class KamstrupManagementServer(object):
    def __init__(self, template, template_directory, args, timeout=0):
        self.template = template
        self.timeout = timeout
        self.command_responder = CommandResponder()
        self.banner = "\r\nWelcome...\r\nConnected to [{0}]\r\n"
        logger.info('Kamstrup management protocol server initialized.')
        self.server = None

    def handle(self, sock, address):
        session = conpot_core.get_session('kamstrup_management_protocol', address[0], address[1])
        logger.info('New Kamstrup connection from %s:%s. (%s)', address[0], address[1], session.id)
        session.add_event({'type': 'NEW_CONNECTION'})

        try:
            sock.send(
                str_to_bytes(self.banner.format(conpot_core.get_databus().get_value("mac_address")))
            )

            while True:
                data = sock.recv(1024)
                if not data:
                    logger.info('Kamstrup client disconnected. (%s)', session.id)
                    session.add_event({'type': 'CONNECTION_LOST'})
                    break
                request = data.decode()
                logdata = {'request': request}
                response = self.command_responder.respond(request)
                logdata['response'] = response
                logger.info('Kamstrup management traffic from %s: %s (%s)', address[0], logdata, session.id)
                session.add_event(logdata)
                gevent.sleep(0.25)  # TODO measure delay and/or RTT

                if response is None:
                    session.add_event({'type': 'CONNECTION_LOST'})
                    break
                # encode data before sending
                reply = str_to_bytes(response)
                sock.send(reply)

        except socket.timeout:
            logger.debug('Socket timeout, remote: %s. (%s)', address[0], session.id)
            session.add_event({'type': 'CONNECTION_LOST'})

        sock.close()

    def start(self, host, port):
        connection = (host, port)
        self.server = StreamServer(connection, self.handle)
        logger.info('Kamstrup management protocol server started on: %s', connection)
        self.server.serve_forever()

    def stop(self):
        self.server.stop()


if __name__ == '__main__':
    TCP_IP = '127.0.0.1'
    TCP_PORT = 50100
    import os
    dir_name = os.path.dirname(conpot.__file__)
    conpot_core.get_databus().initialize(dir_name + '/templates/kamstrup_382/template.xml')
    server = KamstrupManagementServer(dir_name + '/templates/kamstrup_382/kamstrup_management/kamstrup_management.xml',
                                      None, None)
    try:
        server.start(TCP_IP, TCP_PORT)
    except KeyboardInterrupt:
        server.stop()