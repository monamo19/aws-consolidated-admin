import base64
import boto3
import botocore
import json
import os
import posixpath

# from boto3.dynamodb.conditions import Attr

CLOUDTRAIL_BUCKET                    = os.environ['CLOUDTRAIL_BUCKET']
CONFIG_BUCKET                        = os.environ['CONFIG_BUCKET']
DIST_BUCKET                          = os.environ['DIST_BUCKET']
ACCOUNT_TABLE                        = os.environ['ACCOUNT_TABLE']
DEPLOY_TEMPLATE_STATE_MACHINE_ARN    = os.environ['DEPLOY_TEMPLATE_STATE_MACHINE_ARN']
PARALLEL_EXECUTION_STATE_MACHINE_ARN = os.environ['PARALLEL_EXECUTION_STATE_MACHINE_ARN']
EVENTS_SNS_NOTIFICATION_URL          = os.environ['EVENTS_SNS_NOTIFICATION_URL']
CONFIG_SNS_NOTIFICATION_URL          = os.environ['CONFIG_SNS_NOTIFICATION_URL']
CLOUDTRAIL_SNS_NOTIFICATION_URL      = os.environ['CLOUDTRAIL_SNS_NOTIFICATION_URL']
STACK_NAME                           = os.environ['STACK_NAME']
TEMPLATE_FILE_NAME                   = os.environ['TEMPLATE_FILE_NAME']
MANAGEMENT_ACCOUNT_ID                = os.environ['MANAGEMENT_ACCOUNT_ID']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(ACCOUNT_TABLE)

s3 = boto3.resource('s3')
sfn = boto3.client('stepfunctions')
ec2 = boto3.client('ec2')

def modify_bucket_policy(bucket, statement_id, resource_arns=None,
                         principals=None, principal_type=None,
                         actions=None, effect='Allow', delete=False):

    policy = s3.BucketPolicy(bucket)

    if principals is None:
        principals = []

    if resource_arns is None:
        resource_arns = []

    try:
        policy_document = json.loads(policy.policy)
    except botocore.exceptions.ClientError:
        policy_document = {
            'Version': '2012-10-17',
            'Statement': []
        }

    statement = None
    for idx, s in enumerate(policy_document['Statement']):
        if s.get('Sid') == statement_id:
            statement = s
            break

    if statement is None:
        if actions is None:
            actions = ['s3:PutObject']

        statement = {
            'Sid': statement_id,
            'Effect': effect,
            'Principal': { principal_type: principals },
            'Action': actions,
            'Resource': resource_arns
        }

        if 's3:PutObject' in actions:
            statement['Condition'] = {
                'StringEquals': {'s3:x-amz-acl': 'bucket-owner-full-control'}}

        policy_document['Statement'].append(statement)

    else:
        # Update principals
        principal_type = principal_type or statement['Principal'].keys()[0]
        old_principals = statement['Principal'][principal_type]
        if type(old_principals) is not list:
            old_principals = [old_principals]

        # Update resources
        old_resource_arns = statement['Resource']
        if type(old_resource_arns) is not list:
            old_resource_arns = [old_resource_arns]

        if delete:
            statement['Principal'][principal_type] = list(
                set(old_principals).difference(principals))
            statement['Resource'] = list(
                set(old_resource_arns).difference(resource_arns))

            if len(statement['Resource']) == 0:
                policy_document['Statement'].pop(idx)

        else:
            statement['Principal'][principal_type] = list(
                set(old_principals).union(principals))

            statement['Resource'] = list(
                set(old_resource_arns).union(resource_arns))

            statement['Effect'] = effect

    print json.dumps(policy_document, indent=4)

    policy.put(Policy=json.dumps(policy_document))


def lambda_handler(event, context):
    role_arn = event['RoleARN']
    account_id = role_arn.split(':')[4]
    rand_token = base64.b32encode(os.urandom(10))

    # Try to create the record
    table.put_item(
        Item={
            'AccountID': account_id,
            'RoleARN': role_arn
        })

    # Update the necessary bucket policies for read/write access
    modify_bucket_policy(
        CLOUDTRAIL_BUCKET, 'PutObject',
        ['arn:aws:s3:::{}/AWSLogs/{}/*'.format(CLOUDTRAIL_BUCKET, account_id)],
        principal_type='Service', principals=['cloudtrail.amazonaws.com'])

    modify_bucket_policy(
        CONFIG_BUCKET, 'PutObject',
        ['arn:aws:s3:::{}/AWSLogs/{}/*'.format(CONFIG_BUCKET, account_id)],
        principal_type='Service', principals=['config.amazonaws.com'])

    modify_bucket_policy(
        DIST_BUCKET, 'GetObject',
        principal_type='AWS', principals=[
            'arn:aws:iam::{}:root'.format(account_id)
        ])

    sm_input = {
        'StateMachineArn': DEPLOY_TEMPLATE_STATE_MACHINE_ARN,
        'Workflows': []
    }

    resp = ec2.describe_regions()
    for r in resp['Regions']:
        region = r['RegionName']
        workflow = {
            'ExecutionName': 'Deploy_{}_{}_{}_{}'.format(
                STACK_NAME, account_id, region, rand_token),
            'RoleARN': role_arn,
            'Region': region,
            'TemplateURL': posixpath.join(
                'https://s3.amazonaws.com/', DIST_BUCKET, TEMPLATE_FILE_NAME),
            'Parameters': {
                'ExternalCloudTrailBucket': CLOUDTRAIL_BUCKET,
                'ExternalConfigBucket': CONFIG_BUCKET,
                'EventsSNSNotificationURL': EVENTS_SNS_NOTIFICATION_URL,
                'ConfigSNSNotificationURL': CONFIG_SNS_NOTIFICATION_URL,
                'CloudTrailSNSNotificationURL': CLOUDTRAIL_SNS_NOTIFICATION_URL,
                'ManagementAccountID': MANAGEMENT_ACCOUNT_ID
            },
            'Capabilities': ['CAPABILITY_NAMED_IAM'],
            'Stack': {
                'StackName': STACK_NAME
            }
        }
        sm_input['Workflows'].append(workflow)

    resp = sfn.start_execution(
        stateMachineArn=PARALLEL_EXECUTION_STATE_MACHINE_ARN,
        name='Deploy_{}_{}_{}'.format(STACK_NAME, account_id, rand_token),
        input=json.dumps(sm_input))

    table.update_item(
        Key={ 'AccountID': account_id },
        AttributeUpdates={
            'WorkflowARN': {
                'Value': resp['executionArn'],
                'Action': 'PUT'
            },
            'Started': {
                'Value': resp['startDate'].isoformat(),
                'Action': 'PUT'
            }
        })

    return {
        'AccountID': account_id,
        'RoleARN': role_arn,
        'WorkflowARN': resp['executionArn'],
        'Started': resp['startDate'].isoformat()
    }
