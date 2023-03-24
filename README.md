# EXPERIMENTAL/ALPHA/UNSUPPORTED prometheus-security-spy-exporter

[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip) [![Docker Pulls](https://img.shields.io/docker/pulls/jantman/prometheus-security-spy-exporter)](https://hub.docker.com/repository/docker/jantman/prometheus-security-spy-exporter) [![GitHub last commit](https://img.shields.io/github/last-commit/jantman/prometheus-security-spy-exporter)](https://github.com/jantman/prometheus-security-spy-exporter)

Prometheus exporter for [Security Spy](https://www.bensoftware.com/securityspy/) using the API and HTML scraping for metrics.

**WARNING** This code is to be considered experimental/alpha and essentially **unsupported**. I don't use Security Spy myself; I'm writing this for a local non-profit that does, and just wants to get notified if it stops recording or otherwise breaks. Once I get an initial version of this written and working, I will likely never touch it again. I also will have no way to test changes, as I don't run Security Spy myself. Please plan accordingly. If you'd like to take over this project, please let me know via an issue.

## Usage

### Docker

To run on port 8080:

```
docker run -p 8080:8080 \
    -e SECSPY_IP=YOUR_DSM_IP \
    -e SECSPY_USER=YOUR_USERNAME \
    -e SECSPY_PASS='YOUR_PASSWORD' \
    jantman/prometheus-synology-api-exporter:latest
```

### MacOS

Yeah, this may not be best practice. Also, note that the plist currently has `python3.11` hard-coded. Please update that as needed.

1. Install [homebrew](https://brew.sh/) and, if not done yet, ``brew install python``
2. Install dependencies: ``pip install requests prometheus-client==0.15.0 xmltodict==0.13.0``
3. Copy [main.py](main.py) to ``/Users/administrator/security_spy_exporter.py``
4. After editing the relevant items (environment variables; change the ``EDIT-ME`` values, and remove the ``SECSPY_STORAGE_DIR`` one if you don't want storage metrics), copy [security_spy_exporter.plist](security_spy_exporter.plist) to ``/Library/LaunchDaemons/security_spy_exporter.plist`` (using ``sudo cp security_spy_exporter.plist /Library/LaunchDaemons/security_spy_exporter.plist``), and then run ``sudo chown root:wheel /Library/LaunchDaemons/security_spy_exporter.plist && sudo launchctl load /Library/LaunchDaemons/security_spy_exporter.plist``
5. Open System Preferences -> Security and Privacy. Click the "Privacy" tab at the top, and then scroll to and click "Full Disk Access" in the left menu. In the main pane, scroll to and click the check box next to `python3.11`.
6. ``sudo launchctl unload /Library/LaunchDaemons/security_spy_exporter.plist && sudo launchctl load /Library/LaunchDaemons/security_spy_exporter.plist``

You should now be able to reach the metrics endpoint and get metrics back (default: http://127.0.0.1:8080 ).

### Environment Variables

* `SECSPY_IP` (*optional*) - The IP address or hostname to connect to Security Spy on. Defaults to `127.0.0.1`. **Required** when running via Docker.
* `SECSPY_USER` (**required**) - The username for logging in to the Security Spy web UI. Ideally this should be a limited user.
* `SECSPY_PASS` (**required**) - The password for `SECSPY_USER`.
* `SECSPY_PORT` (*optional*) - The port number to connect to Security Spy on. Defaults to 8000.
* `SECSPY_USE_HTTPS` (*optional*) - Set to `true` if you want to connect over HTTPS. Defaults to unset (plain HTTP).
* `SECSPY_VERIFY_SSL` (*optional*) - Set to `true` if you want to verify SSL. Defaults to unset (verify False).
* `SECSPY_TIMEOUT_SEC` (*optional*) - Timeout in seconds for API calls. Defaults to 30.
* `SECSPY_STORAGE_DIR` (*optional) - Video storage directory, if you want to gather statistics on it. **Note** that this can significantly increase scrape time.

### Debugging

For debugging, append `-vv` to your `docker run` command, to run the entrypoint with debug-level logging.

## Metrics Provided

An example of the output of the `/metrics` endpoint can be seen at [example.prom](example.prom)

## Development

Clone the repo, then in your clone:

```
python3 -mvenv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Release Process

Tag the repo. [GitHub Actions](https://github.com/jantman/prometheus-security-spy-exporter/actions) will run a Docker build, push to Docker Hub, and create a release on the repo.
