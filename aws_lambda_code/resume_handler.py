import boto3
import json
import base64

# Initialize S3 client
s3_client = boto3.client('s3')

# S3 Bucket Names
RESUME_BUCKET = "candidate-resume-processing-bucket"
JOB_DESCRIPTION_BUCKET = "candidate-job-description-bucket"  # New bucket for job descriptions

def lambda_handler(event, context):
    try:
        # Handle preflight requests (CORS)
        if event["httpMethod"] == "OPTIONS":
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({
                    'message': 'CORS preflight request successful'
                })
            }

        print('resume lambda invoked...')
        print('event: ', event)

        # Parse the body from the event
        body = event.get("body", "")
        if not body:
            raise ValueError("Missing body in the event")
        
        # Decode the JSON body
        parsed_body = json.loads(body)
        get_file_content = parsed_body.get("content", None)
        file_name = parsed_body.get("file_name", "default_file_name.pdf")
        job_description = parsed_body.get("job_description", "").strip()  # Extract job description
        
        print("get_file_content is: ", get_file_content)
        print('file_name: ', file_name)
        print('job_description: ', job_description)

        if not get_file_content:
            raise ValueError("Missing 'content' in the body")
        
        if not job_description:
            raise ValueError("Missing 'job_description' in the body")

        # Decode the base64 content
        decode_content = base64.b64decode(get_file_content)

        # Upload the PDF file to the resume bucket
        s3_client.put_object(
            Bucket=RESUME_BUCKET,
            Key=file_name,
            Body=decode_content
        )
        print(f"PDF uploaded to {RESUME_BUCKET}/{file_name}")

        # Create a .txt file for the job description and upload it to the job description bucket
        job_description_file_name = file_name.replace(".pdf", ".txt")
        s3_client.put_object(
            Bucket=JOB_DESCRIPTION_BUCKET,
            Key=job_description_file_name,
            Body=job_description,
            ContentType="text/plain"
        )
        print(f"Job description uploaded to {JOB_DESCRIPTION_BUCKET}/{job_description_file_name}")

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',  # Adjust '*' to specific domains in production
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({
                'message': 'File and job description uploaded successfully'
            })
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({
                'message': 'Failed to upload file or job description',
                'error': str(e)
            })
        }
