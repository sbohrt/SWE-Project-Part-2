#!/bin/bash
# Script to prepare Lambda deployment package with only necessary files

echo "Preparing Lambda deployment package..."

# Create staging directory
rm -rf lambda_deploy
mkdir -p lambda_deploy

# Copy only necessary directories
echo "Copying source code..."
cp -r src/ lambda_deploy/src/
cp -r lambda/ lambda_deploy/lambda/

# Copy requirements
cp requirements.txt lambda_deploy/

echo "Lambda package prepared in lambda_deploy/"
echo "Package contents:"
du -sh lambda_deploy/*
