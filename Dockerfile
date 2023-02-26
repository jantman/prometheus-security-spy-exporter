FROM python:3.11.1-alpine3.17

COPY main.py /main.py
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

EXPOSE 8080

ENTRYPOINT /main.py
