.PHONY: deploy-infra deploy-notebooks deploy-all destroy help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

deploy-infra: ## Provision AWS + Databricks infrastructure with Terraform
	cd terraform && terraform init && terraform apply

deploy-notebooks: ## Deploy notebooks and jobs to Databricks with DAB
	databricks bundle deploy \
	  -var="uc_catalog=$$(cd terraform && terraform output -raw uc_catalog_name)" \
	  -var="uc_schema=$$(cd terraform && terraform output -raw uc_schema_name)" \
	  -var="rw_host=$$(cd terraform && terraform output -raw ec2_public_ip)" \
	  -var="s3_bucket=$$(cd terraform && terraform output -raw s3_bucket_name)" \
	  -var="kinesis_stream_name=$$(cd terraform && terraform output -raw kinesis_stream_name)" \
	  -var="aws_region=$$(cd terraform && terraform output -raw aws_region)"

deploy-all: deploy-infra deploy-notebooks ## Deploy everything (infra + notebooks)

destroy: ## Tear down all resources
	databricks bundle destroy --auto-approve || true
	cd terraform && terraform destroy

status: ## Show key infrastructure info
	@echo "=== Terraform Outputs ==="
	@cd terraform && terraform output
	@echo ""
	@echo "=== Databricks Bundle ==="
	@databricks bundle summary 2>/dev/null || echo "Bundle not deployed yet"

validate: ## Validate Terraform and DAB configs
	cd terraform && terraform validate
	databricks bundle validate
