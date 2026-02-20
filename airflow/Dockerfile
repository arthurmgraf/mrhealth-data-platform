# Pin by tag for readability; production should also verify digest
FROM apache/airflow:3.1.7-python3.11

USER airflow

RUN pip install --no-cache-dir \
    apache-airflow-providers-google==10.12.0 \
    google-cloud-bigquery==3.17.2 \
    google-cloud-storage==2.14.0 \
    pyyaml==6.0.1
