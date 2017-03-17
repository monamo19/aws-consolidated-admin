import boto3
import collections

sfn = boto3.client('stepfunctions')

def lambda_handler(event, context):
    status_counts = collections.defaultdict(lambda: 0)

    for wf in event['Workflows']:
        resp = sfn.describe_execution(
            executionArn=wf['ExecutionArn'])

        status = resp['status']
        wf['Status'] = status
        status_counts[status] += 1

        if 'stopDate' in resp:
            wf['StoppedAt'] = resp['stopDate'].isoformat()

    if status_counts['RUNNING'] > 0:
        event['Status'] = 'RUNNING'
    else:
        if status_counts['SUCCEEDED'] == len(event['Workflows']):
            event['Status'] = 'SUCCEEDED'
        else:
            event['Status'] = 'FAILED'

    return event
