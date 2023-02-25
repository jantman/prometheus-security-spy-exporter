#!/usr/bin/env python
"""
https://github.com/jantman/prometheus-security-spy-exporter

MIT License

Copyright (c) 2023 Jason Antman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys
import os
import argparse
import logging
import socket
import time
from typing import Generator, List, Dict, Optional

import xmltodict
from wsgiref.simple_server import make_server, WSGIServer
from prometheus_client.core import (
    REGISTRY, GaugeMetricFamily, InfoMetricFamily, StateSetMetricFamily, Metric
)
from prometheus_client.exposition import make_wsgi_app, _SilentHandler
from prometheus_client.samples import Sample

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


def enum_metric_family(
    name: str, documentation: str, states: List[str], value: str
):
    """Since the client library doesn't have this..."""
    if value not in states:
        logger.error(
            'Value of "%s" not listed in states %s for enum_metric_family %s',
            value, states, name
        )
        states.append(value)
    return StateSetMetricFamily(
        name, documentation,
        {
            x: x == value for x in states
        }
    )


class LabeledGaugeMetricFamily(Metric):
    """Not sure why the upstream one doesn't allow labels..."""

    def __init__(
        self,
        name: str,
        documentation: str,
        value: Optional[float] = None,
        labels: Dict[str, str] = None,
        unit: str = '',
    ):
        Metric.__init__(self, name, documentation, 'gauge', unit)
        if labels is None:
            labels = {}
        self._labels = labels
        if value is not None:
            self.add_metric(labels, value)

    def add_metric(self, labels: Dict[str, str], value: float) -> None:
        """Add a metric to the metric family.
        Args:
          labels: A dictionary of labels
          value: A float
        """
        self.samples.append(
            Sample(self.name, dict(labels | self._labels), value, None)
        )


class LabeledStateSetMetricFamily(Metric):
    """Not sure why upstream doesn't allow this..."""

    def __init__(
        self,
        name: str,
        documentation: str,
        labels: Optional[Dict[str, str]] = None,
    ):
        Metric.__init__(self, name, documentation, 'stateset')
        if labels is None:
            labels = {}
        self._labels = labels

    def add_metric(
        self, value: Dict[str, bool], labels: Optional[Dict[str, str]] = None
    ) -> None:
        if labels is None:
            labels = {}
        for state, enabled in sorted(value.items()):
            v = (1 if enabled else 0)
            self.samples.append(Sample(
                self.name,
                dict(self._labels | labels | {self.name: state}),
                v,
            ))


class SecuritySpyCollector:

    def _env_or_err(self, name: str) -> str:
        s: str = os.environ.get(name)
        if not s:
            raise RuntimeError(
                f'ERROR: You must set the "{name}" environment variable.'
            )
        return s

    def __init__(self):
        logger.debug('Instantiating SecuritySpyCollector')
        ip: str = self._env_or_err('SECSPY_IP')
        port: int = int(os.environ.get('SECSPY_PORT', '8000'))
        username: str = self._env_or_err('SECSPY_USER')
        passwd: str = self._env_or_err('SECSPY_PASS')
        use_https: bool = os.environ.get('SECSPY_USE_HTTPS') == 'true'
        verify_ssl: bool = os.environ.get('SECSPY_VERIFY_SSL') == 'true'
        timeout: int = int(os.environ.get('SECSPY_TIMEOUT_SEC', '30'))
        logger.info(
            'Connecting to Security Spy at %s:%s as user %s', ip, port, username
        )
        self.query_time: float = 0.0

    def _get_systeminfo_data(self):
        with open('apiResponse.xml', 'r') as fh:
            xml = fh.read()
        d = xmltodict.parse(xml)
        import json
        print(json.dumps(d, sort_keys=True, indent=4))

    def collect(self) -> Generator[Metric, None, None]:
        logger.debug('Beginning collection')
        raise NotImplementedError()


def _get_best_family(address, port):
    """
    Automatically select address family depending on address
    copied from prometheus_client.exposition.start_http_server
    """
    # HTTPServer defaults to AF_INET, which will not start properly if
    # binding an ipv6 address is requested.
    # This function is based on what upstream python did for http.server
    # in https://github.com/python/cpython/pull/11767
    infos = socket.getaddrinfo(address, port)
    family, _, _, _, sockaddr = next(iter(infos))
    return family, sockaddr[0]


def serve_exporter(port: int, addr: str = '0.0.0.0'):
    """
    Copied from prometheus_client.exposition.start_http_server, but doesn't run
    in a thread because we're just a proxy.
    """

    class TmpServer(WSGIServer):
        """Copy of WSGIServer to update address_family locally"""

    TmpServer.address_family, addr = _get_best_family(addr, port)
    app = make_wsgi_app(REGISTRY)
    httpd = make_server(
        addr, port, app, TmpServer, handler_class=_SilentHandler
    )
    httpd.serve_forever()


def parse_args(argv):
    p = argparse.ArgumentParser(description='Prometheus Security Spy exporter')
    p.add_argument(
        '-v', '--verbose', dest='verbose', action='count', default=0,
        help='verbose output. specify twice for debug-level output.'
    )
    PORT_DEF = int(os.environ.get('PORT', '8080'))
    p.add_argument(
        '-p', '--port', dest='port', action='store', type=int,
        default=PORT_DEF, help=f'Port to listen on (default: {PORT_DEF})'
    )
    args = p.parse_args(argv)
    return args


def set_log_info():
    set_log_level_format(
        logging.INFO, '%(asctime)s %(levelname)s:%(name)s:%(message)s'
    )


def set_log_debug():
    set_log_level_format(
        logging.DEBUG,
        "%(asctime)s [%(levelname)s %(filename)s:%(lineno)s - "
        "%(name)s.%(funcName)s() ] %(message)s"
    )


def set_log_level_format(level: int, format: str):
    """
    Set logger level and format.

    :param level: logging level; see the :py:mod:`logging` constants.
    :type level: int
    :param format: logging formatter format string
    :type format: str
    """
    formatter = logging.Formatter(fmt=format)
    logger.handlers[0].setFormatter(formatter)
    logger.setLevel(level)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    if args.verbose > 1:
        set_log_debug()
    elif args.verbose == 1:
        set_log_info()
    SecuritySpyCollector()._get_systeminfo_data()
    raise NotImplementedError()
    logger.debug('Registering collector...')
    REGISTRY.register(SecuritySpyCollector())
    logger.info('Starting HTTP server on port %d', args.port)
    serve_exporter(args.port)
