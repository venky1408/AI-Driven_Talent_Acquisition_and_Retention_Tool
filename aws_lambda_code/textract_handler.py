import boto3
import json

# Initialize clients for S3, Textract, and Lambda
s3_client = boto3.client('s3')
textract_client = boto3.client('textract')
lambda_client = boto3.client('lambda')  # For invoking the bedrock Lambda function

BEDROCK_LAMBDA = "arn:aws:lambda:us-east-1:619071344683:function:bedrock-handler"

def lambda_handler(event, context):
    # Get the bucket name and file name from the event
    for record in event['Records']:
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        
        print(f"File uploaded: {object_key} in bucket: {bucket_name}")
        
        # Ensure the file is a PDF
        if object_key.lower().endswith('.pdf'):
            # Call Textract to process the PDF file
            response = textract_client.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': object_key
                    }
                }
            )
            job_id = response['JobId']
            print(f"Textract Job started with ID: {job_id}")
            
            # Poll the job status until completion
            while True:
                status = textract_client.get_document_text_detection(JobId=job_id)
                if status['JobStatus'] in ['SUCCEEDED', 'FAILED']:
                    break
            
            if status['JobStatus'] == 'SUCCEEDED':
                print("Textract Job succeeded.")
                
                # Collect the extracted text
                extracted_text = []
                for block in status['Blocks']:
                    if block['BlockType'] == 'LINE':
                        extracted_text.append(block['Text'])
                
                # Combine all lines into a single string
                text_data = "\n".join(extracted_text)
                print("Extracted Text:", text_data)
                
                # Invoke the second Lambda function
                try:
                    print("Invoking the second Lambda function...")
                    lambda_response = lambda_client.invoke(
                        FunctionName=BEDROCK_LAMBDA,
                        InvocationType='RequestResponse',
                        Payload=json.dumps({"text": text_data, "file_name": object_key})  # Passing the extracted text
                    )
                    
                    # Parse the response from the second Lambda function
                    response_payload = json.loads(lambda_response['Payload'].read())
                    print("Response from second Lambda:", response_payload)
                except Exception as e:
                    print(f"Failed to invoke the second Lambda function: {str(e)}")
            else:
                print("Textract Job failed.")
        else:
            print("Uploaded file is not a PDF. Skipping.")

    return {
        'statusCode': 200,
        'body': json.dumps('PDF processed successfully and second Lambda invoked.')
    }
