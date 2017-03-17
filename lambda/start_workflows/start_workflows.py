import boto3
import json

sfn = boto3.client('stepfunctions')

def lambda_handler(event, context):
    output = []

    for wf in event['Workflows']:
        resp = sfn.start_execution(
            stateMachineArn=event['StateMachineArn'],
            name=wf['ExecutionName'],
            input=json.dumps(wf))

        output.append({
            'ExecutionArn': resp['executionArn'],
            'StartedAt': resp['startDate'].isoformat()
        })

    return output
