COPY product_trends.trend_features_load
FROM 's3://novelty-margin-lakehouse-672350744457/curated/new_product_trend/features/'
IAM_ROLE 'arn:aws:iam::672350744457:role/ReferenceRedshiftCuratedLoadRole'
FORMAT AS PARQUET;
