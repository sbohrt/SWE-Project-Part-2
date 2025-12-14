FROM public.ecr.aws/lambda/python:3.13

# Copy only necessary directories and files for the Lambda function
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY lambda/ ${LAMBDA_TASK_ROOT}/lambda/
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -t ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD ["lambda.handler.handler"]
