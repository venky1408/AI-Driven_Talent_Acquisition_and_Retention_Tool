import boto3
import json

# Initialize the Bedrock client
bedrock_client = boto3.client('bedrock-runtime')

# Initialize S3 client
s3_client = boto3.client('s3')

# S3 Buckets
RESULTS_BUCKET = "resume-analysis-results-bucket"
JOB_DESCRIPTION_BUCKET = "candidate-job-description-bucket"

# Define prompts
#PROMPTS = {
 #   "education_level": "Analyze the text and determine the level of education of the candidate, and whether he/she is pursuing MS/BS/PHD, and scale the GPAs to 4., very briefly give information about this in maximum 3 short lines.",
  #  "skills": "Extract the primary skills and expertise of the candidate from the given text, in one line.",
   # "work experience": "Summarize the current and past work experience of the candidate and check whether it matches with the job description. Look out for the challenges faced and relevant solutions provided, in 2 lines",
    #"similarity score":"predict a similarity score based on the f{job_description} and f{resume_text}"
#}

PROMPTS = {
    "education_level": "Analyze the text and determine the level of education of the candidate, and whether he/she is pursuing MS/BS/PHD, and scale the GPAs to 4., very briefly give information about this in maximum 3 short lines.",
    "skills": "Extract the primary skills and expertise of the candidate from the given text, in one line.",
    "work experience": "Summarize the current and past work experience of the candidate and check whether it matches with the job description. Look out for the challenges faced and relevant solutions provided, in 2 lines.",
    "candidate_relevancy": (
        "Analyze the following job description and resume text to assess the candidate's fit for the job:\n\n"
        "Job Description:\n"
        "{job_description}\n\n"
        "Resume Text:\n"
        "{resume_text}\n\n"
        "Provide a detailed analysis of whether the candidate is a good fit for the job. "
        "In your response, include:\n"
        "- Reasons why the candidate is a good fit or not a good fit.\n"
        "- Key areas where the candidate matches or lacks relevant skills or experience.\n"
        "-Always provide a relavant 'Recall-Oriented Understudy for Gisting Evaluation' score of the candidate based on the relevant skills required for the job on a scale from 0 to 1. If nothing matches, please provide a score of 0"
    )
}

# Helper function to clean and format the response
def clean_response(text):
    # Replace \\n with a newline
    cleaned_text = text.replace("\\n", " ")
    # Optionally remove leading/trailing whitespace
    cleaned_text = text.strip()
    return cleaned_text

# Lambda function handler
def lambda_handler(event, context):
    try:
        # Extract the text from the event payload
        resume_text = event.get("text", "")
        if not resume_text:
            raise ValueError("No text provided in the payload.")
        
        print("Received resume text for processing.")

        file_name = event.get("file_name", "default_response.json")
        print('Filename: ', file_name)

        # Extract job description from S3
        job_description_file_name = file_name.replace(".pdf", ".txt")  # Derive the .txt filename
        print(f"Fetching job description from S3: {JOB_DESCRIPTION_BUCKET}/{job_description_file_name}")

        # Fetch the job description file from S3
        job_description_object = s3_client.get_object(
            Bucket=JOB_DESCRIPTION_BUCKET,
            Key=job_description_file_name
        )
        job_description = job_description_object['Body'].read().decode('utf-8')
        print("Job Description Content:", job_description)

        # Function to interact with AWS Bedrock for each prompt
        def query_bedrock(prompt):
            # Construct the conversational format required by Anthropic Claude
            input_prompt = f"\n\nHuman: {prompt}\nResume Text:\n{resume_text}\n\nJob Description:\n{job_description}\n\nAssistant:"
            
            # Invoke the model
            response = bedrock_client.invoke_model(
                modelId='anthropic.claude-v2:1',
                body=json.dumps({
                    "prompt": input_prompt,
                    "max_tokens_to_sample": 400
                }),
                accept='application/json',
                contentType='application/json'
            )

            # Read and decode the StreamingBody
            response_body = json.loads(response['body'].read().decode('utf-8'))
            return response_body.get("completion", "No response received.")
        
        # Process prompts
        responses = {}
        for key, prompt in PROMPTS.items():
            print(f"Processing prompt: {key}")
            raw_response = query_bedrock(prompt)
            responses[key] = clean_response(raw_response)

        # Log and return responses
        print("Bedrock responses:", responses)

        # Save responses to S3
        response_key = f"responses/{file_name.replace('.pdf', '.json')}"
        s3_client.put_object(
            Bucket=RESULTS_BUCKET,
            Key=response_key,
            Body=json.dumps(responses),
            ContentType='application/json'
        )
        
        print(f"Response saved to S3 as {response_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(responses, indent=2)
        }
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({"error": str(e)})
        }
