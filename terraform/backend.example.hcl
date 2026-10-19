# COPY to backend.hcl (gitignored), review before use.
# This is the existing project bucket, NOT the previous demo account bucket.
bucket       = "novelty-margin-lakehouse-672350744457"
key          = "terraform/new-product-trend/study.tfstate"
region       = "us-east-1"
encrypt      = true
use_lockfile = true
