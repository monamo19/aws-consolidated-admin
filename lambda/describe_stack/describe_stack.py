import base64
import boto3
import botocore
import os

kms = boto3.client('kms')

KMS_KEY_ID = os.environ['KMS_KEY_ID']

def decrypt(ciphertext):
    return kms.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext))['Plaintext']

STACK_KEYS = {'StackName', 'StackId', 'StackStatus', 'Parameters',
              'Outputs', 'Tags', 'Capabilities', 'NotificationARNs',
              'StackStatusReason', 'RoleARN', 'ChangeSetId'}

def lambda_handler(event, context):
    sess = boto3.session.Session(
        aws_access_key_id=event['Credentials']['AccessKeyId'],
        aws_secret_access_key=decrypt(event['Credentials']['SecretAccessKeyCiphertext']),
        aws_session_token=event['Credentials']['SessionToken'],
        region_name=event['Region'])

    cfn = sess.client('cloudformation')

    try:
        stack_query = event['Stack']['StackId']
    except KeyError:
        stack_query = event['Stack']['StackName']

    try:
        resp = cfn.describe_stacks(StackName=stack_query)
    except botocore.exceptions.ClientError as e:
        if e.message.endswith('does not exist'):
            return {
                'StackName': event['Stack']['StackName'],
                'StackStatus': 'DOES_NOT_EXIST'
            }

        raise e

    resp = resp['Stacks'][0]

    return { k: v for k, v in resp.iteritems() if k in STACK_KEYS }
