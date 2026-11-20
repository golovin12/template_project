FROM python:3.11

WORKDIR /repair_service

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip
RUN apt install libpango-1.0-0 libpangoft2-1.0-0 libffi-dev libcairo2

COPY requirements.txt ./

RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ --default-timeout=120 -r requirements.txt

COPY . .
