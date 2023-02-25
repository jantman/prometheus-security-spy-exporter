FROM python:3.11.1-alpine3.17

COPY main.py /main.py
RUN pip install requests prometheus-client==0.15.0 xmltodict==0.13.0

EXPOSE 8080

ENTRYPOINT /main.py
