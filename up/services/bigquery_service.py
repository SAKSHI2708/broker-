import os

from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()


class BigQueryService:
    """Reusable BigQuery service for the UP agent."""

    def __init__(self):
        self.project_id = os.getenv(
            "GOOGLE_CLOUD_PROJECT",
            "gcp-app-builder"
        )

        self.dataset_id = os.getenv(
            "BQ_DATASET",
            "Broker_Productivity"
        )

        self.client = bigquery.Client(
            project=self.project_id
        )

    def query(self, sql: str, parameters=None):
        """
        Execute a parameterized BigQuery query.
        """

        job_config = bigquery.QueryJobConfig()

        if parameters:
            job_config.query_parameters = parameters

        query_job = self.client.query(
            sql,
            job_config=job_config
        )

        return [dict(row) for row in query_job.result()]