"""
LogisticAI daily batch ETL DAG.
Orchestrated by Cloud Composer (Airflow).
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "logisticai-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": ["platform-alerts@logisticai.com"],
}

with DAG(
    dag_id="daily_logistics_etl",
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["logistics", "etl", "production"],
) as dag:

    load_raw = BashOperator(
        task_id="load_raw_shipments",
        bash_command="""
        bq load \
          --source_format=PARQUET \
          --replace \
          logisticai:staging.shipments_{{ ds_nodash }} \
          gs://logisticai-lake/raw/shipments/{{ ds }}/*.parquet
        """,
    )

    run_dbt = BashOperator(
        task_id="run_dbt_models",
        bash_command="dbt run --profiles-dir /dbt --target prod --select marts.*",
    )

    check_data_quality = BashOperator(
        task_id="great_expectations_checkpoint",
        bash_command="great_expectations checkpoint run logistics_daily",
    )

    trigger_drift_check = BashOperator(
        task_id="ml_drift_check",
        bash_command="python /opt/airflow/dags/scripts/run_drift_check.py",
    )

    load_raw >> run_dbt >> check_data_quality >> trigger_drift_check
