FROM apache/airflow:2.9.2-python3.12

EXPOSE 8080

CMD ["airflow", "standalone"]
