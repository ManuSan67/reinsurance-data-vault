resources:
  jobs:
    reinsurance_monthly:
      name: reinsurance-monthly
      schedule:
        quartz_cron_expression: "0 0 6 5 * ?"
        timezone_id: America/Mexico_City
        pause_status: PAUSED
      tasks:
        - task_key: staging
          pipeline_task:
            pipeline_id: ${resources.pipelines.reinsurance_pipeline.id}

        - task_key: raw_vault
          depends_on:
            - task_key: staging
          notebook_task:
            notebook_path: ../notebooks/02_load_raw_vault.ipynb
            base_parameters:
              catalog: ${var.catalog}

        - task_key: business_vault
          depends_on:
            - task_key: raw_vault
          notebook_task:
            notebook_path: ../notebooks/03_business_vault.ipynb
            base_parameters:
              catalog: ${var.catalog}

        - task_key: mart
          depends_on:
            - task_key: business_vault
          notebook_task:
            notebook_path: ../notebooks/04_mart.ipynb
            base_parameters:
              catalog: ${var.catalog}

        - task_key: reconciliation
          depends_on:
            - task_key: business_vault
          notebook_task:
            notebook_path: ../notebooks/05_legacy_reconciliation.ipynb
            base_parameters:
              catalog: ${var.catalog}