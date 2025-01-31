import boto3
import json

sqs = boto3.client('sqs', region_name='us-east-2')
SQS_QUEUE_URL = 'https://sqs.us-east-2.amazonaws.com/971422676723/ArticleQueue'

def lambda_handler(event, context):
    try:
        # Send event to SQS
        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(event)
        )
        
        # Return 202 immediately to avoid webhook timeout
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Request accepted. Processing asynchronously.'})
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }