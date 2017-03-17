import base64
import boto3
import botocore
import os

kms = boto3.client('kms')

KMS_KEY_ID = os.environ['KMS_KEY_ID']

def decrypt(ciphertext):
    return kms.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext))['Plaintext']

def format_parameters(params):
    return [{
        'ParameterKey': k,
        'ParameterValue': v,
        'UsePreviousValue': False
    } for k,v in params.iteritems()]

def lambda_handler(event, context):
    sess = boto3.session.Session(
        aws_access_key_id=event['Credentials']['AccessKeyId'],
        aws_secret_access_key=decrypt(
            event['Credentials']['SecretAccessKeyCiphertext']),
        aws_session_token=event['Credentials']['SessionToken'],
        region_name=event['Region'])

    cfn = sess.client('cloudformation')

    try:
        resp = cfn.update_stack(
            TemplateURL=event['TemplateURL'],
            StackName=event['Stack']['StackName'],
            Capabilities=event.get('Capabilities', []),
            Parameters=format_parameters(event['Parameters']))
    except botocore.exceptions.ClientError as e:
        if e.message.endswith('No updates are to be performed.'):
            return {'Warning': 'NOTHING_TO_UPDATE'}

        raise e

    resp['Warning'] = 'NONE' # Ew

    return resp
