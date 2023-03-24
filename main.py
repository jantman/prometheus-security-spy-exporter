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
import time
import socket
from typing import Generator, Dict, Optional, List

import requests
import xmltodict
from wsgiref.simple_server import make_server, WSGIServer
from prometheus_client.core import REGISTRY, GaugeMetricFamily, Metric
from prometheus_client.exposition import make_wsgi_app, _SilentHandler
from prometheus_client.samples import Sample

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


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
        ip: str = os.environ.get('SECSPY_IP', '127.0.0.1')
        port: int = int(os.environ.get('SECSPY_PORT', '8000'))
        username: str = self._env_or_err('SECSPY_USER')
        passwd: str = self._env_or_err('SECSPY_PASS')
        use_https: bool = os.environ.get('SECSPY_USE_HTTPS') == 'true'
        verify_ssl: bool = os.environ.get('SECSPY_VERIFY_SSL') == 'true'
        timeout: int = int(os.environ.get('SECSPY_TIMEOUT_SEC', '30'))
        logger.info(
            'Connecting to Security Spy at %s:%s as user %s', ip, port, username
        )
        self.video_dir: Optional[str] = os.environ.get('SECSPY_STORAGE_DIR')
        self.sess: requests.Session = requests.Session()
        self.sess.auth = (username, passwd)
        self.url: str = f'http://{ip}:{port}/systemInfo'
        self.kwargs: dict = {'timeout': timeout}
        if use_https:
            self.url: str = f'https://{ip}:{port}/systemInfo'
            if verify_ssl:
                self.kwargs['verify'] = True
            else:
                self.kwargs['verify'] = False

    def _get_data(self) -> dict:
        r = self.sess.get(self.url, **self.kwargs)
        r.raise_for_status()
        return xmltodict.parse(r.content)['system']

    def collect(self) -> Generator[Metric, None, None]:
        sysinfo: dict = self._get_data()
        yield GaugeMetricFamily(
            'securityspy_server_camera_count', 'Camera count',
            value=int(sysinfo['server']['camera-count'])
        )
        yield GaugeMetricFamily(
            'securityspy_server_cpu_usage', 'CPU Usage',
            unit='percent', value=int(sysinfo['server']['cpu-usage'])
        )
        yield GaugeMetricFamily(
            'securityspy_server_memory_pressure', 'Memory Pressure',
            value=int(sysinfo['server']['memory-pressure'])
        )
        # cameras
        connected = LabeledGaugeMetricFamily(
            'securityspy_camera_connected', 'Camera connected'
        )
        fps = LabeledGaugeMetricFamily(
            'securityspy_camera_fps', 'Camera FPS', unit='FPS'
        )
        height = LabeledGaugeMetricFamily(
            'securityspy_camera_height', 'Camera Height', unit='PX'
        )
        width = LabeledGaugeMetricFamily(
            'securityspy_camera_width', 'Camera Width', unit='PX'
        )
        md_cap = LabeledGaugeMetricFamily(
            'securityspy_camera_md_capture', 'Camera Motion Detection Capture'
        )
        md_en = LabeledGaugeMetricFamily(
            'securityspy_camera_md_enable', 'Camera Motion Detection Enabled'
        )
        mode = LabeledGaugeMetricFamily(
            'securityspy_camera_mode', 'Camera Mode'
        )
        mode_a = LabeledGaugeMetricFamily(
            'securityspy_camera_mode_a', 'Camera Mode A'
        )
        mode_c = LabeledGaugeMetricFamily(
            'securityspy_camera_mode_c', 'Camera Mode C'
        )
        mode_m = LabeledGaugeMetricFamily(
            'securityspy_camera_mode_m', 'Camera Mode M'
        )
        tslf = LabeledGaugeMetricFamily(
            'securityspy_camera_time_since_last_frame',
            'Camera Time Since Last Frame', unit='seconds'
        )
        tslm = LabeledGaugeMetricFamily(
            'securityspy_camera_time_since_last_motion',
            'Camera Time Since Last Motion', unit='seconds'
        )
        metrics = [
            connected, fps, height, width, md_cap, md_en, mode, mode_a, mode_c,
            mode_m, tslf, tslm
        ]
        for cam in sysinfo['cameralist']['camera']:
            labels = {'camera_name': cam['name']}
            connected.add_metric(
                labels=labels, value=1 if cam['connected'] == 'yes' else 0
            )
            fps.add_metric(
                labels=labels, value=float(cam['current-fps'])
            )
            height.add_metric(
                labels=labels, value=int(cam['height'])
            )
            width.add_metric(
                labels=labels, value=int(cam['width'])
            )
            md_cap.add_metric(
                labels=labels, value=1 if cam['md_capture'] == 'yes' else 0
            )
            md_en.add_metric(
                labels=labels, value=1 if cam['md_enabled'] == 'yes' else 0
            )
            mode.add_metric(
                labels=labels, value=1 if cam['mode'] == 'active' else 0
            )
            mode_a.add_metric(
                labels=labels, value=1 if cam['mode-a'] == 'armed' else 0
            )
            mode_c.add_metric(
                labels=labels, value=1 if cam['mode-c'] == 'armed' else 0
            )
            mode_m.add_metric(
                labels=labels, value=1 if cam['mode-m'] == 'armed' else 0
            )
            tslf.add_metric(
                labels=labels, value=float(cam['timesincelastframe'])
            )
            tslm.add_metric(
                labels=labels, value=float(cam['timesincelastmotion'])
            )
        if self.video_dir:
            numf = LabeledGaugeMetricFamily(
                'securityspy_camera_num_files',
                'Camera Number of Files'
            )
            num_bytes = LabeledGaugeMetricFamily(
                'securityspy_camera_recorded',
                'Camera Recorded Bytes', unit='bytes'
            )
            oldest_age = LabeledGaugeMetricFamily(
                'securityspy_oldest_recording_age',
                'Camera Oldest Recording Age', unit='seconds'
            )
            newest_age = LabeledGaugeMetricFamily(
                'securityspy_newest_recording_age',
                'Camera Newest Recording Age', unit='seconds'
            )
            metrics.extend([numf, num_bytes, newest_age, oldest_age])
            logger.debug('Listing subdirectories under %s', self.video_dir)
            subdir: str
            for subdir in [
                f.path for f in os.scandir(self.video_dir) if f.is_dir()
            ]:
                dirname: str = os.path.basename(subdir)
                if dirname.startswith('.'):
                    logger.debug('Skipping dot directory: %s', dirname)
                    continue
                logger.debug('Handling directory: %s', dirname)
                labels = {'camera_name': dirname}
                numfiles: int = 0
                total_bytes: int = 0
                oldest: float = time.time() + 100
                newest: float = 0
                for topdir, subdirs, files in os.walk(subdir):
                    for f in files:
                        fpath: str = os.path.join(subdir, topdir, f)
                        numfiles += 1
                        stat = os.stat(fpath)
                        total_bytes += stat.st_size
                        if stat.st_ctime > newest:
                            newest = stat.st_ctime
                        if stat.st_ctime < oldest:
                            oldest = stat.st_ctime
                age_oldest = time.time() - oldest
                age_newest = time.time() - newest
                logger.debug(
                    '%s: numfiles=%d total_bytes=%d oldest_age=%d newest_age=%d',
                    dirname, numfiles, total_bytes, age_oldest, age_newest
                )
                numf.add_metric(labels=labels, value=numfiles)
                num_bytes.add_metric(labels=labels, value=total_bytes)
                oldest_age.add_metric(labels=labels, value=age_oldest)
                newest_age.add_metric(labels=labels, value=age_newest)
        yield from metrics


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
    REGISTRY.register(SecuritySpyCollector())
    logger.info('Starting HTTP server on port %d', args.port)
    serve_exporter(args.port)
