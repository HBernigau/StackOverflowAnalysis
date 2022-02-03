FROM python:3.8.6

COPY . /req
WORKDIR /req
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip install -r essentials.txt
RUN apt-get update && apt-get install -y netcat