import base64
import boto3
import os

kms = boto3.client('kms')

KMS_KEY_ID = os.environ['KMS_KEY_ID']

def decrypt(ciphertext):
    return kms.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext))['Plaintext']

def lambda_handler(event, context):
    sess = boto3.session.Session(
        aws_access_key_id=event['Credentials']['AccessKeyId'],
        aws_secret_access_key=decrypt(
            event['Credentials']['SecretAccessKeyCiphertext']),
        aws_session_token=event['Credentials']['SessionToken'],
        region_name=event['Region'])

    cfn = sess.client('cloudformation')

    resp = cfn.delete_stack(StackName=event['Stack']['StackId'])

    return {
        'RequestId': resp['ResponseMetadata']['RequestId']
    }
