#!/usr/bin/env python3
"""
Setup script for local DynamoDB tables.
Run this after starting DynamoDB Local with:
  docker run -p 8000:8000 amazon/dynamodb-local
"""
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

# Connect to local DynamoDB
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url='http://localhost:8000',
    region_name='us-east-1',
    aws_access_key_id='dummy',
    aws_secret_access_key='dummy'
)

def create_rating_table():
    """Create the model ratings table."""
    try:
        table = dynamodb.create_table(
            TableName='swe-project-model-ratings',
            KeySchema=[
                {
                    'AttributeName': 'modelId',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'modelId',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand billing for local testing
        )

        print(f"✅ Created table: {table.table_name}")
        print(f"   Status: {table.table_status}")
        return table
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"⚠️  Table 'swe-project-model-ratings' already exists")
            return dynamodb.Table('swe-project-model-ratings')
        else:
            print(f"❌ Error creating table: {e}")
            raise

def create_lineage_table():
    """Create the model lineage table."""
    try:
        table = dynamodb.create_table(
            TableName='ModelLineage',
            KeySchema=[
                {
                    'AttributeName': 'PK',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'SK',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'PK',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'SK',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        print(f"✅ Created table: {table.table_name}")
        print(f"   Status: {table.table_status}")
        return table
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"⚠️  Table 'ModelLineage' already exists")
            return dynamodb.Table('ModelLineage')
        else:
            print(f"❌ Error creating table: {e}")
            raise

def insert_sample_data():
    """Insert some sample model data for testing."""
    table = dynamodb.Table('swe-project-model-ratings')

    sample_models = [
        {
            'modelId': 'bert-base-uncased',
            'name': 'bert-base-uncased',
            'url': 'https://huggingface.co/google-bert/bert-base-uncased',
            'type': 'model',
            'net_score': Decimal('0.85'),
            'ramp_up_time': Decimal('0.9'),
            'bus_factor': Decimal('0.7'),
            'license': Decimal('1.0'),
            'license_id': 'apache-2.0',
            'size_score': {
                'raspberry_pi': Decimal('0.3'),
                'jetson_nano': Decimal('0.5'),
                'desktop_pc': Decimal('0.8'),
                'aws_server': Decimal('0.9')
            },
            'size_mb': Decimal('420.5'),
            'performance_claims': Decimal('0.8'),
            'dataset_and_code_score': Decimal('0.9'),
            'dataset_quality': Decimal('0.85'),
            'code_quality': Decimal('0.75')
        },
        {
            'modelId': 'gpt2',
            'name': 'gpt2',
            'url': 'https://huggingface.co/openai-community/gpt2',
            'type': 'model',
            'net_score': Decimal('0.92'),
            'ramp_up_time': Decimal('0.95'),
            'bus_factor': Decimal('0.8'),
            'license': Decimal('1.0'),
            'license_id': 'mit',
            'size_score': {
                'raspberry_pi': Decimal('0.4'),
                'jetson_nano': Decimal('0.6'),
                'desktop_pc': Decimal('0.9'),
                'aws_server': Decimal('0.95')
            },
            'size_mb': Decimal('548.5'),
            'performance_claims': Decimal('0.9'),
            'dataset_and_code_score': Decimal('0.95'),
            'dataset_quality': Decimal('0.9'),
            'code_quality': Decimal('0.85')
        }
    ]

    for model in sample_models:
        try:
            table.put_item(Item=model)
            print(f"✅ Inserted sample model: {model['name']}")
        except ClientError as e:
            print(f"❌ Error inserting {model['name']}: {e}")

def main():
    print("🚀 Setting up local DynamoDB tables...\n")

    # Create tables
    create_rating_table()
    create_lineage_table()

    print("\n📊 Inserting sample data...\n")
    insert_sample_data()

    print("\n✅ Setup complete!")
    print("\nYou can now start the Flask backend with:")
    print("  python3 src/swe_project/api/run.py")
    print("\nMake sure to set these environment variables first:")
    print("  export AWS_ENDPOINT_URL=http://localhost:8000")
    print("  export AWS_ACCESS_KEY_ID=dummy")
    print("  export AWS_SECRET_ACCESS_KEY=dummy")
    print("  export AWS_DEFAULT_REGION=us-east-1")

if __name__ == '__main__':
    main()
